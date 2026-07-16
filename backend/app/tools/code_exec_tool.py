"""
代码执行 Tool - 在沙盒内执行 Python/JS 代码
"""
from app.tools.base import BaseTool, register_tool
from app.services.agent_code_policy import (
    parse_run_file_request,
    validate_code_execution,
    validate_runnable_file_path,
)
from app.services.sandbox_service import sandbox_service


@register_tool
class CodeExecTool(BaseTool):
    """在沙盒内执行代码"""

    @property
    def id(self) -> str:
        return "code_exec"

    @property
    def name(self) -> str:
        return "执行代码"

    @property
    def description(self) -> str:
        return "在沙盒环境内执行代码。支持两种模式：1）直接执行简短的 Python/JavaScript 示例代码；2）运行一个已经写入沙盒中的单个代码文件。代码执行输出是纯文本，不支持依赖安装、项目脚手架和交互式输入。"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的代码内容，或类似 'python demo.py' / 'node demo.js' 的单文件运行指令"
                },
                "path": {
                    "type": "string",
                    "description": "运行沙盒中已存在的单个代码文件路径，如 'quick_sort.py'"
                },
                "lang": {
                    "type": "string",
                    "enum": ["python", "javascript"],
                    "description": "代码语言",
                    "default": "python"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 30 秒",
                    "default": 30
                }
            },
            "required": []
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        lang = params.get("lang", "python")
        run_path = params.get("path")
        code = params.get("code", "")

        if not run_path:
            run_path = parse_run_file_request(code, lang)

        if run_path:
            allowed, error = validate_runnable_file_path(run_path, lang)
            if not allowed:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                    "error": error,
                }
            result = await sandbox_service.execute_file(
                user_id=None,
                file_path=run_path,
                lang=lang,
                timeout=params.get("timeout", 30),
                sandbox_path=sandbox_path,
            )
            result["success"] = bool(result.get("exit_code", -1) == 0 and not result.get("error"))
            return result

        if not code:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": "必须提供 code 或 path。",
            }

        allowed, error = validate_code_execution(code, lang)
        if not allowed:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": error,
            }

        result = await sandbox_service.execute_code(
            user_id=None,
            code=code,
            lang=lang,
            timeout=params.get("timeout", 30),
            sandbox_path=sandbox_path
        )
        result["success"] = bool(result.get("exit_code", -1) == 0 and not result.get("error"))
        return result

    @staticmethod
    def evaluate_practice(*, user_id: bytes, assessment_id: str, language: str, mode: str, code: str, test_cases: list[dict], progress=None) -> dict:
        """Restricted code-practice path used by the Code Execution Agent.

        Unlike general Agent code execution, this receives server-owned test cases
        and only returns an evaluation record; it never rewrites learner code.
        """
        from app.services.code_practice_service import run_practice_code
        return run_practice_code(
            user_id=user_id,
            assessment_id=assessment_id,
            language=language,
            mode=mode,
            code=code,
            test_cases=test_cases,
            progress=progress,
        )
