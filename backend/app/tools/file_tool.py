"""
文件操作 Tool - 读取、写入、列出沙盒内文件
"""
from app.tools.base import BaseTool, register_tool
from app.services.sandbox_service import sandbox_service


@register_tool
class FileReadTool(BaseTool):
    """读取沙盒内文件"""

    @property
    def id(self) -> str:
        return "file_read"

    @property
    def name(self) -> str:
        return "读取文件"

    @property
    def description(self) -> str:
        return """【读取文件】用于查看沙盒内文件的内容。
适用场景：
- 用户说"读取文件"、"查看文件内容"、"打开文件"
- 用户说"看看 xx 文件里写的什么"
- 用户说"帮我查看配置"

参数：path 是文件路径（相对于沙盒根目录）"""

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于沙盒根目录），例如 'workspace/main.py' 或 'config.json'"
                }
            },
            "required": ["path"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        # 使用传入的 sandbox_path 进行文件操作
        result = await sandbox_service.read_file(
            user_id=None,
            file_path=params["path"],
            sandbox_path=sandbox_path
        )
        return result


@register_tool
class FileWriteTool(BaseTool):
    """写入内容到沙盒内文件"""

    @property
    def id(self) -> str:
        return "file_write"

    @property
    def name(self) -> str:
        return "写入文件"

    @property
    def description(self) -> str:
        return """【写入文件】用于创建新文件或覆盖已有文件的内容。
适用场景：
- 用户说"创建文件"、"写文件"、"保存到文件"
- 用户说"把 xx 内容写入 xx 文件"
- 用户说"帮我生成一个 xx 文件"

参数：path 是文件路径，content 是要写入的内容"""

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（相对于沙盒根目录），例如 'workspace/output.txt'"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文件内容"
                }
            },
            "required": ["path", "content"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        result = await sandbox_service.write_file(
            user_id=None,
            file_path=params["path"],
            content=params["content"],
            sandbox_path=sandbox_path
        )
        return result


@register_tool
class FileListTool(BaseTool):
    """列出沙盒内目录内容"""

    @property
    def id(self) -> str:
        return "file_list"

    @property
    def name(self) -> str:
        return "列出文件"

    @property
    def description(self) -> str:
        return """【列出文件】用于查看沙盒内某个目录包含哪些文件和子目录。
适用场景：
- 用户说"列出文件"、"查看目录"、"看看有哪些文件"
- 用户说"workspace 目录下有什么"
- 用户说"查看沙盒结构"

参数：path 是目录路径（空字符串表示根目录）"""

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径（相对于沙盒根目录），空字符串表示根目录。例如 'workspace' 或 ''"
                }
            },
            "required": []
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        result = await sandbox_service.list_directory(
            user_id=None,
            dir_path=params.get("path", ""),
            sandbox_path=sandbox_path
        )
        return result
