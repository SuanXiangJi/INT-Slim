"""
Autonomous Agent Service - Native LLM tool calling with ReAct + Reflexion.

Public API
----------
    AutonomousAgent(...).run(messages, user_input) -> AsyncGenerator[dict, None]

The async generator yields structured events:
    {"type": "thinking",    "data": {"step": N, "content": "..."}}
    {"type": "action",      "data": {"step": N, "tool": "...", "params": {...}}}
    {"type": "observation", "data": {"step": N, "tool": "...", "success": bool, "raw": {...}, "formatted": "..."}}
    {"type": "reflection",  "data": {"step": N, "n": K, "content": "..."}}
    {"type": "ask",         "data": {"content": "..."}}
    {"type": "finish",      "content": "..."}
    {"type": "done",        "data": {"steps": N, "tools": [...], "reflections": K, "answer": "..."}}
    {"type": "error",       "data": {"message": "..."}}

The wire layer (conversation.py) maps these to SSE JSON.
"""
from __future__ import annotations
from string import Template

import asyncio
import json
import re
from typing import (AsyncGenerator, Awaitable, Callable, Dict, List,
                    Optional, Any)

from app.services.llm_service import llm_service

# Reflexion v2: structured reflection with persistent memory
try:
    from app.services.reflection_store import ReflectionEntry, get_reflection_store
except ImportError:
    get_reflection_store = None
    ReflectionEntry = None


# ─── Tool result truncation ───────────────────────────────────────────
MAX_TOOL_RESULT_LENGTH = 4000  # Truncate tool results beyond this to save context

_TOOL_PURPOSES = {
    "datetime": "核实当前日期和时间",
    "web_search": "查找可核验的最新网页资料",
    "url_fetch": "读取候选网页的原文细节",
    "knowledge_search": "查找与问题直接相关的学习资料",
    "knowledge_graph": "补充知识点之间的关联",
    "code_exec": "运行简短代码并验证实际结果",
    "calculator": "核对计算过程和数值",
    "file_read": "读取指定文件的实际内容",
    "file_write": "按要求写入单个文件",
    "file_list": "确认可用文件和目录",
    "ask_user": "补充继续执行所必需的信息",
}


def _tool_transition(tool_name: str, *, has_prior_results: bool = False, corrective: bool = False) -> str:
    purpose = _TOOL_PURPOSES.get(tool_name, f"完成当前任务所需的 {tool_name} 操作")
    if corrective:
        return f"审核发现仍需补充验证，接下来调用工具以{purpose}。"
    if has_prior_results:
        return f"基于上一项结果，还需要进一步确认，接下来调用工具以{purpose}。"
    return f"为获得完成回答所需的信息，接下来调用工具以{purpose}。"


class AgentInterrupted(Exception):
    """Raised when a running await is preempted by the user."""


def _truncate_result(result, max_len: int = MAX_TOOL_RESULT_LENGTH):
    """Truncate large string fields in a tool result.

    Always returns a *new* object so the caller's view of the original
    tool result is never mutated (important for transcript persistence).
    """
    if not isinstance(result, dict):
        return result
    out = dict(result)  # shallow copy is fine because we only mutate string fields
    for key in ("content", "summary", "raw_text"):
        v = out.get(key)
        if isinstance(v, str) and len(v) > max_len:
            out[key] = v[:max_len] + f"\n... [truncated {len(v) - max_len} chars]"
    return out


# ─── Reflection prompt (中文) ─────────────────────────────────────────────
# 鈹€鈹€鈹€ Reflection prompt (中文) 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
STRUCTURED_REFLECT_PROMPT = """你是一个严格的自我评审员（Reflexion 方法）。

# 用户问题
$user_input

# Agent 的回答
$answer

# 工具调用记录
$tool_history
$prev_block
$relevant_reflections
$strategy_hints

请按以下五个维度评估 Agent 的回答，其中前四项需要评分：
1. 事实依据：回答中的数字、日期、名称等事实是否有对应工具结果支撑？
2. 验证深度：不确定的 claims 是否在回答前被工具验证过？
3. 完整性：是否覆盖了用户问题的所有方面？有没有遗漏的工具调用？
4. 直接性：是否回答了用户的问题，还是在绕弯子？
5. 相关性：回答中是否包含用户未要求的信息或无效工具调用？

只输出一个合法 JSON 对象，不要 Markdown 代码块，不要额外文字：
{
  "overall": "PASS 或 FAIL",
  "scores": {
    "factual_grounding": 0.0到1.0,
    "verification_depth": 0.0到1.0,
    "completeness": 0.0到1.0,
    "directness": 0.0到1.0
  },
  "feedback": "具体、简短的检查结论",
  "action_plan": "需要补救时填写 tool_name({参数JSON})，否则为空字符串",
  "strategy_hint": "可复用经验；没有则为空字符串"
}
只有四项评分均不低于 0.8 且没有明显无效调用时，overall 才能为 PASS。
"""



def _ask_user_tool_definition() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "Ask the user a clarifying question when you cannot proceed "
                "without more information. Use sparingly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The clarifying question to ask the user"
                    }
                },
                "required": ["question"],
            },
        },
    }


class AutonomousAgent:
    """A single request's autonomous agent run.

    The caller is responsible for providing tool definitions and an async
    executor (`tool_executor(name, params) -> dict`).  This keeps the service
    independent from the tool registry so tools can be substituted in tests.
    """

    def __init__(
        self,
        model: str = "deepseek:deepseek-chat",
        enable_reflection: bool = True,
        max_reflections: int = 2,
        max_iterations: int = 16,
        tool_definitions: Optional[List[dict]] = None,
        tool_executor: Optional[Callable[[str, dict], Awaitable[dict]]] = None,
        # 新参数
        min_tool_calls_before_answer: int = 1,
        skip_reflection_if_grounded: bool = True,
        interrupt_event: Optional[asyncio.Event] = None,
    ):
        self.model = model
        self.enable_reflection = enable_reflection
        self.max_reflections = max_reflections
        self.max_iterations = max_iterations
        self.tool_definitions = list(tool_definitions or [])
        # Inject a virtual ask-user tool so the model can still ask clarifying
        # questions via native tool calling.
        if not any(
            t.get("function", {}).get("name") == "ask_user"
            for t in self.tool_definitions
        ):
            self.tool_definitions.append(_ask_user_tool_definition())
        self.tool_executor = tool_executor
        self._tool_name_set = {
            t["function"]["name"] for t in self.tool_definitions
            if isinstance(t, dict) and "function" in t
        }
        self.min_tool_calls_before_answer = min_tool_calls_before_answer
        self.skip_reflection_if_grounded = skip_reflection_if_grounded
        self.interrupt_event = interrupt_event
        self._reflection_store = None
        self.preloaded_evidence: List[dict] = []
        self.profile_context = ""

    async def _await_interruptibly(self, awaitable, poll_interval: float = 0.1):
        """Await work while polling the cross-worker interrupt flag."""
        task = asyncio.ensure_future(awaitable)
        try:
            while not task.done():
                if self.interrupt_event and self.interrupt_event.is_set():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    raise AgentInterrupted()
                await asyncio.wait({task}, timeout=poll_interval)
            return await task
        except asyncio.CancelledError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise

    async def _iterate_interruptibly(self, source):
        iterator = source.__aiter__()
        while True:
            try:
                yield await self._await_interruptibly(anext(iterator))
            except StopAsyncIteration:
                return

    # ── Prompt construction ─────────────────────────────────────────────
    def system_prompt(self) -> str:
        tools_desc = "\n".join(
            self._format_tool_definition(t)
            for t in self.tool_definitions
        ) or "- (no tools available)"
        return (
            "You are XBot, an autonomous agent that plans, uses tools, and reasons step by step.\n\n"
            "# Available tools\n"
            f"{tools_desc}\n\n"
            "# Output rules (CRITICAL - follow strictly)\n"
            "- Thinking: focus on reasoning, DO NOT repeat or rephrase the user's question\n"
            "- Use bullet points (·) for lists, keep each point under 20 words\n"
            "- CRITICAL: Focus ONLY on the current/last user message. Ignore unrelated context from previous conversation history.\n"
            "- Numbers/dates/quotes must come from a tool result you actually called\n"
            "- A reference title alone is not evidence for a precise number; omit benchmark/QPS figures "
            "unless that exact figure appears in the supplied evidence or a tool result\n"
            "- If you cannot verify something, say \"(未核实)\" instead of guessing\n"
            "- For `url_fetch`, always set `focus` to a concrete angle "
            "  (e.g. 'pricing' not 'main content')\n\n"
            "# Code execution policy\n"
            "- `code_exec` is only for short self-contained examples\n"
            "- Never install dependencies or run shell/package-manager commands\n"
            "- Never use `code_exec` to write files or scaffold a project\n"
            "- If a file must be generated, write at most one code file in the whole answer\n\n"
            "# Final answer contract when using sandbox / code tools\n"
            "- The user cannot see the sandbox directly, so never assume hidden execution is self-explanatory\n"
            "- If you wrote a file, state the exact file path\n"
            "- If the code is short, include the full source in a fenced code block\n"
            "- If you executed code, report the actual run method and the actual stdout/stderr result\n"
            "- Never claim code ran successfully unless a tool result confirms it\n"
            "- If execution failed because the sandbox lacks a dependency, say it is a server sandbox environment limitation\n"
            "- For missing modules, explain how the user should install the dependency locally and then run the code\n"
            "- Do not paste a full traceback in the final answer unless the user explicitly asks for debugging details\n"
            "- If execution failed, explain the failure plainly and give the corrected next step\n\n"
            "# When to stop using tools and answer\n"
            "- Current/live queries (weather, news, exchange rates, prices): call `web_search` before answering\n"
            "- Use `url_fetch` only when a specific search result needs deeper verification\n"
            "- Never claim live-data access is unavailable before trying the available search tools\n"
            "- Info queries (price, date, definition): 1-2 relevant tool results → answer\n"
            "- Multi-source queries (compare, analyze): ≥2 different sources → answer\n"
            "- For learning and technical research, prefer official documentation, universities, papers, "
            "standards, and primary project repositories\n"
            "- Do not use one tutorial website as the default source; diversify domains when multiple sources are shown\n"
            "- Never call the same tool 3+ times for the same sub-task\n"
            "- If tool results already answer the question → stop and answer\n\n"
            "# Reflexion\n"
            "If you see \"Your previous self-reflections\", follow the reflection's "
            "instructions exactly (tool + params), do not repeat the same mistake\n"
        )

    def _format_tool_definition(self, tool: dict) -> str:
        fn = tool.get("function", {})
        name = fn.get("name", "unknown")
        desc = fn.get("description", "")
        schema = fn.get("parameters", {})
        schema_str = json.dumps(schema, ensure_ascii=False)
        return f"- **{name}**: {desc}\n  Parameters: {schema_str}"

    @staticmethod
    def _looks_like_direct_explanation(user_input: str) -> bool:
        text = (user_input or "").strip().lower()
        if not text:
            return False
        normalized = re.sub(r"[\s，。！!？?]+", "", text)
        if normalized in {"你好", "嗨", "hi", "hello", "谢谢", "感谢", "再见", "晚安"}:
            return True
        realtime_markers = (
            "今天", "明天", "昨天", "现在", "最新", "实时", "新闻", "价格",
            "天气", "汇率", "股票", "官网", "链接", "http://", "https://",
            "深度调研", "调研", "论文检索", "文献检索", "研究综述", "相关论文",
        )
        if any(marker in text for marker in realtime_markers):
            return False
        explain_markers = (
            "解释", "讲讲", "讲解", "说明", "用例子", "举例", "图解",
            "分步", "一步步", "通俗", "容易理解", "是什么", "原理",
            "你能帮我", "你可以帮我", "你会做什么", "你能做什么",
            "你有什么能力", "你可以做什么", "介绍一下你自己",
        )
        return any(marker in text for marker in explain_markers)

    @staticmethod
    def _looks_like_simple_response(user_input: str) -> bool:
        text = (user_input or "").strip().lower()
        normalized = re.sub(r"[\s，。！!？?]+", "", text)
        if normalized in {"你好", "嗨", "hi", "hello", "谢谢", "感谢", "再见", "晚安"}:
            return True
        return any(marker in text for marker in (
            "你能帮我", "你可以帮我", "你会做什么", "你能做什么",
            "你有什么能力", "你可以做什么", "介绍一下你自己",
        ))

    @staticmethod
    def _reflection_suggests_direct_answer(reflections: List[str]) -> bool:
        text = "\n".join(reflections or "")
        direct_markers = (
            "无需调用工具",
            "不调用无关工具",
            "直接回答",
            "避免为了展示代码而执行实际代码",
            "纯解释性问题",
        )
        return any(marker in text for marker in direct_markers)

    @classmethod
    def should_answer_directly(cls, user_input: str, reflections: Optional[List[str]] = None) -> bool:
        if not cls._looks_like_direct_explanation(user_input):
            return False
        return not reflections or cls._reflection_suggests_direct_answer(reflections)

    # ── Tool result formatting (compact, human-readable) ────────────────
    MAX_DISPLAY_LENGTH = 600  # 单条观察结果最大显示长度

    def format_result(self, tool_name: str, data: Any) -> str:
        if not isinstance(data, dict):
            return f"  {data}"
        if data.get("_ask"):
            return f"  ? {data.get('question', '')}"
        if not data.get("success", True):
            if tool_name == "code_exec":
                reason = self._short_failure_reason(data)
                module = self._missing_python_module(data.get("stderr") or "", data.get("error") or "")
                if module:
                    package = {
                        "redis": "redis",
                        "yaml": "PyYAML",
                        "cv2": "opencv-python",
                        "PIL": "Pillow",
                        "sklearn": "scikit-learn",
                    }.get(module, module)
                    return f"  ✗ {reason}。本地运行前请先安装依赖：pip install {package}"
                return f"  ✗ {reason}"
            err = data.get("error") or data.get("stderr") or (
                f"Process exited with code {data.get('exit_code')}"
                if data.get("exit_code") not in (None, 0) else "unknown error"
            )
            return f"  ✗ {err}"

        if "results" in data and self._looks_like_course_search(data.get("results") or []):
            items = data.get("results") or []
            total = data.get("total_courses_with_matches", len(items))
            out = [f"  Knowledge: {total} 个相关课程"]
            for i, item in enumerate(items[:5], 1):
                course = item.get("course_name") or item.get("course_id") or "课程"
                page_count = item.get("page_count", 0)
                out.append(f"  {i}. {course}（{page_count} 个相关页面）")
                for page in (item.get("pages") or [])[:3]:
                    title = page.get("title") or page.get("slug") or "未命名页面"
                    summary = (page.get("summary") or "").strip()
                    out.append(f"     - {title}")
                    if summary:
                        out.append(f"       {summary[:100]}")
            return "\n".join(out)

        # url_fetch：优先用 summary 结构化输出
        if "summary" in data:
            title = data.get("title", "")
            summary = (data.get("summary") or "").strip()
            focus = data.get("focus", "")
            raw_len = data.get("raw_length", 0)

            parts = []
            if title:
                parts.append(f"【{title}】")
            if focus and focus != "主要内容":
                parts.append(f"  方向: {focus}")
            # 摘要分段截断显示
            display = summary
            if len(display) > self.MAX_DISPLAY_LENGTH:
                display = display[:self.MAX_DISPLAY_LENGTH] + f"\n  ... [内容过长，已截断]"
            parts.append("  " + display.replace("\n", "\n  "))
            if raw_len:
                parts.append(f"  (原始长度: {raw_len}字符)")
            return "\n".join(parts)

        # web_search：简洁列表
        if "results" in data:
            items = data["results"]
            count = data.get("count", len(items))
            out = [f"  📰 {count} 条结果"]
            for i, item in enumerate(items[:5], 1):  # 最多显示5条
                t = item.get("title", "N/A")
                u = item.get("url", "")
                s = (item.get("content") or "").strip()[:120]
                out.append(f"  {i}. {t}")
                if u:
                    out.append(f"     🔗 {u[:80]}")
                if s:
                    out.append(f"     {s}")
            if count > 5:
                out.append(f"  ... 还有 {count - 5} 条结果")
            return "\n".join(out)

        # legacy url_fetch (raw content)
        if "content" in data:
            content = str(data.get("content", ""))[:300]
            return f"  ✓ fetched · {content}"

        # code_exec
        if "stdout" in data:
            out = ["  ✓ executed"]
            stdout = data.get("stdout", "").rstrip()
            if stdout:
                lines = stdout.split("\n")
                display = "\n".join(lines[:10])
                if len(lines) > 10:
                    display += f"\n  ... (共{len(lines)}行)"
                out.append("  " + display.replace("\n", "\n  "))
            if data.get("stderr"):
                out.append(f"  ⚠ stderr: {data['stderr'].rstrip()[:200]}")
            return "\n".join(out)

        return "  " + json.dumps(data, ensure_ascii=False)[:300]

    @staticmethod
    def _looks_like_course_search(items: Any) -> bool:
        if not isinstance(items, list) or not items:
            return False
        first = items[0]
        return isinstance(first, dict) and (
            "course_name" in first
            or "course_id" in first
            or "pages" in first
        )

    @staticmethod
    def _looks_like_run_command(code: str) -> bool:
        text = (code or "").strip()
        if not text:
            return False
        prefixes = ("python ", "python3 ", "node ", "bash ", "sh ")
        return text.startswith(prefixes) or text.startswith("exec(open(")

    @staticmethod
    def _missing_python_module(stderr: str, error: str = "") -> Optional[str]:
        text = "\n".join(part for part in (stderr or "", error or "") if part)
        match = re.search(r"No module named ['\"]([^'\"]+)['\"]", text)
        return match.group(1) if match else None

    @staticmethod
    def _short_failure_reason(result: dict) -> str:
        stderr = (result.get("stderr") or "").strip()
        error = (result.get("error") or "").strip()
        module = AutonomousAgent._missing_python_module(stderr, error)
        if module:
            return f"服务器沙盒缺少 Python 依赖 `{module}`"
        if error:
            return error.splitlines()[0][:180]
        if stderr:
            lines = [line.strip() for line in stderr.splitlines() if line.strip()]
            if lines:
                return lines[-1][:180]
        return f"进程退出码：{result.get('exit_code')}"

    @staticmethod
    def _install_hint_for_missing_module(module: str, lang: str) -> str:
        package = {
            "redis": "redis",
            "yaml": "PyYAML",
            "cv2": "opencv-python",
            "PIL": "Pillow",
            "sklearn": "scikit-learn",
        }.get(module, module)
        if lang == "python":
            return (
                "本地运行前先安装依赖：\n"
                f"```bash\npip install {package}\n```\n"
                "如果你使用 conda/venv，请先激活对应环境再安装。"
            )
        return ""

    def _build_code_task_appendix(self, tool_history: List[dict]) -> str:
        if not tool_history:
            return ""

        file_write = None
        successful_exec = None
        failed_exec = None
        inline_code = None

        for item in tool_history:
            tool = item.get("tool")
            params = item.get("params") or {}
            result = item.get("result") or {}
            if tool == "file_write":
                file_write = item
            elif tool == "code_exec":
                if params.get("code") and not self._looks_like_run_command(params.get("code", "")):
                    inline_code = item
                if result.get("success"):
                    successful_exec = item
                else:
                    failed_exec = item

        if not any([file_write, successful_exec, failed_exec, inline_code]):
            return ""

        sections = ["\n\n---\n## 代码与执行记录"]

        if file_write:
            path = (file_write.get("params") or {}).get("path")
            content = (file_write.get("params") or {}).get("content", "")
            if path:
                sections.append(f"\n文件路径：`{path}`")
            if content:
                lang = "python" if str(path or "").lower().endswith(".py") else ""
                sections.append(f"\n源码：\n```{lang}\n{content.rstrip()}\n```")
        elif inline_code:
            code = (inline_code.get("params") or {}).get("code", "")
            lang = (inline_code.get("params") or {}).get("lang", "")
            if code:
                sections.append(f"\n执行的代码：\n```{lang}\n{code.rstrip()}\n```")

        run_item = successful_exec or failed_exec
        if run_item:
            params = run_item.get("params") or {}
            result = run_item.get("result") or {}
            run_desc = ""
            if params.get("path"):
                run_desc = f"运行方式：执行文件 `{params['path']}`"
            elif params.get("code"):
                code_text = params.get("code", "").strip()
                if self._looks_like_run_command(code_text):
                    run_desc = f"运行方式：`{code_text}`"
                else:
                    lang = params.get("lang", "python")
                    run_desc = f"运行方式：直接执行 {lang} 代码片段"
            if run_desc:
                sections.append(f"\n{run_desc}")

            stdout = (result.get("stdout") or "").rstrip()
            stderr = (result.get("stderr") or "").rstrip()
            exit_code = result.get("exit_code")

            if stdout:
                sections.append(f"\n标准输出：\n```text\n{stdout}\n```")
            if stderr:
                sections.append(f"\n标准错误：\n```text\n{stderr}\n```")
            if not stdout and not stderr:
                if result.get("success"):
                    sections.append("\n执行结果：程序执行完成，但没有输出内容。")
                else:
                    err = result.get("error") or f"进程退出码：{exit_code}"
                    sections.append(f"\n执行结果：失败，原因是 `{err}`。")
            elif result.get("success"):
                sections.append("\n执行结果：运行成功。")
            else:
                err = result.get("error") or f"进程退出码：{exit_code}"
                sections.append(f"\n执行结果：失败，原因是 `{err}`。")

        return "\n".join(sections).rstrip()

    def _build_code_task_appendix(self, tool_history: List[dict]) -> str:
        """Append user-facing code/run information without exposing raw tracebacks."""
        if not tool_history:
            return ""

        file_write = None
        successful_exec = None
        failed_exec = None
        inline_code = None

        for item in tool_history:
            tool = item.get("tool")
            params = item.get("params") or {}
            result = item.get("result") or {}
            if tool == "file_write":
                file_write = item
            elif tool == "code_exec":
                if params.get("code") and not self._looks_like_run_command(params.get("code", "")):
                    inline_code = item
                if result.get("success"):
                    successful_exec = item
                else:
                    failed_exec = item

        if not any([file_write, successful_exec, failed_exec, inline_code]):
            return ""

        sections = ["\n\n---\n## 代码与运行说明"]

        if file_write:
            path = (file_write.get("params") or {}).get("path")
            content = (file_write.get("params") or {}).get("content", "")
            if path:
                sections.append(f"\n文件路径：`{path}`")
            if content:
                lang = "python" if str(path or "").lower().endswith(".py") else ""
                sections.append(f"\n源码：\n```{lang}\n{content.rstrip()}\n```")
        elif inline_code:
            params = inline_code.get("params") or {}
            code = params.get("code", "")
            lang = params.get("lang", "")
            if code:
                sections.append(f"\n代码：\n```{lang}\n{code.rstrip()}\n```")

        run_item = successful_exec or failed_exec
        if run_item:
            params = run_item.get("params") or {}
            result = run_item.get("result") or {}
            run_desc = ""
            if params.get("path"):
                run_desc = f"运行方式：执行文件 `{params['path']}`"
            elif params.get("code"):
                code_text = params.get("code", "").strip()
                if self._looks_like_run_command(code_text):
                    run_desc = f"运行方式：`{code_text}`"
                else:
                    run_desc = f"运行方式：直接执行 {params.get('lang', 'python')} 代码片段"
            if run_desc:
                sections.append(f"\n{run_desc}")

            stdout = (result.get("stdout") or "").rstrip()
            stderr = (result.get("stderr") or "").rstrip()
            lang = (params.get("lang") or "python").lower()

            if result.get("success"):
                if stdout:
                    sections.append(f"\n运行输出：\n```text\n{stdout}\n```")
                elif stderr:
                    sections.append(f"\n运行提示：\n```text\n{stderr[:800]}\n```")
                else:
                    sections.append("\n运行结果：程序执行完成，但没有输出内容。")
                sections.append("\n执行状态：服务器沙盒运行成功。")
            else:
                reason = self._short_failure_reason(result)
                sections.append(f"\n执行状态：服务器沙盒未能完成运行，原因是：{reason}。")
                module = self._missing_python_module(stderr, result.get("error") or "")
                if module:
                    hint = self._install_hint_for_missing_module(module, lang)
                    if hint:
                        sections.append(f"\n你在本地正确运行时需要先准备环境：\n{hint}")
                else:
                    sections.append("\n建议：按上面的代码和运行方式在你的本地环境重试；如果仍失败，再查看完整错误信息定位。")

        return "\n".join(sections).rstrip()

    def _augment_answer_for_code_tasks(self, answer: str, tool_history: List[dict]) -> str:
        appendix = self._build_code_task_appendix(tool_history)
        if not appendix:
            return answer

        text = answer or ""
        has_code_tools = any(tc.get("tool") in {"file_write", "code_exec"} for tc in tool_history or [])
        if not has_code_tools:
            return text

        if "## 代码与运行说明" in text or "## 代码与执行记录" in text:
            return text
        return (text.rstrip() + appendix).strip()

    # ── Tool execution plumbing ─────────────────────────────────────────
    async def _execute_tool(self, name: str, params: dict) -> dict:
        if name == "ask_user":
            return {"_ask": True, "question": params.get("question", "")}
        if self.tool_executor is None:
            return {"success": False, "error": "no tool executor configured"}
        if name not in self._tool_name_set:
            return {"success": False, "error": f"unknown tool: {name}"}
        try:
            result = await self.tool_executor(name, params)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Reflexion ───────────────────────────────────────────────────────
    def _answer_looks_grounded(self, answer: str, tool_history: List[dict]) -> bool:
        """Heuristic: skip reflection when the answer already cites numbers,
        URLs, or explicit sources. Works for both English and Chinese."""
        import re
        if not answer:
            return False
        # Number patterns: percentages, prices, dates, years/months
        has_numbers = bool(re.search(
            r"\d+(?:[.,]\d+)?%|\d{4}\s*[年月日]|[$￥€]\s*\d",
            answer,
        ))
        # URLs (require http(s):// to avoid false positives like "::")
        has_urls = "http://" in answer or "https://" in answer
        # Source / citation tokens (zh + en)
        # Use surrounding-character boundaries to avoid false positives
        # like "据" inside "数据库" / "数据". A citation token only counts
        # when it is delimited by punctuation, whitespace, or sentence
        # boundaries on at least one side.
        has_sources = bool(re.search(
            r"(?:\bsource\b|\bsources?\b|\baccording to\b|\breference\b"
            r"|来源"
            r"|(?<=[\s\u3002\uff0c\uff1a\uff1b\u3001])据|(?<=^)据"
            r"|据(?=[\s\u3002\uff0c\uff1a\uff1b\u3001]|$)"
            r"|参考|引用"
            r"|Source:|Ref:"
            r"|\uff08[^\uff09]*\u6765\u6e90[^\uff09]*\uff09)",
            answer,
            re.IGNORECASE,
        ))
        # Tool history reference
        for tc in tool_history or []:
            tname = tc.get("tool", "") if isinstance(tc, dict) else ""
            if tname and tname in answer:
                has_sources = True
                break
        return has_numbers or has_urls or has_sources

    async def reflect(
        self,
        user_input: str,
        answer: str,
        tool_history: List[dict],
        prev_reflections: List[str],
        relevant_past: List[str] = None,
    ) -> dict:
        """Reflexion v2: structured reflection with persistent memory."""
        if not answer or len(answer.strip()) < 10:
            return {
                "scores": {"factual_grounding": 0.0, "verification_depth": 0.0,
                           "completeness": 0.0, "directness": 0.0},
                "overall": "FAIL",
                "feedback": "回答为空或太短。应继续使用工具获取实质性证据。",
                "action_plan": "调用更多工具收集信息后再回答。",
                "strategy_hint": "",
            }

        has_code_tool = any(tc.get("tool") in {"code_exec", "file_write", "file_read"} for tc in tool_history or [])
        if has_code_tool:
            text = answer.lower()
            mentions_code = "```" in answer or "代码" in answer or "source" in text
            mentions_output = ("输出" in answer or "结果" in answer or "stdout" in text or "stderr" in text)
            mentions_path = any(
                isinstance(tc.get("params"), dict)
                and tc.get("params", {}).get("path")
                and tc["params"]["path"] in answer
                for tc in tool_history or []
                if tc.get("tool") == "file_write"
            )
            if not mentions_output or (
                any(tc.get("tool") == "file_write" for tc in tool_history or [])
                and not (mentions_code or mentions_path)
            ):
                return {
                    "scores": {
                        "factual_grounding": 0.8,
                        "verification_depth": 0.8,
                        "completeness": 0.2,
                        "directness": 0.6,
                    },
                    "overall": "FAIL",
                    "feedback": "回答没有把沙箱中的代码、文件路径或实际运行结果对用户讲清楚。",
                    "action_plan": "重新组织最终答案，明确给出源码、文件路径和实际输出。",
                    "strategy_hint": "当使用代码或文件工具时，最终答复必须显式展示源码、文件位置和运行结果，因为用户看不到沙箱内部。",
                }

        def _short_result(res: Any) -> str:
            if isinstance(res, dict):
                if res.get("_ask"):
                    return f"询问用户: {res.get('question', '')}"
                if not res.get("success", True):
                    return f"错误: {res.get('error', 'unknown')}"
                if "summary" in res:
                    return (res.get("summary") or "")[:120]
                if "results" in res:
                    return f"{len(res['results'])} 条结果"
                if "stdout" in res:
                    return (res.get("stdout") or "")[:120]
            return json.dumps(res, ensure_ascii=False)[:120]

        log = "\n".join(
            f"  - {tc['tool']}({json.dumps(tc['params'], ensure_ascii=False)}) -> {_short_result(tc.get('result'))}"
            for tc in tool_history
        ) or "  (none)"
        if self.preloaded_evidence:
            evidence_lines = "\n".join(
                "    · "
                + str(ref.get("title") or ref.get("doc_id") or "参考资料")
                + (f"：{str(ref.get('snippet') or '')[:180]}" if ref.get("snippet") else "（仅有标题，不足以支撑精确事实）")
                for ref in self.preloaded_evidence[:5]
            )
            log += f"\n  - 检索 Agent 已提供 {len(self.preloaded_evidence)} 条资料：\n{evidence_lines}"

        prev_block = ""
        if prev_reflections:
            prev_block = "\n\n# 此前已完成的自我反思\n" + "\n".join(
                f"  - 第{i+1}次: {r}" for i, r in enumerate(prev_reflections)
            )

        relevant_block = ""
        if relevant_past:
            relevant_block = "\n\n# 历史上类似任务的反思经验\n" + "\n".join(
                f"  - {r}" for r in relevant_past
            )

        # === T-1: retrieve strategy hints from past similar tasks ===
        strategy_block = ""
        if self._reflection_store is not None:
            try:
                hints = self._reflection_store.search_strategies(user_input, top_k=3)
                if hints:
                    strategy_block = "\n\n# 策略红利（来自历史类似任务）\n" + "\n".join(
                        f"  - {h}" for h in hints
                    )
            except Exception:
                strategy_block = ""

        prompt = Template(STRUCTURED_REFLECT_PROMPT).safe_substitute(
            user_input=user_input, answer=answer,
            tool_history=log, prev_block=prev_block,
            relevant_reflections=relevant_block,
            strategy_hints=strategy_block,
        )
        if self.profile_context:
            prompt += (
                "\n\n用户画像是本轮可用上下文；若答案中的地点或偏好来自画像，不应判为臆测：\n"
                + self.profile_context[:800]
            )

        try:
            resp = llm_service.call_model_with_tools(
                messages=[{"role": "user", "content": prompt}],
                tools=None, model=self.model,
                stream=False, temperature=0.1, max_tokens=1600,
            )
            if isinstance(resp, dict):
                raw_resp = str(resp.get("content") or resp.get("reasoning_content") or "").strip()
            else:
                raw_resp = str(resp).strip()
        except Exception:
            return {
                "scores": {"factual_grounding": 1.0, "verification_depth": 1.0,
                           "completeness": 1.0, "directness": 1.0},
                "overall": "PASS",
                "feedback": "",
                "action_plan": "",
                "strategy_hint": "",
            }

        return self._parse_reflection_response(raw_resp)

    def _parse_reflection_response(self, raw: str) -> dict:
        """Parse structured JSON reflection; harvest `策略：...` from non-JSON (B) text."""
        import json, re
        default = {
            "scores": {"factual_grounding": 0.7, "verification_depth": 0.7,
                       "completeness": 0.7, "directness": 0.7},
            "overall": "FAIL",
            "feedback": raw[:200] if raw else "无法解析反思结果",
            "action_plan": "",
            "strategy_hint": "",
        }
        if not raw:
            return default

        def _harvest() -> str:
            m = re.search(r"策略[：:]\s*([^\n。]+)", raw)
            if not m:
                return ""
            v = m.group(1).strip().strip(chr(34) + chr(39) + chr(96))
            if not v or v in ("无", "none", "None", "N/A"):
                return ""
            return v

        # Accept multiple PASS variants: bare "PASS", "(A) PASS", "A: PASS",
        # "答案：A PASS", etc. Treat it as PASS only if no "(B)" / no "策略"
        # signal is also present.
        raw_compact = raw.strip()
        lower = raw_compact.lower()
        has_b_signal = bool(re.search(r"[（(]?\s*[bB]\s*[)）]\s*[:：]?", raw_compact))
        has_strategy = "策略" in raw_compact
        has_pass_signal = bool(re.search(r"\bpass\b|[（(]\s*[aA]\s*[)）]\s*[:：]?\s*pass",
                                          lower)) or lower.strip() in ("pass", "a", "(a)")
        if (
            has_pass_signal
            and not has_b_signal
            and not has_strategy
            and not raw_compact.lstrip().startswith(("{", "```"))
        ):
            return {
                "scores": {"factual_grounding": 1.0, "verification_depth": 1.0,
                           "completeness": 1.0, "directness": 1.0},
                "overall": "PASS",
                "feedback": "",
                "action_plan": "",
                "strategy_hint": "",
            }

        text = raw.strip()
        if text.startswith("```"):
            s_idx = text.find("{")
            e_idx = text.rfind("}")
            if s_idx >= 0 and e_idx > s_idx:
                text = text[s_idx:e_idx + 1]

        data = None
        try:
            data = json.loads(text)
        except Exception:
            m_json = re.search(r"\{[^{}]*\"scores\"\s*:[^{}]*\}", text, re.DOTALL)
            if m_json:
                try:
                    data = json.loads(m_json.group())
                except Exception:
                    pass

        if isinstance(data, dict):
            if not data.get("strategy_hint"):
                h = _harvest()
                if h:
                    data["strategy_hint"] = h
            scores = data.get("scores", {})
            if not isinstance(scores, dict):
                scores = {}
            normalized = {
                "factual_grounding": float(scores.get("factual_grounding", 0.7)),
                "verification_depth": float(scores.get("verification_depth", 0.7)),
                "completeness": float(scores.get("completeness", 0.7)),
                "directness": float(scores.get("directness", 0.7)),
            }
            overall = str(data.get("overall", "FAIL")).upper().strip()
            if overall not in ("PASS", "FAIL"):
                avg = sum(normalized.values()) / 4.0
                overall = "PASS" if avg >= 0.8 else "FAIL"
            return {
                "scores": normalized,
                "overall": overall,
                "feedback": str(data.get("feedback", "")).strip(),
                "action_plan": str(data.get("action_plan", "")).strip(),
                "strategy_hint": str(data.get("strategy_hint", "")).strip(),
            }

        default["strategy_hint"] = _harvest()
        fb_text = raw
        idx = fb_text.find("策略")
        if idx > 0:
            fb_text = fb_text[:idx]
        fb_text = fb_text.strip().rstrip("。.;;").strip()
        if fb_text:
            default["feedback"] = fb_text[:300]
        return default

    def _execute_action_plan(self, action_plan: str) -> Optional[dict]:
        """Parse a `(B)`-format action_plan and return {'tool': str, 'params': dict}."""
        import re as _re
        if not action_plan or not action_plan.strip():
            return None
        m = _re.search(r"`?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)`?", action_plan)
        if not m:
            return None
        tool_name = m.group(1)
        args_text = m.group(2).strip()
        try:
            import json as _json
            params = _json.loads("{" + args_text + "}")
            if not isinstance(params, dict):
                params = {"args": args_text}
        except Exception:
            params = {}
            for part in _re.split(r",\s*(?=[a-zA-Z_])", args_text):
                if ":" in part:
                    k, v = part.split(":", 1)
                    params[k.strip().strip("\"'")] = v.strip().strip("\"'")
            if not params:
                params = {"args": args_text}
        return {"tool": tool_name, "params": params}

    async def _save_reflection(self, user_input: str, answer: str,
                               tool_history, reflection: dict) -> None:
        """Persist reflection entry to the store (if available)."""
        if not get_reflection_store or not hasattr(self, "_reflection_store"):
            return
        if self._reflection_store is None:
            return
        try:
            entry = ReflectionEntry(
                task_summary=user_input[:200],
                scores=reflection.get("scores", {}) or {},
                feedback=reflection.get("feedback", "") or "",
                action_plan=reflection.get("action_plan", "") or "",
                strategy_hint=reflection.get("strategy_hint", "") or "",
                tool_history=[t.get("tool", "") for t in (tool_history or [])[-10:]],
            )
            self._reflection_store.add_reflection(entry)
        except Exception:
            pass

    async def _search_relevant_reflections(self, user_input: str, top_k: int = 3) -> List[str]:
        """Get relevant past reflections as plain-text snippets."""
        if not get_reflection_store or not hasattr(self, "_reflection_store"):
            return []
        if self._reflection_store is None:
            return []
        try:
            entries = self._reflection_store.search_relevant(user_input, top_k=top_k)
            snippets = []
            for entry in entries:
                parts = [
                    entry.feedback.strip(),
                    entry.action_plan.strip(),
                    entry.strategy_hint.strip(),
                ]
                body = " -> ".join(part for part in parts if part)
                if body:
                    snippets.append(f"[{entry.task_summary[:50]}] {body}")
            return snippets
        except Exception:
            return []

    # ── Streaming helpers ────────────────────────────────────────────────    # ── Streaming helpers ───────────────────────────────────────────────
    @staticmethod
    def _parse_tool_params(arguments: str) -> dict:
        try:
            return json.loads(arguments) if arguments else {}
        except Exception:
            return {}

    # ── Main loop (AsyncGenerator of SSE events) ────────────────────────
    async def run(
        self,
        messages: List[dict],
        user_input: str,
        initial_state: Optional[dict] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Run the ReAct + Reflexion loop using native LLM tool calls.

        `messages` MUST already include the system prompt at index 0 and any
        conversation history. The new user message is the last entry.

        Yields dicts; see module docstring for the schema.
        """
        tool_history: List[dict] = []
        reflections: List[str] = []
        step = 0
        total_iter = 0
        last_answer: Optional[str] = None
        
        # Restore initial state if resuming from interrupt
        if initial_state:
            tool_history = list(initial_state.get('tool_history', []))
            reflections = list(initial_state.get('reflections', []))
            step = initial_state.get('step', 0)
            total_iter = step

        # Some reasoning models (e.g. MiniMax-M3) emit their CoT inline as
        # <think>...</think> blocks within the content field. The closing tag
        # may be split across multiple chunks, so we use a stateful parser
        # that buffers partial tags across calls.
        import re as _re_split

        class _ThinkParser:
            """Splits <think>...</think> blocks from streamed content chunks.

            The model may emit ``<think>`` and ``</think>`` in different chunks
            (or even character by character). This class buffers the partial
            state and produces clean (visible, hidden) pairs per chunk.
            """
            _OPEN = "<think>"
            _CLOSE = "</think>"

            def __init__(self):
                self._buf = ""           # pending fragment after a partial <think>
                self._in_think = False   # currently inside a <think> block
                self._hidden = ""        # accumulated hidden text

            def feed(self, text):
                """Return (visible, hidden_new) for this chunk."""
                if not text:
                    return "", ""
                visible_parts = []
                hidden_new = ""
                i = 0
                while i < len(text):
                    if self._in_think:
                        # Looking for </think>
                        close_idx = text.find(self._CLOSE, i)
                        if close_idx < 0:
                            self._hidden += text[i:]
                            break
                        self._hidden += text[i:close_idx]
                        self._in_think = False
                        i = close_idx + len(self._CLOSE)
                        # Add a separator between consecutive think blocks
                        if self._hidden and not self._hidden.endswith("\n"):
                            self._hidden += "\n"
                    else:
                        # Looking for <think>
                        open_idx = text.find(self._OPEN, i)
                        if open_idx < 0:
                            visible_parts.append(text[i:])
                            break
                        visible_parts.append(text[i:open_idx])
                        self._in_think = True
                        i = open_idx + len(self._OPEN)
                hidden_new = self._drain_hidden()
                return "".join(visible_parts), hidden_new

            def _drain_hidden(self):
                h = self._hidden
                self._hidden = ""
                return h

        _think_parser = _ThinkParser()

        def _split_think(text):
            return _think_parser.feed(text)

        simple_response_mode = self._looks_like_simple_response(user_input)
        startup_reflections: List[str] = []
        if not initial_state and not simple_response_mode:
            startup_reflections = await self._search_relevant_reflections(user_input, top_k=3)
            if startup_reflections:
                memory_block = (
                    "Your previous self-reflections for similar tasks:\n"
                    + "\n".join(f"- {item}" for item in startup_reflections)
                    + "\nUse these lessons before deciding whether to call tools."
                )
                insert_at = 1 if messages and messages[0].get("role") == "system" else 0
                messages.insert(insert_at, {"role": "system", "content": memory_block})
                yield {
                    "type": "reflection",
                    "data": {
                        "step": 0,
                        "n": 0,
                        "agent": "review",
                        "agent_name": "审核 Agent",
                        "transition": "已识别到可复用的历史经验，接下来由审核 Agent 调整本轮执行策略。",
                        "content": "已读取与本轮相关的历史经验，用于调整执行策略。",
                        "overall": "MEMORY",
                        "action_plan": "",
                        "strategy_hint": "",
                    },
                }

        direct_answer_mode = (
            not initial_state
            and self._looks_like_direct_explanation(user_input)
            and (
                not startup_reflections
                or self._reflection_suggests_direct_answer(startup_reflections)
            )
        )
        if direct_answer_mode:
            if simple_response_mode:
                direct_policy = (
                    "Execution policy for this turn: answer directly without tool calls. "
                    "For capability questions, describe only capabilities that this system actually has: "
                    "knowledge-grounded explanations, learning assistance, web search and page reading, "
                    "short sandboxed code execution, explicitly requested sandbox file operations, "
                    "date/time lookup, and calculation. Do not claim reminders, email, background jobs, "
                    "or other unavailable functions. For greetings, respond naturally and briefly."
                )
            else:
                direct_policy = (
                    "Execution policy for this turn: answer directly without tools. "
                    "The user is asking for an explanation or worked example, not live data. "
                    "Do not call knowledge_search, url_fetch, code_exec, or other tools. "
                    "Provide a concrete, step-by-step explanation in the final answer."
                )
            messages.insert(1 if messages and messages[0].get("role") == "system" else 0, {
                "role": "system",
                "content": direct_policy,
            })
            if not simple_response_mode:
                yield {
                    "type": "reflection",
                    "data": {
                        "step": 0,
                        "n": 0,
                        "agent": "policy",
                        "agent_name": "响应策略",
                        "transition": "任务类型已经确认，接下来选择直接讲解还是借助工具完成。",
                        "content": "本轮为直接讲解任务，无需调用工具。",
                        "overall": "MEMORY" if startup_reflections else "POLICY",
                        "action_plan": "",
                        "strategy_hint": "解释类问题优先直接给出清晰示例，避免无关工具调用。",
                    },
                }

        blocked_tool_names: set[str] = set()
        while total_iter < self.max_iterations:
            total_iter += 1
            step += 1

            # ── Check for interruption before LLM call ──
            if self.interrupt_event and self.interrupt_event.is_set():
                yield {'type': 'interrupted', 'data': {'step': step, 'reason': 'user requested'}}
                return


            # ── 1. LLM call (streaming) ──
            content_buffer = ""
            thinking_buffer = ""
            tool_call_chunks: Dict[int, Dict[str, Any]] = {}
            finish_reason: Optional[str] = None

            stream_gen = None
            try:
                prior_tool_counts: Dict[str, int] = {}
                for history_item in tool_history:
                    history_name = str(history_item.get("tool") or "")
                    prior_tool_counts[history_name] = prior_tool_counts.get(history_name, 0) + 1
                available_tools = [
                    definition for definition in self.tool_definitions
                    if definition.get("function", {}).get("name") not in blocked_tool_names
                    and prior_tool_counts.get(definition.get("function", {}).get("name", ""), 0) < 2
                ]
                stream_gen = llm_service.call_model_with_tools(
                    messages=messages,
                    tools=[] if direct_answer_mode else available_tools,
                    model=self.model,
                    stream=True,
                    max_tokens=8000,  # 降低以抑制过度推理
                )

                async for chunk in self._iterate_interruptibly(stream_gen):
                    ctype = chunk.get("type")
                    if ctype == "content":
                        raw = chunk.get("content", "")
                        visible, hidden = _split_think(raw)
                        if hidden:
                            thinking_buffer += hidden + "\n"
                        if visible:
                            content_buffer += visible
                    elif ctype == "reasoning":
                        thinking_buffer += chunk.get("content", "")
                    elif ctype == "tool_call":
                        idx = chunk.get("index", 0)
                        entry = tool_call_chunks.setdefault(
                            idx,
                            {
                                "id": chunk.get("tool_call_id") or "",
                                "name": "",
                                "arguments": "",
                            },
                        )
                        if chunk.get("tool_call_id"):
                            entry["id"] = chunk["tool_call_id"]
                        name = (chunk.get("function") or {}).get("name")
                        if name:
                            entry["name"] = name
                        args = (chunk.get("function") or {}).get("arguments")
                        if args:
                            entry["arguments"] += args
                    elif ctype == "done":
                        finish_reason = chunk.get("finish_reason")
                        break

            except AgentInterrupted:
                yield {"type": "interrupted", "data": {"step": step, "reason": "user requested"}}
                return
            except Exception as e:
                yield {"type": "error", "data": {"message": str(e), "step": step}}
                return
            finally:
                if stream_gen is not None and hasattr(stream_gen, "aclose"):
                    try:
                        await stream_gen.aclose()
                    except Exception:
                        pass

            tool_calls_list = [
                {
                    "id": entry["id"] or f"call_{idx}",
                    "function": {
                        "name": entry["name"],
                        "arguments": entry["arguments"],
                    },
                }
                for idx, entry in sorted(tool_call_chunks.items())
                if entry["name"]
            ]
            rejected_tool_calls = 0
            if tool_calls_list:
                prior_counts: Dict[str, int] = {}
                prior_signatures = set()
                for item in tool_history:
                    name = str(item.get("tool") or "")
                    prior_counts[name] = prior_counts.get(name, 0) + 1
                    prior_signatures.add(
                        f"{name}:{json.dumps(item.get('params') or {}, ensure_ascii=False, sort_keys=True)}"
                    )
                accepted_calls = []
                batch_counts: Dict[str, int] = {}
                batch_signatures = set()
                for tc in tool_calls_list:
                    name = tc["function"]["name"]
                    params = self._parse_tool_params(tc["function"]["arguments"])
                    signature = f"{name}:{json.dumps(params or {}, ensure_ascii=False, sort_keys=True)}"
                    used = prior_counts.get(name, 0) + batch_counts.get(name, 0)
                    if used >= 2 or signature in prior_signatures or signature in batch_signatures:
                        rejected_tool_calls += 1
                        blocked_tool_names.add(name)
                        continue
                    accepted_calls.append(tc)
                    batch_counts[name] = batch_counts.get(name, 0) + 1
                    batch_signatures.add(signature)
                tool_calls_list = accepted_calls
                if rejected_tool_calls and not tool_calls_list:
                    messages.append({
                        "role": "system",
                        "content": "工具调用额度已用完。请立即基于已有结果完成回答，不要继续调用工具。",
                    })
                    continue

            # If we collected inline thinking during streaming, surface it as a
            # dedicated thinking event. We combine the streamed hidden text with
            # any visible content that appeared BEFORE the first tool call (which
            # is usually the model's CoT for the next action).
            thinking_text = (content_buffer or "").strip()
            if thinking_buffer.strip():
                thinking_text = (thinking_buffer.strip() + "\n" + thinking_text).strip()

            # ── 3. Tool calls ──
            if tool_calls_list:
                # Record the assistant message that issued the tool calls.
                assistant_tool_message = {
                    "role": "assistant",
                    "content": content_buffer,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            },
                        }
                        for tc in tool_calls_list
                    ],
                }
                if thinking_buffer.strip():
                    assistant_tool_message["reasoning_content"] = thinking_buffer
                messages.append(assistant_tool_message)

                ask_question: Optional[str] = None

                # ── 3a. Emit thinking FIRST (buffered), then all action events ──
                # This ensures thinking appears before actions in the SSE stream,
                # so the Renderer can group them correctly per step.
                if thinking_text:
                    yield {
                        "type": "thinking",
                        "data": {
                            "step": step,
                            "agent": "generation",
                            "agent_name": "生成 Agent",
                            "transition": (
                                "已有工具结果可供使用，接下来由生成 Agent 判断是否还需补充信息。"
                                if tool_history else
                                "任务路径已经确定，接下来由生成 Agent 组织回答并判断是否需要工具。"
                            ),
                            "content": thinking_text,
                            "is_final_draft": False,
                        },
                    }

                for tc in tool_calls_list:
                    tool_name = tc["function"]["name"]
                    params = self._parse_tool_params(tc["function"]["arguments"])
                    yield {
                        "type": "action",
                        "data": {
                            "step": step,
                            "tool": tool_name,
                            "params": params,
                            "transition": _tool_transition(
                                tool_name,
                                has_prior_results=bool(tool_history),
                            ),
                        },
                    }

                # ── 3b. Execute all tools in parallel ──
                async def _exec_one(tc: dict):
                    tool_name = tc["function"]["name"]
                    params = self._parse_tool_params(tc["function"]["arguments"])
                    result = await self._execute_tool(tool_name, params)
                    formatted = self.format_result(tool_name, result)
                    success = (
                        bool(result.get("success", True))
                        if isinstance(result, dict) and not result.get("_ask")
                        else True
                    )
                    return tc, tool_name, params, result, formatted, success

                try:
                    results = await self._await_interruptibly(asyncio.gather(
                        *[_exec_one(tc) for tc in tool_calls_list],
                        return_exceptions=True,
                    ))
                except AgentInterrupted:
                    yield {"type": "interrupted", "data": {"step": step, "reason": "user requested"}}
                    return

                # ── 3c. Process results in order, emit observations ──
                for i, res in enumerate(results):
                    if isinstance(res, Exception):
                        tc = tool_calls_list[i]
                        tool_name = tc["function"]["name"]
                        params = self._parse_tool_params(tc["function"]["arguments"])
                        result = {"success": False, "error": str(res)}
                        formatted = self.format_result(tool_name, result)
                        success = False
                    else:
                        tc, tool_name, params, result, formatted, success = res

                    yield {
                        "type": "observation",
                        "data": {
                            "step": step,
                            "tool": tool_name,
                            "success": success,
                            "formatted": formatted,
                            "raw": _truncate_result(result),
                        },
                    }

                    tool_history.append({
                        "tool": tool_name,
                        "params": params,
                        "result": result,
                    })

                    # Append raw result for the LLM context (truncated to save tokens).
                    truncated = _truncate_result(result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": json.dumps(truncated, ensure_ascii=False),
                    })

                    if isinstance(result, dict) and result.get("_ask"):
                        ask_question = result.get("question", "")
                        break

                if rejected_tool_calls:
                    messages.append({
                        "role": "system",
                        "content": "部分重复或超额工具调用已省略。请基于本轮已有结果完成回答。",
                    })

                if ask_question is not None:
                    yield {"type": "ask", "data": {"content": ask_question}}
                    yield {
                        "type": "done",
                        "data": {
                            "step": step,
                            "tools": [{"tool": t["tool"], "params": t["params"]} for t in tool_history],
                            "reflections": len(reflections),
                            "answer": ask_question,
                        },
                    }
                    return

                # Check for interruption after tool execution
                if self.interrupt_event and self.interrupt_event.is_set():
                    yield {"type": "interrupted", "data": {"step": step, "reason": "user requested"}}
                    yield {"type": "done", "data": {"step": step, "tools": [{"tool": t["tool"], "params": t["params"]} for t in tool_history], "reflections": len(reflections), "answer": "", "interrupted": True}}
                    return
                
                continue

            # ── 4. Final answer (with conditional Reflexion) ──
            answer = content_buffer.strip()
            if not answer:
                yield {
                    "type": "done",
                    "data": {
                        "step": step,
                        "tools": [{"tool": t["tool"], "params": t["params"]} for t in tool_history],
                        "reflections": len(reflections),
                        "answer": last_answer or "",
                        "error": "model returned an empty answer",
                    },
                }
                return

            answer = self._augment_answer_for_code_tasks(answer, tool_history)
            last_answer = answer

            # ── Smart reflection trigger ──
            # Skip reflection if:
            # 1. no tool calls at all (pure reasoning, no ground needed)
            # 2. tool coverage is low AND answer is short (likely already concise)
            # 3. Already did max_reflections
            should_reflect = (
                self.enable_reflection
                and len(reflections) < self.max_reflections
            )
            if should_reflect:
                tool_count = len(tool_history)
                # If we barely used any tools (< 2) and answer is short,
                # reflection is unlikely to help much — skip it
                if tool_count == 0 and len(answer) < 200:
                    should_reflect = False

            if should_reflect:
                relevant_past = await self._search_relevant_reflections(user_input, top_k=3)
                reflection = await self.reflect(
                    user_input, answer, tool_history, reflections,
                    relevant_past=relevant_past,
                )
                await self._save_reflection(user_input, answer, tool_history, reflection)

                if reflection["overall"] == "PASS":
                    reflection_text = reflection["feedback"] or "Self-check passed."
                    reflections.append(reflection_text)
                    yield {
                        "type": "reflection",
                        "data": {
                            "step": step,
                            "n": len(reflections),
                            "agent": "review",
                            "agent_name": "审核 Agent",
                            "transition": "回答草稿已经形成，接下来由审核 Agent 检查事实依据、完整性和直接性。",
                            "content": reflection_text,
                            "scores": reflection["scores"],
                            "overall": reflection["overall"],
                            "action_plan": reflection["action_plan"],
                            "strategy_hint": reflection["strategy_hint"],
                        },
                    }
                    yield {"type": "finish", "content": answer}
                    yield {
                        "type": "done",
                        "data": {
                            "step": step,
                            "tools": [{"tool": t["tool"], "params": t["params"]} for t in tool_history],
                            "reflections": len(reflections),
                            "answer": answer,
                            "reflection_scores": reflection["scores"],
                        },
                    }
                    return

                reflection_text = reflection["feedback"]
                if reflection["action_plan"]:
                    reflection_text += f" | 行动计划: {reflection['action_plan']}"
                reflections.append(reflection_text)

                yield {
                    "type": "reflection",
                    "data": {
                        "step": step,
                        "n": len(reflections),
                        "agent": "review",
                        "agent_name": "审核 Agent",
                        "transition": "回答草稿已经形成，接下来由审核 Agent 定位仍需修正的内容。",
                        "content": reflection_text,
                        "scores": reflection["scores"],
                        "overall": reflection["overall"],
                        "action_plan": reflection["action_plan"],
                        "strategy_hint": reflection["strategy_hint"],
                    },
                }

                pending_action = self._execute_action_plan(reflection["action_plan"])
                if pending_action and pending_action["tool"] in self._tool_name_set:
                    tool_name = pending_action["tool"]
                    params = pending_action["params"]
                    auto_call_id = f"auto_{step}"
                    yield {
                        "type": "action",
                        "data": {
                            "step": step,
                            "tool": tool_name,
                            "params": params,
                            "auto": True,
                            "transition": _tool_transition(tool_name, corrective=True),
                        },
                    }
                    result = await self._execute_tool(tool_name, params)
                    formatted = self.format_result(tool_name, result)
                    success = (
                        bool(result.get("success", True))
                        if isinstance(result, dict) and not result.get("_ask")
                        else True
                    )
                    yield {
                        "type": "observation",
                        "data": {
                            "step": step,
                            "tool": tool_name,
                            "success": success,
                            "formatted": formatted,
                            "auto": True,
                        },
                    }
                    tool_history.append({
                        "tool": tool_name,
                        "params": params,
                        "result": result,
                    })
                    import json as _json
                    truncated = _truncate_result(result)
                    messages.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": auto_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": _json.dumps(params, ensure_ascii=False),
                            },
                        }],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": auto_call_id,
                        "name": tool_name,
                        "content": _json.dumps(truncated, ensure_ascii=False),
                    })
                    continue


            # No tool calls - this is a final-answer step: emit thinking first
            if thinking_text:
                yield {
                    "type": "thinking",
                    "data": {
                        "step": step,
                        "agent": "generation",
                        "agent_name": "生成 Agent",
                        "transition": "所需信息已经准备完成，接下来由生成 Agent 整理最终回答。",
                        "content": thinking_text,
                        "is_final_draft": True,
                    },
                }

            yield {"type": "finish", "content": answer}
            yield {
                "type": "done",
                "data": {
                    "step": step,
                    "tools": [{"tool": t["tool"], "params": t["params"]} for t in tool_history],
                    "reflections": len(reflections),
                    "answer": answer,
                },
            }
            return

        # Fell through: max iterations
        # Reserve one tool-free recovery call so a run that spent its normal
        # iterations on retrieval/reflection still produces a user-facing answer.
        recovery_results = json.dumps(
            [
                {
                    "tool": item.get("tool"),
                    "params": item.get("params"),
                    "result": _truncate_result(item.get("result")),
                }
                for item in tool_history
            ],
            ensure_ascii=False,
        )[:16000]
        recovery_messages = [
            {
                "role": "system",
                "content": (
                    "你是最终答案编辑器，没有任何可调用工具。只根据提供的执行结果回答用户。"
                    "禁止输出 tool_calls、DSML、XML 调用标记或再次请求工具；"
                    "不得虚构执行结果中不存在的事实。"
                ),
            },
            {
                "role": "user",
                "content": f"用户问题：{user_input}\n\n已有工具执行结果：\n{recovery_results}\n\n请直接给出最终答案。",
            },
        ]
        recovery_answer = ""
        recovery_stream = None
        try:
            recovery_stream = llm_service.call_model_with_tools(
                messages=recovery_messages,
                tools=[],
                model=self.model,
                stream=True,
                max_tokens=8000,
            )
            async for chunk in self._iterate_interruptibly(recovery_stream):
                if chunk.get("type") == "content":
                    visible, _ = _split_think(chunk.get("content", ""))
                    recovery_answer += visible
                elif chunk.get("type") == "done":
                    break
        except AgentInterrupted:
            yield {"type": "interrupted", "data": {"step": step, "reason": "user requested"}}
            return
        except Exception:
            recovery_answer = ""
        finally:
            if recovery_stream is not None and hasattr(recovery_stream, "aclose"):
                try:
                    await recovery_stream.aclose()
                except Exception:
                    pass

        recovery_answer = recovery_answer.strip()
        leaked_tool_protocol = any(marker in recovery_answer for marker in (
            "DSML", "tool_calls", "<invoke", "<｜tool", "<|tool",
        ))
        if recovery_answer and not leaked_tool_protocol:
            recovery_answer = self._augment_answer_for_code_tasks(recovery_answer, tool_history)
            yield {"type": "finish", "content": recovery_answer}
            yield {
                "type": "done",
                "data": {
                    "step": step,
                    "tools": [{"tool": t["tool"], "params": t["params"]} for t in tool_history],
                    "reflections": len(reflections),
                    "answer": recovery_answer,
                    "recovered_after_max_iterations": True,
                },
            }
            return

        yield {
            "type": "done",
            "data": {
                "step": step,
                "tools": [{"tool": t["tool"], "params": t["params"]} for t in tool_history],
                "reflections": len(reflections),
                "answer": last_answer or "task incomplete",
                "error": "max iterations reached",
            },
        }
