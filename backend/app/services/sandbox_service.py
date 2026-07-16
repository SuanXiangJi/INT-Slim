# -*- coding: utf-8 -*-
"""
Sandbox V2 - 分层隔离沙盒体系

目录结构:
    backend/sandbox/
    ├── users/
    │   └── <user_id_hex>/          # 用户持久化沙盒
    │       ├── workspace/          # 工作目录（文件读写）
    │       ├── output/             # 输出结果
    │       └── sessions/
    │           └── <session_id>/   # 单次会话隔离区
    ├── temp/
    │   └── <uuid>/                 # 匿名/临时沙盒（自动清理）
    └── system/                     # 系统级沙盒（预留）

安全设计:
    1. 绝对路径禁止
    2. .. 目录跳转禁止
    3. 符号链接解析（realpath）
    4. 路径前缀严格匹配
    5. 文件大小/数量配额限制
    6. 自动过期清理
"""
import os
import shutil
import asyncio
import hashlib
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from fastapi import HTTPException
import nest_asyncio
from app.services.sandbox_runtime import sandbox_runtime
nest_asyncio.apply()

# 沙盒根目录 - 绝对路径，与代码目录隔离
SANDBOX_ROOT = Path(__file__).parent.parent.parent / "sandbox"

# 配额限制
MAX_FILE_SIZE = 10 * 1024 * 1024       # 单个文件 10MB
MAX_TOTAL_SIZE = 100 * 1024 * 1024     # 用户总配额 100MB
MAX_FILES = 1000                        # 最大文件数
TEMP_TTL_HOURS = 24                     # 临时沙盒存活时间


class SandboxPath:
    """沙盒路径封装，所有路径操作必须通过此类。"""

    def __init__(self, root: Path):
        self._root = root.resolve()
        if not self._root.exists():
            self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def resolve(self, rel_path: str) -> Path:
        """将相对路径解析为沙盒内的绝对路径。"""
        if os.path.isabs(rel_path):
            raise HTTPException(status_code=403, detail="Access denied: absolute path not allowed")
        if ".." in Path(rel_path).parts:
            raise HTTPException(status_code=403, detail="Access denied: path traversal not allowed")

        target = (self._root / rel_path).resolve()
        # 严格检查：目标路径必须在沙盒根目录下
        try:
            target.relative_to(self._root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied: path outside sandbox")
        return target

    def exists(self, rel_path: str = "") -> bool:
        return self.resolve(rel_path).exists()

    def mkdir(self, rel_path: str, parents: bool = True) -> Path:
        p = self.resolve(rel_path)
        p.mkdir(parents=parents, exist_ok=True)
        return p

    def list_dir(self, rel_path: str = "") -> List[Dict[str, Any]]:
        p = self.resolve(rel_path)
        if not p.exists():
            return []
        entries = []
        for entry in os.listdir(p):
            entry_path = p / entry
            entries.append({
                "name": entry,
                "path": str(entry_path.relative_to(self._root)),
                "is_dir": entry_path.is_dir(),
                "size": entry_path.stat().st_size if entry_path.is_file() else None,
                "mtime": datetime.fromtimestamp(entry_path.stat().st_mtime).isoformat(),
            })
        return entries

    def read_file(self, rel_path: str, max_size: int = MAX_FILE_SIZE) -> str:
        p = self.resolve(rel_path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {rel_path}")
        if not p.is_file():
            raise HTTPException(status_code=400, detail=f"Not a file: {rel_path}")
        if p.stat().st_size > max_size:
            raise HTTPException(status_code=413, detail=f"File too large: {rel_path}")
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    def write_file(self, rel_path: str, content: str, mode: str = "w") -> int:
        p = self.resolve(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, mode, encoding="utf-8") as f:
            return f.write(content)

    def delete(self, rel_path: str) -> bool:
        p = self.resolve(rel_path)
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return True

    def get_size(self) -> int:
        """计算沙盒总大小（字节）。"""
        total = 0
        for dirpath, dirnames, filenames in os.walk(self._root):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
        return total

    def get_file_count(self) -> int:
        """计算文件数量。"""
        count = 0
        for dirpath, dirnames, filenames in os.walk(self._root):
            count += len(filenames)
        return count


class SandboxManager:
    """沙盒管理器 - 负责创建、查找、清理沙盒。"""

    def __init__(self):
        self._root = SANDBOX_ROOT
        self._users_dir = self._root / "users"
        self._temp_dir = self._root / "temp"
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保基础目录结构存在。"""
        for d in [self._root, self._users_dir, self._temp_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _ensure_standard_subdirs(path: Path):
        for sub in ["workspace", "output", "sessions"]:
            (path / sub).mkdir(parents=True, exist_ok=True)

    def _user_id_str(self, user_id: bytes) -> str:
        if isinstance(user_id, bytes):
            return user_id.hex()
        return str(user_id)

    def get_user_sandbox(self, user_id: bytes) -> SandboxPath:
        """获取用户持久化沙盒。"""
        uid = self._user_id_str(user_id)
        path = self._users_dir / uid
        path.mkdir(parents=True, exist_ok=True)
        self._ensure_standard_subdirs(path)
        return SandboxPath(path)

    def get_session_sandbox(self, user_id: bytes, session_id: str) -> SandboxPath:
        """获取会话级隔离沙盒。"""
        user_path = self.get_user_sandbox(user_id).root
        session_path = user_path / "sessions" / session_id
        session_path.mkdir(parents=True, exist_ok=True)
        return SandboxPath(session_path)

    def create_temp_sandbox(self) -> SandboxPath:
        """创建临时沙盒（匿名请求使用）。"""
        import uuid
        temp_id = uuid.uuid4().hex[:16]
        path = self._temp_dir / temp_id
        path.mkdir(parents=True, exist_ok=True)
        self._ensure_standard_subdirs(path)
        # 记录创建时间用于后续清理
        (path / ".created_at").write_text(datetime.now().isoformat())
        return SandboxPath(path)

    def get_temp_sandbox(self, temp_id: str) -> Optional[SandboxPath]:
        """获取已存在的临时沙盒。"""
        path = self._temp_dir / temp_id
        if path.exists():
            return SandboxPath(path)
        return None

    def delete_user_sandbox(self, user_id: bytes) -> bool:
        """删除用户沙盒（危险操作）。"""
        uid = self._user_id_str(user_id)
        path = self._users_dir / uid
        if path.exists():
            shutil.rmtree(path)
            return True
        return False

    def delete_temp_sandbox(self, temp_id: str) -> bool:
        """删除临时沙盒。"""
        path = self._temp_dir / temp_id
        if path.exists():
            shutil.rmtree(path)
            return True
        return False

    def cleanup_expired(self, max_age_hours: int = TEMP_TTL_HOURS) -> int:
        """清理过期的临时沙盒。"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        count = 0
        if not self._temp_dir.exists():
            return 0
        for item in self._temp_dir.iterdir():
            if not item.is_dir():
                continue
            created_file = item / ".created_at"
            if created_file.exists():
                try:
                    created = datetime.fromisoformat(created_file.read_text().strip())
                    if created < cutoff:
                        shutil.rmtree(item)
                        count += 1
                except Exception:
                    pass
            else:
                # 没有创建时间标记的也清理（保守策略）
                stat = item.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)
                if mtime < cutoff:
                    shutil.rmtree(item)
                    count += 1
        return count

    def check_quota(self, sandbox: SandboxPath) -> Dict[str, Any]:
        """检查沙盒配额使用情况。"""
        size = sandbox.get_size()
        files = sandbox.get_file_count()
        return {
            "size_bytes": size,
            "size_human": self._human_size(size),
            "max_size_bytes": MAX_TOTAL_SIZE,
            "file_count": files,
            "max_files": MAX_FILES,
            "within_quota": size <= MAX_TOTAL_SIZE and files <= MAX_FILES,
        }

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


# 全局单例
sandbox_manager = SandboxManager()


# 兼容旧接口的 SandboxService（逐步迁移）
class SandboxService:
    """兼容旧接口的沙盒服务（基于新的 SandboxManager）。"""

    def __init__(self):
        self._manager = sandbox_manager

    def _get_user_sandbox_path(self, user_id: bytes) -> Path:
        if user_id is None:
            return self._manager.create_temp_sandbox().root
        return self._manager.get_user_sandbox(user_id).root

    async def create_sandbox(self, user_id: bytes) -> str:
        if user_id is None:
            return str(self._manager.create_temp_sandbox().root)
        return str(self._manager.get_user_sandbox(user_id).root)

    def get_sandbox_path(self, user_id: bytes) -> Optional[str]:
        path = self._get_user_sandbox_path(user_id)
        if path.exists():
            return str(path)
        return None

    def ensure_session_sandbox(self, user_id: bytes, session_id: str) -> str:
        """Get or create session-level sandbox directory (shared within same session)."""
        if user_id is None:
            # 匿名用户：使用临时沙盒，但基于session_id复用
            temp_path = self._manager._temp_dir / session_id[:16]
            temp_path.mkdir(parents=True, exist_ok=True)
            self._manager._ensure_standard_subdirs(temp_path)
            return str(temp_path)
        # 登录用户：使用用户沙盒下的 sessions/<session_id>
        user_path = self._manager.get_user_sandbox(user_id).root
        session_path = user_path / "sessions" / session_id[:16]
        session_path.mkdir(parents=True, exist_ok=True)
        self._manager._ensure_standard_subdirs(session_path)
        # 同时确保workspace目录存在
        workspace_path = user_path / "workspace"
        workspace_path.mkdir(parents=True, exist_ok=True)
        return str(session_path)
    def ensure_sandbox_exists(self, user_id: bytes) -> str:
        sandbox_path = self.get_sandbox_path(user_id)
        if not sandbox_path:
            # 同步创建（首次访问）
            loop = asyncio.get_event_loop()
            sandbox_path = loop.run_until_complete(self.create_sandbox(user_id))
        return sandbox_path

    def _validate_path(self, sandbox_path: str, file_path: str) -> str:
        """Validate file path stays within sandbox."""
        if not file_path or not isinstance(file_path, str):
            raise HTTPException(status_code=400, detail="Invalid file path")
        if os.path.isabs(file_path) or file_path.startswith("/") or file_path.startswith("\\"):
            raise HTTPException(status_code=403, detail="Access denied: absolute path not allowed")
        if file_path.startswith("~") or "${HOME}" in file_path or "%HOME%" in file_path:
            raise HTTPException(status_code=403, detail="Access denied: path traversal not allowed")
        if ".." in Path(file_path).parts:
            raise HTTPException(status_code=403, detail="Access denied: path traversal not allowed")
        if chr(0) in file_path:
            raise HTTPException(status_code=403, detail="Access denied: invalid path")
        full_path = os.path.realpath(os.path.join(sandbox_path, file_path))
        resolved_sandbox = os.path.realpath(sandbox_path)
        if not (full_path == resolved_sandbox or full_path.startswith(resolved_sandbox + os.sep)):
            raise HTTPException(status_code=403, detail="Access denied: path outside sandbox")
        return full_path

    async def execute_code(self, user_id: bytes, code: str, lang: str, timeout: int = 30, sandbox_path: str = None) -> dict:
        if sandbox_path is None:
            sandbox_path = self.ensure_sandbox_exists(user_id)
        if lang == "python":
            cmd = [sandbox_runtime("python", "backend-python"), "-c", code]
        elif lang == "javascript":
            cmd = [sandbox_runtime("node", "node"), "-e", code]
        elif lang == "bash":
            cmd = ["bash", "-c", code]
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported language: {lang}")

        def _run():
            try:
                completed = subprocess.run(
                    cmd,
                    cwd=sandbox_path,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                    shell=False,
                )
                return {
                    "stdout": completed.stdout or "",
                    "stderr": completed.stderr or "",
                    "exit_code": completed.returncode,
                    "error": None,
                }
            except subprocess.TimeoutExpired:
                return {"stdout": "", "stderr": "", "exit_code": -1, "error": "Execution timeout"}
            except FileNotFoundError as e:
                return {
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                    "error": f"Runtime not found: {e.filename}",
                }
            except Exception as e:
                return {"stdout": "", "stderr": "", "exit_code": -1, "error": str(e)}

        return await asyncio.to_thread(_run)

    async def execute_file(self, user_id: bytes, file_path: str, lang: str, timeout: int = 30, sandbox_path: str = None) -> dict:
        if sandbox_path is None:
            sandbox_path = self.ensure_sandbox_exists(user_id)
        try:
            full_path = self._validate_path(sandbox_path, file_path)
        except HTTPException as e:
            return {"stdout": "", "stderr": "", "exit_code": -1, "error": e.detail}

        if not os.path.exists(full_path):
            return {"stdout": "", "stderr": "", "exit_code": -1, "error": f"File not found: {file_path}"}
        if not os.path.isfile(full_path):
            return {"stdout": "", "stderr": "", "exit_code": -1, "error": f"Not a file: {file_path}"}

        if lang == "python":
            cmd = [sandbox_runtime("python", "backend-python"), full_path]
        elif lang == "javascript":
            cmd = [sandbox_runtime("node", "node"), full_path]
        else:
            return {"stdout": "", "stderr": "", "exit_code": -1, "error": f"Unsupported language: {lang}"}

        def _run():
            try:
                completed = subprocess.run(
                    cmd,
                    cwd=sandbox_path,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                    shell=False,
                )
                return {
                    "stdout": completed.stdout or "",
                    "stderr": completed.stderr or "",
                    "exit_code": completed.returncode,
                    "error": None,
                }
            except subprocess.TimeoutExpired:
                return {"stdout": "", "stderr": "", "exit_code": -1, "error": "Execution timeout"}
            except FileNotFoundError as e:
                return {"stdout": "", "stderr": "", "exit_code": -1, "error": f"Runtime not found: {e.filename}"}
            except Exception as e:
                return {"stdout": "", "stderr": "", "exit_code": -1, "error": str(e)}

        return await asyncio.to_thread(_run)

    async def read_file(self, user_id: bytes, file_path: str, sandbox_path: str = None) -> dict:
        if sandbox_path is None:
            sandbox_path = self.ensure_sandbox_exists(user_id)
        try:
            full_path = self._validate_path(sandbox_path, file_path)
            if not os.path.exists(full_path):
                return {"content": None, "error": f"File not found: {file_path}"}
            if not os.path.isfile(full_path):
                return {"content": None, "error": f"Not a file: {file_path}"}
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"content": content, "error": None}
        except HTTPException:
            raise
        except Exception as e:
            return {"content": None, "error": str(e)}

    async def write_file(self, user_id: bytes, file_path: str, content: str, mode: str = "w", sandbox_path: str = None) -> dict:
        if sandbox_path is None:
            sandbox_path = self.ensure_sandbox_exists(user_id)
        try:
            full_path = self._validate_path(sandbox_path, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, mode, encoding="utf-8") as f:
                bytes_written = f.write(content)
            return {"bytes_written": bytes_written, "error": None}
        except HTTPException:
            raise
        except Exception as e:
            return {"bytes_written": 0, "error": str(e)}

    async def list_directory(self, user_id: bytes, dir_path: str = "", sandbox_path: str = None) -> dict:
        if sandbox_path is None:
            sandbox_path = self.ensure_sandbox_exists(user_id)
        try:
            if dir_path:
                full_path = self._validate_path(sandbox_path, dir_path)
            else:
                full_path = sandbox_path
            if not os.path.exists(full_path):
                return {"files": None, "error": f"Directory not found: {dir_path}"}
            if not os.path.isdir(full_path):
                return {"files": None, "error": f"Not a directory: {dir_path}"}
            entries = []
            for entry in os.listdir(full_path):
                entry_path = os.path.join(full_path, entry)
                entries.append({
                    "name": entry,
                    "is_dir": os.path.isdir(entry_path),
                    "size": os.path.getsize(entry_path) if os.path.isfile(entry_path) else None,
                })
            return {"files": entries, "error": None}
        except HTTPException:
            raise
        except Exception as e:
            return {"files": None, "error": str(e)}

    def delete_sandbox(self, user_id: bytes) -> dict:
        if user_id is None:
            return {"success": False, "error": "Cannot delete temp sandbox by user_id"}
        success = self._manager.delete_user_sandbox(user_id)
        return {"success": success, "message": "Sandbox deleted" if success else "Sandbox not found"}


# 兼容旧接口
sandbox_service = SandboxService()



