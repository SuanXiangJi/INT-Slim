from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath


ALLOWED_CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".cpp",
    ".cc",
    ".cxx",
    ".c",
    ".h",
    ".hpp",
    ".cs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
    ".m",
    ".scala",
    ".sql",
    ".sh",
    ".html",
    ".css",
    ".scss",
    ".less",
    ".vue",
    ".svelte",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".md",
}

PROJECT_LEVEL_FILENAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "pipfile",
    "pipfile.lock",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    ".gitignore",
    ".env",
    "vite.config.js",
    "vite.config.ts",
    "tsconfig.json",
    "webpack.config.js",
    "webpack.config.ts",
}

INSTALL_PATTERNS = [
    r"\bpip(?:3)?\s+install\b",
    r"\bpython\s+-m\s+pip\s+install\b",
    r"\bconda\s+install\b",
    r"\bmamba\s+install\b",
    r"\bpoetry\s+add\b",
    r"\bpipenv\s+install\b",
    r"\bnpm\s+(?:i|install)\b",
    r"\byarn\s+add\b",
    r"\bpnpm\s+add\b",
    r"\bbun\s+add\b",
    r"\bapt(?:-get)?\s+install\b",
    r"\byum\s+install\b",
    r"\bdnf\s+install\b",
    r"\bbrew\s+install\b",
    r"\bchoco\s+install\b",
    r"\bwinget\s+install\b",
]

PROCESS_PATTERNS = [
    r"\bos\.system\s*\(",
    r"\bsubprocess\.",
    r"\bPopen\s*\(",
    r"\bexec\s*\(",
    r"\beval\s*\(",
    r"\bchild_process\b",
    r"\bspawn\s*\(",
    r"\bexecSync\s*\(",
    r"\bexecFile\s*\(",
]

FILE_WRITE_PATTERNS = [
    r"\bopen\s*\([^)]*,\s*[\"'][wa+]",
    r"\bPath\s*\([^)]*\)\.write_(?:text|bytes)\s*\(",
    r"\bmkdir\s*\(",
    r"\bmakedirs\s*\(",
    r"\bfs\.(?:writeFile|writeFileSync|appendFile|appendFileSync|mkdir|mkdirSync)\b",
]


def validate_code_execution(code: str, lang: str) -> tuple[bool, str | None]:
    snippet = (code or "").strip()
    if not snippet:
        return False, "代码为空，无法执行。"
    if len(snippet) > 8000:
        return False, "代码过长。当前仅允许执行简短示例代码。"
    if snippet.count("\n") > 220:
        return False, "代码行数过多。当前仅允许执行简短示例代码。"
    if lang not in {"python", "javascript"}:
        return False, "仅允许执行 Python 或 JavaScript 简短示例代码。"

    lower = snippet.lower()
    for pattern in INSTALL_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return False, "不允许执行依赖安装或环境配置命令。"

    for pattern in PROCESS_PATTERNS:
        if re.search(pattern, snippet, re.IGNORECASE):
            return False, "仅允许简单代码示例，不允许启动子进程或执行系统命令。"

    for pattern in FILE_WRITE_PATTERNS:
        if re.search(pattern, snippet, re.IGNORECASE):
            return False, "代码执行工具不允许写文件或创建工程目录。"

    return True, None


def parse_run_file_request(code: str, lang: str) -> str | None:
    snippet = (code or "").strip()
    if not snippet:
        return None

    patterns = []
    if lang == "python":
        patterns.extend([
            r"^python\s+([^\s]+\.py)\s*$",
            r"^python3\s+([^\s]+\.py)\s*$",
            r"^exec\(open\([\"']([^\"']+\.py)[\"']\)\.read\(\)\)\s*$",
        ])
    elif lang == "javascript":
        patterns.extend([
            r"^node\s+([^\s]+\.m?js)\s*$",
        ])

    for pattern in patterns:
        match = re.match(pattern, snippet, re.IGNORECASE)
        if match:
            return normalize_virtual_path(match.group(1))
    return None


def normalize_virtual_path(path: str) -> str:
    text = (path or "").strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    return text.lstrip("/")


def validate_generated_file_path(path: str) -> tuple[bool, str | None]:
    normalized = normalize_virtual_path(path)
    if not normalized:
        return False, "文件路径不能为空。"

    pure_path = PurePosixPath(normalized)
    windows_parts = PureWindowsPath(path).parts
    if pure_path.is_absolute() or any(part == ".." for part in pure_path.parts) or any(part == ".." for part in windows_parts):
        return False, "不允许写入沙箱外路径。"

    filename = pure_path.name.lower()
    if filename in PROJECT_LEVEL_FILENAMES:
        return False, "当前仅允许生成单个代码文件，不允许生成项目级配置或依赖文件。"

    suffix = pure_path.suffix.lower()
    if suffix not in ALLOWED_CODE_EXTENSIONS:
        return False, "当前仅允许生成单个代码或文档文件。"

    return True, None


def validate_runnable_file_path(path: str, lang: str) -> tuple[bool, str | None]:
    normalized = normalize_virtual_path(path)
    if not normalized:
        return False, "文件路径不能为空。"

    pure_path = PurePosixPath(normalized)
    windows_parts = PureWindowsPath(path).parts
    if pure_path.is_absolute() or any(part == ".." for part in pure_path.parts) or any(part == ".." for part in windows_parts):
        return False, "不允许运行沙箱外路径。"

    suffix = pure_path.suffix.lower()
    if lang == "python" and suffix != ".py":
        return False, "Python 运行仅允许 .py 文件。"
    if lang == "javascript" and suffix not in {".js", ".mjs"}:
        return False, "JavaScript 运行仅允许 .js 或 .mjs 文件。"
    return True, None


def validate_single_generated_file(existing_path: str | None, new_path: str) -> tuple[bool, str | None, str | None]:
    allowed, error = validate_generated_file_path(new_path)
    if not allowed:
        return False, error, existing_path

    normalized = normalize_virtual_path(new_path)
    if existing_path and existing_path != normalized:
        return False, f"当前一次回答只允许生成一个文件。已生成: {existing_path}", existing_path
    return True, None, normalized
