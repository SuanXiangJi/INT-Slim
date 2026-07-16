"""
XBot · Autonomous Agent · v5.0
==============================

Claude Code 美学 + Reflexion 论文对齐的终端智能体。

能力
----
- ReAct 循环: think -> action -> observation -> (reflect -> retry) -> finish
- url_fetch 用 LLM 围绕 focus 提炼页面, 输出真正有价值的内容
- Reflexion 自我反思（4 维评估: hallucination / verification / completeness / relevance）
  + episodic memory 累积（每轮自省会注入下一次尝试的上下文）
- 增强终端 UI: Claude Code 美学, 一致的缩进层级, 全部强制 flush

单一事实源: 本文件复用 backend 的 AutonomousAgent（CLI 只渲染, 不重复决策逻辑）
避免 CLI / Web 行为漂移; 任何 backend 改动都会在 CLI 中同步体现。

运行: python test/cli.py
输入: 自然语言问题, 或命令（help / clear / model <id> / history / quit）
"""

from __future__ import annotations

import os
import sys
import json
import re
import signal
import asyncio
import textwrap
import shutil
import threading
import itertools
from typing import Any, Dict, List

# ─── 注入 backend 路径 ─────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.abspath(os.path.join(_HERE, "..", "backend"))
sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)

from app.services.autonomous_agent import AutonomousAgent
from app.services.llm_service import llm_service
from app.skills.web_search_skill import WebSearchSkill
from app.skills.url_fetch_skill import UrlFetchSkill, set_tool_llm_model
from app.skills.code_exec_skill import CodeExecSkill
from app.services.user_profile import UserProfileService, UserProfile
from app.services.user_profile_file_store import FileProfileStore


# ═══ ANSI 颜色（极简、低饱和、贴近 Claude Code）══════════════════════════════
def G(t): return "\033[32m" + t + "\033[0m"        # success / answer
def R(t): return "\033[31m" + t + "\033[0m"        # error
def Y(t): return "\033[33m" + t + "\033[0m"        # ask / reflection / warning
def B(t): return "\033[34m" + t + "\033[0m"        # tool name
def M(t): return "\033[35m" + t + "\033[0m"        # thinking
def C(t): return "\033[36m" + t + "\033[0m"        # user prompt / accent
def K(t): return "\033[90m" + t + "\033[0m"        # dim / meta
def X(t): return "\033[1m"  + t + "\033[0m"        # bold
def DIM(t): return "\033[2m" + t + "\033[0m"       # dimmer
def IT(t): return "\033[3m" + t + "\033[0m"        # italic / soft


# ═══ Terminal 布局 ════════════════════════════════════════════════════════
TERM_W = shutil.get_terminal_size((100, 24)).columns
PANEL_W = min(max(TERM_W, 70), 110)


def hr(char: str = "\u2500") -> str:
    return K(char * PANEL_W)


def wrap_text(text: str, indent: str = "    ", width: int = 0) -> str:
    """按段落折叠长文本, 保留显式换行."""
    if not text:
        return ""
    width = width or max(20, PANEL_W - len(indent))
    out: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            out.append(indent.rstrip())
            continue
        try:
            wrapped = textwrap.fill(
                paragraph, width=width,
                initial_indent=indent, subsequent_indent=indent,
                replace_whitespace=True, break_long_words=False,
            )
        except Exception:
            wrapped = indent + paragraph
        out.append(wrapped)
    return "\n".join(out)


def short_params(params: Dict[str, Any], limit: int = 140) -> str:
    try:
        s = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        s = str(params)
    return s if len(s) <= limit else s[:limit] + "\u2026"


# ═══ Spinner（轻量、占位、不留残余字符）═════════════════════════════════════
class Spinner:
    """行内 ASCII spinner. 用 with 语句包裹一段"等待"代码."""
    FRAMES = ["\u280b", "\u2819", "\u2839", "\u2838", "\u283c",
              "\u2834", "\u2826", "\u2827", "\u2807", "\u280f"]

    def __init__(self, label: str, color=lambda s: s):
        self.label = label
        self.color = color
        self._stop = threading.Event()
        self._thread = None  # type: ignore

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        try:
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()
        except Exception:
            pass

    def _run(self):
        for frame in itertools.cycle(self.FRAMES):
            try:
                sys.stdout.write(
                    "\r  " + self.color(frame) + " " + self.color(self.label)
                )
                sys.stdout.flush()
            except Exception:
                return
            if self._stop.wait(0.08):
                break



# ═══ 工具元数据（喂给 LLM）══════════════════════════════════════════════════
def _tool_definitions() -> List[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the public web for a query and get a list of "
                    "results (title, url, snippet). Use when you need "
                    "up-to-date or external facts."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string",
                                  "description": "Search query"},
                        "limit": {"type": "integer", "default": 5,
                                  "description": "Max results (default 5)"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "url_fetch",
                "description": (
                    "Fetch a single URL and LLM-summarize the page around a "
                    "concrete focus. Use when you have a specific URL and "
                    "need page-grounded facts (without forcing the user to "
                    "read the page). ALWAYS pass a concrete `focus` like "
                    "'pricing', 'release date', 'architecture' or 'funding "
                    "history' — NOT generic 'main content'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string",
                                "description": "Target URL"},
                        "focus": {"type": "string",
                                  "description": "Concrete extraction angle",
                                  "default": "主要内容"},
                        "max_length": {"type": "integer", "default": 12000,
                                       "description": "Raw text cap before LLM"},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "code_exec",
                "description": (
                    "Run a short Python snippet in a sandbox; returns "
                    "stdout and stderr. Use for quick numeric / algorithmic "
                    "work; not for long-running jobs."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string",
                                 "description": "Python source code"},
                    },
                    "required": ["code"],
                },
            },
        },
    ]




# ═════════════════════════ User profile (per-host, file-backed) ════════════════════════════
# CLI stores its profile at ~/.xbots/<os_user>/profile.json (one profile per host user).
_profile_store = FileProfileStore()
_profile_service = UserProfileService(_profile_store, llm_service=llm_service,
                                  model="deepseek:deepseek-chat")


async def cli_tool_executor(name: str, params: dict) -> dict:
    """把 tool 调用路由到具体的 Skill 实现（无 db / sandbox 上下文）."""
    try:
        if name == "web_search":
            return await WebSearchSkill().execute({
                "query": (params.get("query") or "").strip(),
                "limit": int(params.get("limit") or 5),
            }, None)

        if name == "url_fetch":
            return await UrlFetchSkill().execute({
                "url": (params.get("url") or "").strip(),
                "focus": (params.get("focus") or "主要内容").strip(),
                "max_length": int(params.get("max_length") or 12000),
            }, None)

        if name == "code_exec":
            return await CodeExecSkill().execute(
                {"code": params.get("code", "")}, None)

        return {"success": False, "error": f"unknown tool: {name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}



# ═══ Renderer（事件 -> 终端; 不重排决策）═════════════════════════════════════
class AgentRenderer:
    """把 autonomous-agent 的事件流渲染到终端.

    设计原则:
    - 每个事件只调用 print; 不做光标移动 / 行删除（兼容性差）
    - thinking / action / observation / reflection / answer 用统一的 4-space 缩进
    - 模型输出靠 "\n" 起新行, 不靠位置覆写（避免 ANSI 假阴性)
    - 全部 flush=True（防止 stdout 缓冲导致输出"卡住" = 用户感知的"不完整"）
    """

    def __init__(self):
        self.steps = 0
        self.tool_count = 0
        self.reflect_count = 0
        self.last_kind: str = ""
        self.model: str = ""

    def set_model(self, model: str):
        self.model = model

    # ── 入口（供 autonomous-agent 回调） ──
    def handle(self, event: Dict[str, Any]):
        kind = event.get("type")
        if kind == "thinking":
            self._thinking(event.get("data") or {})
        elif kind == "action":
            self._action(event.get("data") or {})
        elif kind == "observation":
            self._observation(event.get("data") or {})
        elif kind == "reflection":
            self._reflection(event.get("data") or {})
        elif kind == "finish":
            self._finish(event.get("content", "") or "")
        elif kind == "ask":
            self._ask(event.get("content", "") or "")
        elif kind == "done":
            self._done(event.get("data") or {})
        elif kind == "error":
            self._error(event.get("data") or {})
        try:
            sys.stdout.flush()
        except Exception:
            pass
        self.last_kind = kind or ""

    # ── 内部渲染 ──
    def _blank_line(self):
        print(flush=True)

    def _thinking(self, data: dict):
        content = (data.get("content") or "").strip()
        if not content:
            return
        self.steps += 1
        self._blank_line()
        print(f"  {M(chr(0x273b))} {M(X(chr(0x2009) + 'thinking'))}", flush=True)
        print(wrap_text(content, indent="    "), flush=True)

    def _action(self, data: dict):
        tool = data.get("tool") or "?"
        params = data.get("params") or {}
        self.tool_count += 1
        self._blank_line()
        icon = chr(0x25cf)
        print(f"  {B(icon)} {B(X(tool))}  {K(short_params(params))}", flush=True)

    def _observation(self, data: dict):
        success = bool(data.get("success", True))
        formatted = (data.get("formatted") or "").rstrip()
        if not formatted:
            tool = data.get("tool") or "?"
            mark = G(chr(0x2713)) if success else R(chr(0x2717))
            print(f"  {mark} {K(tool)}", flush=True)
            return
        # format_result 已带 2/5-space 缩进; 这里下沉到 5-space 与 action 对齐
        lines = formatted.split("\n")
        print("     " + lines[0].lstrip(), flush=True)
        for ln in lines[1:]:
            if not ln.strip():
                print(flush=True)
                continue
            print("     " + ln.lstrip(), flush=True)

    def _reflection(self, data: dict):
        n = int(data.get("n") or 0)
        content = (data.get("content") or "").strip()
        if not content:
            return
        self.reflect_count = max(self.reflect_count, n)
        self._blank_line()
        icon = chr(0x25c6)
        print(f"  {Y(icon)} {Y(X('reflection #' + str(n)))}", flush=True)
        print(wrap_text(content, indent="    "), flush=True)

    def _finish(self, content: str):
        if not content.strip():
            return
        self._blank_line()
        icon = chr(0x2726)
        print(f"  {G(icon)} {G(X(chr(0x2009) + 'answer'))}", flush=True)
        print(flush=True)
        for ln in content.split("\n"):
            if not ln.strip():
                print(flush=True)
                continue
            print(wrap_text(ln, indent="  "), flush=True)

    def _ask(self, content: str):
        if not content.strip():
            return
        self._blank_line()
        print(f"  {Y(chr(0x003f))} {Y(IT(content))}", flush=True)

    def _done(self, data: dict):
        # summary stats line + 分隔线
        tools = data.get("tools") or []
        steps = data.get("step", self.steps) or self.steps
        ref = f" · {chr(0x21bb)} {self.reflect_count} reflection" if self.reflect_count else ""
        model_str = self.model
        print(flush=True)
        print(hr(), flush=True)
        suffix = f" · {model_str}" if model_str else ""
        print(f"  {K(str(steps) + ' steps · ' + str(len(tools)) + ' tools' + ref + suffix)}", flush=True)

    def _error(self, data: dict):
        msg = data.get("message") or "unknown error"
        print(flush=True)
        print(f"  {R(chr(0x2717))} {R(msg)}", flush=True)



# ═══ 一轮对话（CLI 视角）══════════════════════════════════════════════════
async def run_one(user_input: str, history: List[dict],
                  model: str, renderer: AgentRenderer) -> None:
    """跑一轮 ReAct + (可选) Reflexion; 事件流由 renderer 渲染."""
    reset_pause()
    # 让 url_fetch 的内部 LLM 调用使用与 agent 一致的模型
    set_tool_llm_model(model)
    renderer.set_model(model)

    agent = AutonomousAgent(
        model=model,
        enable_reflection=True,
        max_reflections=2,
        max_iterations=14,
        tool_definitions=_tool_definitions(),
        tool_executor=cli_tool_executor,
    )

    # Inject user profile context into system prompt (per-host portrait)
    profile_ctx = _profile_service.build_context_string()
    base_system = agent.system_prompt()
    if profile_ctx:
        system_content = (base_system
                         + "\n\n## User profile (use this to personalise responses)\n"
                         + profile_ctx)
    else:
        system_content = base_system
    msgs: List[dict] = [{"role": "system", "content": system_content}]
    for m in history:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": user_input})

    final_answer = ""
    stopped = False
    try:
        async for event in agent.run(msgs, user_input=user_input):
            renderer.handle(event)
            # Capture the final answer so we can queue profile analysis after
            if event.get("type") == "finish":
                final_answer = event.get("content", "") or ""
            # Yield to the event loop so any pending pause request is visible.
            await asyncio.sleep(0)
            if _pause_event.is_set():
                stopped = True
                break
    except asyncio.CancelledError:
        stopped = True
        raise
    except KeyboardInterrupt:
        stopped = True
    except Exception as e:
        # Surface upstream errors but don't crash the loop.
        print(R(f"\n  ⏸  agent error: {e}"), flush=True)
        stopped = True

    if stopped:
        print(R("  ⏸  paused"), flush=True)
        return

    # Fire-and-forget async profile analysis (does NOT block the response)
    if final_answer and final_answer.strip():
        try:
            recent = [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": final_answer},
            ]
            asyncio.create_task(_profile_service.analyze_and_update(recent))
        except Exception:
            pass


# ═══ 帮助文本 + 主循环 ══════════════════════════════════════════════════════
HELP_TEXT = (
    "\n"
    "XBot autonomous agent - 命令与运行说明\n"
    "------------------------------------\n"
    "\n"
    "  直接输入任务     agent 自动规划 -> 调用工具 -> 自我反思 -> 给出最终答案\n"
    "\n"
    "  命令:\n"
    "    help              显示此帮助\n"
    "    clear             清空当前会话历史\n"
    "    history           查看历史累积大小\n"
    "    model <id>        切换模型   示例: model minimax:m3\n"
    "    profile ...       用户画像子命令 (show / analyze / on / off / reset / path)\n"
    "    quit / exit       退出\n"
    "\n"
    "  暂停:\n"
    "    Ctrl-C            立刻中断当前 agent 的运行\n"
    "    pause / stop      立即暂停（与 Ctrl-C 等价）\n"
    "\n"
    "  运行中你会看到:\n"
    "    star  thinking          agent 的思考（每一步要做什么 + 为什么）\n"
    "    dot   action            调用某个工具\n"
    "    v     observation       工具返回\n"
    "    diamond reflection #N   agent 自我反思（不合格时触发, 会注入下一次尝试）\n"
    "    star  answer            最终答案\n"
    "\n"
    "  默认关闭 Reflexion 才能调试工具调用; 保留 ON 适合生产。\n"
)





def _handle_profile_command(rest: str) -> None:
    """profile sub-commands: show / analyze / reset / on / off / path"""
    rest = (rest or "").strip().lower()
    profile = _profile_service.get_or_create()

    if rest in ("", "show"):
        print(flush=True)
        print(f"  {X(chr(0x2130))} user profile   {K(chr(0x2014) + chr(0x2009) + _profile_store.path)}", flush=True)
        if profile.display_name:
            print(f"    {K(chr(0x2022))} display_name: {profile.display_name}", flush=True)
        if profile.profession:
            print(f"    {K(chr(0x2022))} profession:   {profile.profession}", flush=True)
        if profile.location:
            print(f"    {K(chr(0x2022))} location:     {profile.location}", flush=True)
        print(f"    {K(chr(0x2022))} language:     {profile.language_preference}", flush=True)
        print(f"    {K(chr(0x2022))} auto-update:  {profile.auto_update_enabled}", flush=True)
        last_at = profile.last_analyzed_at or chr(0x2014)
        print(f"    {K(chr(0x2022))} analysed:     {profile.analyzed_msg_count} msgs, last at {last_at}", flush=True)
        if profile.interests:
            print(f"    {K(chr(0x2022))} interests:    {chr(0x2009).join(profile.interests[:12])}", flush=True)
        if profile.expertise:
            levels = {k: v for k, v in list(profile.expertise.items())[:8]}
            print(f"    {K(chr(0x2022))} expertise:    {levels}", flush=True)
        if profile.preferences:
            print(f"    {K(chr(0x2022))} preferences:  {profile.preferences}", flush=True)
        if profile.portrait_summary:
            print(f"    {K(chr(0x2022))} portrait:     {IT(profile.portrait_summary[:200])}", flush=True)
        return

    if rest == "reset":
        _profile_service.reset()
        print(f"  {G(chr(0x2713))} profile reset to defaults", flush=True)
        return

    if rest == "analyze":
        recent = []
        for h in history[-10:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                recent.append({"role": h["role"], "content": h["content"]})
        if not recent:
            print(f"  {Y(chr(0x203c))} no history to analyse - chat a bit first", flush=True)
            return
        print(f"  {M(chr(0x273b))} analysing {len(recent)} messages...", flush=True)

        async def _do_analyze():
            await _profile_service.analyze_and_update(recent, force=True)
            print(f"  {G(chr(0x2713))} profile updated", flush=True)
        try:
            asyncio.create_task(_do_analyze())
        except Exception as e:
            print(f"  {R(chr(0x2717))} {e}", flush=True)
        return

    if rest in ("on", "off"):
        enabled = rest == "on"
        _profile_service.set_auto_update(enabled)
        flag = G("on") if enabled else Y("off")
        print(f"  {G(chr(0x2713))} auto-update = {flag}", flush=True)
        return

    if rest == "path":
        print(f"  {K(_profile_store.path)}", flush=True)
        return

    # Unknown sub-command: list available
    print(f"  {K(chr(0x2130))} profile sub-commands:", flush=True)
    print(f"    {B(chr(0x2022))} profile            show current profile", flush=True)
    print(f"    {B(chr(0x2022))} profile analyze    re-run LLM analysis on session history", flush=True)
    print(f"    {B(chr(0x2022))} profile on/off     toggle auto-update", flush=True)
    print(f"    {B(chr(0x2022))} profile reset      wipe profile to defaults", flush=True)
    print(f"    {B(chr(0x2022))} profile path       show file location", flush=True)

async def main() -> None:
    print(flush=True)
    title = X("  XBot · autonomous agent · v5.0")
    # 居中显示
    pad = max(0, (PANEL_W - _visual_width(title)) // 2)
    print((" " * pad) + title, flush=True)
    print(hr(), flush=True)
    print(K("  claude-code ui  ·  reflexion paper-aligned  ·  single-source-of-truth"), flush=True)
    print(K("  输入 ") + C("'help'") + K("  查看命令,  ") + C("'quit'") + K("  退出"), flush=True)
    print(flush=True)

    model = "deepseek:deepseek-chat"
    history: List[dict] = []

    while True:
        try:
            user = input(C(chr(0x203a) + " "))
        except (EOFError, KeyboardInterrupt):
            print(K("\n  bye"), flush=True)
            break

        user = user.strip()
        if not user:
            continue

        # ── 命令分发 ──
        cmd = user.lower()
        if cmd in ("quit", "exit"):
            print(K("  bye"), flush=True)
            break
        if cmd == "clear":
            history = []
            print(f"  {G(chr(0x2713))} history cleared", flush=True)
            continue
        if cmd == "help":
            print(HELP_TEXT, flush=True)
            continue
        if cmd == "history":
            n = len(history) // 2
            suffix = f"   ·   {len(history)} messages in context"
            print(K(f"  {n} turns{suffix}"), flush=True)
            continue
        if cmd == "profile" or cmd.startswith("profile "):
            _handle_profile_command(user[len("profile"):].strip())
            continue
        if cmd.startswith("model "):
            new = user[6:].strip()
            if new:
                model = new
                msg = f"  {G(chr(0x2713))} model = {model}"
                print(msg, flush=True)
            continue

        # Inline pause: ask the running agent loop (if any) to stop.
        # Currently meaningful only if the user hits it BEFORE the next turn —
        # during a turn, Ctrl-C is the primary signal. Kept for symmetry / scripts.
        if cmd in ("pause", "stop", "abort"):
            request_pause(reason=cmd)
            continue

        # ── 普通任务 ──
        renderer = AgentRenderer()
        # While a turn runs, intercept Ctrl-C: instead of dying, just pause.
        # Pressing Ctrl-C twice in a row will bypass this and quit (SIGINT default).
        prev_handler = signal.getsignal(signal.SIGINT)

        def _sigint_pause(signum, frame):
            request_pause(reason="Ctrl-C")
            # second Ctrl-C should still kill the process
            signal.signal(signal.SIGINT, prev_handler)
        try:
            signal.signal(signal.SIGINT, _sigint_pause)
        except (ValueError, OSError):
            # Not on main thread / unsupported platform — skip the handler.
            pass

        paused = False
        try:
            await run_one(user, history, model, renderer)
            paused = _pause_event.is_set()
        except KeyboardInterrupt:
            print(R("\n  " + chr(0x2717) + " interrupted"), flush=True)
        except Exception as e:
            err = f"\n  {R(chr(0x2717))} {R(str(e))}"
            print(err, flush=True)
        finally:
            # Restore default SIGINT handling for the next input() wait.
            try:
                signal.signal(signal.SIGINT, prev_handler)
            except (ValueError, OSError):
                pass
            reset_pause()

        if paused:
            # Don't pollute history with a half-finished turn.
            continue

        history.extend([
            {"role": "user", "content": user},
            {"role": "assistant", "content": "(see terminal output above)"},
        ])
        if len(history) > 12:
            history = history[-12:]


def _visual_width(s: str) -> int:
    """粗略估算终端显示宽度（CJK 计 2 列, ANSI 转义不计）."""
    import re as _re
    s = _re.sub(r"\033\[[0-9;]*m", "", s)
    w = 0
    for ch in s:
        o = ord(ch)
        if o > 0x2E80:      # CJK / full-width
            w += 2
        elif ord(ch) < 32:
            pass
        else:
            w += 1
    return w


# ═══ Pause control ═════════════════════════════════════════════════════════
# A threading.Event lets the main input loop / Ctrl-C handler ask the agent
# loop to stop between events without blocking the terminal readline.
_pause_event = threading.Event()


def request_pause(reason: str = "user") -> None:
    """Signal the running agent loop to stop ASAP (between events). Idempotent."""
    if not _pause_event.is_set():
        _pause_event.set()
        print(R("\n  ⏸  pause requested ({0}); stopping after current step…"
                .format(reason)), flush=True)


def reset_pause() -> None:
    _pause_event.clear()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
