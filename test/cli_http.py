"""
XBot · HTTP CLI · v1.2
=======================

通过 HTTP API 调用后端服务，完整测试接口完整性。

功能
----
- 邮箱 + 密码登录，获取 Bearer token
- Quick 模式：普通 LLM 对话，无 agent / 无工具（流式输出，响应快）
- Agent 模式：ReAct + Reflexion 自主智能体（工个调用 + 自我反思）
- /new 新会话 / /conv 交互式会话管理
- /model 交互式模型切换 / /agent / /quick 模式切换
- /rename 重命名当前会话 / /info 查看状态
- SSE 流式输出，完整渲染 agent 事件
- Ctrl-C 中断，/pause 暂停

运行: python test/cli_http.py
"""

from __future__ import annotations

import os
import sys
import json
import signal
import asyncio
import shutil
import textwrap
import argparse
import time
from typing import Any, Dict, List, Optional

import httpx

# Global interrupt state
_interrupted = False

# ─── 配置 ────────────────────────────────────────────────────────────────────
_BASE_URL = os.getenv("XBOTS_API_URL", "http://localhost:8000/api/v1")
_EMAIL = os.getenv("XBOTS_EMAIL", "")
_PASSWORD = os.getenv("XBOTS_PASSWORD", "")


# ═══ ANSI 颜色（复用原生 CLI 的调色板）══════════════════════════════════════
def G(t): return "\033[32m" + t + "\033[0m"
def R(t): return "\033[31m" + t + "\033[0m"
def Y(t): return "\033[33m" + t + "\033[0m"
def B(t): return "\033[34m" + t + "\033[0m"
def M(t): return "\033[35m" + t + "\033[0m"
def C(t): return "\033[36m" + t + "\033[0m"
def K(t): return "\033[90m" + t + "\033[0m"
def X(t): return "\033[1m"  + t + "\033[0m"
def DIM(t): return "\033[2m" + t + "\033[0m"
def IT(t): return "\033[3m" + t + "\033[0m"


TERM_W = shutil.get_terminal_size((100, 24)).columns
PANEL_W = min(max(TERM_W, 70), 110)


def hr(char: str = "─") -> str:
    return K(char * PANEL_W)


def wrap_text(text: str, indent: str = "    ", width: int = 0) -> str:
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


# ═══ API 客户端 ──────────────────────────────────────────────────────────────
class XBotClient:
    def __init__(self, base_url: str = _BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    def set_token(self, token: str) -> None:
        self.token = token

    @property
    def headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=httpx.Timeout(60.0, connect=10.0),
            trust_env=False,
        )
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.__aexit__(*args)

    # ── Auth ──
    async def login(self, email: str, password: str) -> str:
        resp = await self._client.post("/auth/login/json", json={"email": email, "password": password})
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"login response missing access_token: {data}")
        self.set_token(token)
        self._client.headers.update(self.headers)
        return token

    async def get_me(self) -> dict:
        resp = await self._client.get("/auth/me")
        resp.raise_for_status()
        return resp.json()

    # ── Conversations ──
    async def list_conversations(self) -> List[dict]:
        resp = await self._client.get("/conversations")
        resp.raise_for_status()
        return resp.json()

    async def create_conversation(self, title: str = "New Chat") -> dict:
        resp = await self._client.post("/conversations", json={"title": title})
        resp.raise_for_status()
        return resp.json()

    async def get_conversation(self, conversation_id: str) -> dict:
        resp = await self._client.get(f"/conversations/{conversation_id}")
        resp.raise_for_status()
        return resp.json()

    async def update_conversation(self, conversation_id: str, title: str) -> dict:
        resp = await self._client.put(f"/conversations/{conversation_id}", json={"title": title})
        resp.raise_for_status()
        return resp.json()

    async def delete_conversation(self, conversation_id: str) -> None:
        resp = await self._client.delete(f"/conversations/{conversation_id}")
        resp.raise_for_status()

    async def get_or_create_conversation(self, conversation_id: Optional[str] = None,
                                         title: str = "New Chat") -> tuple[str, dict]:
        if conversation_id:
            resp = await self._client.get(f"/conversations/{conversation_id}")
            resp.raise_for_status()
            return conversation_id, resp.json()
        convs = await self.list_conversations()
        if convs:
            return convs[0]["id"], convs[0]
        conv = await self.create_conversation(title)
        return conv["id"], conv

    # ── Messages (streaming SSE) ──
    def send_message_stream(
        self,
        conversation_id: str,
        content: str,
        model: str = "deepseek:deepseek-chat",
        enable_agent: bool = True,
        resume: bool = False,
    ):
        """
        Send a message and return a streaming context manager.
        client.stream() returns an _AsyncGeneratorContextManager (NOT a coroutine).
        Usage:
            async with client.send_message_stream(...) as resp:
                async for chunk in resp.aiter_bytes(chunk_size=1):
                    ...
        """
        headers = {**self.headers, "Accept": "text/event-stream"}
        payload = {"content": content, "model": model, "enable_agent": enable_agent}
        if resume:
            payload["resume"] = True
        return self._client.stream(
            "POST",
            f"/conversations/{conversation_id}/messages",
            json=payload,
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers=headers,
        )

    # ── Models ──
    async def list_models(self) -> List[dict]:
        resp = await self._client.get("/models/available")
        resp.raise_for_status()
        return resp.json().get("models", [])

    # Knowledge Base (RAG) - thin client wrapper
    async def kb_add(self, content: str, metadata: dict = None) -> dict:
        resp = await self._client.post("/knowledge-base/documents", json={"content": content, "metadata": metadata or {}})
        resp.raise_for_status()
        return resp.json()

    async def kb_list(self) -> List[dict]:
        resp = await self._client.get("/knowledge-base/documents")
        resp.raise_for_status()
        return resp.json()

    async def kb_search(self, query: str, top_k: int = 3) -> List[dict]:
        resp = await self._client.post("/knowledge-base/search", json={"query": query, "top_k": top_k})
        resp.raise_for_status()
        return resp.json()

    async def kb_delete(self, doc_id: str) -> dict:
        resp = await self._client.delete(f"/knowledge-base/documents/{doc_id}")
        resp.raise_for_status()
        return resp.json()

    async def kb_clear(self) -> dict:
        resp = await self._client.delete("/knowledge-base/")
        resp.raise_for_status()
        return resp.json()



# ═══ SSE 解析 ────────────────────────────────────────────────────────────────
def parse_sse_line(line: bytes) -> Optional[tuple[str, dict]]:
    line = line.decode("utf-8", errors="replace").rstrip("\r\n")
    if not line.startswith("data: "):
        return None
    data = line[6:].strip()
    if data == "[DONE]":
        return ("done", {})
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    kind = payload.get("type")
    if kind:
        return (kind, payload)
    kind = payload.get("data", {}).get("type")
    if kind:
        return (kind, payload)
    return None


async def consume_sse_agent(response: httpx.Response,
                             renderer: "AgentRenderer",
                             pause_event,
                             title_callback) -> str:
    """消费 agent 模式 SSE（完整事件流）。

    SSE 事件以 \n\n 分隔，累积字节找到完整事件后再解析。
    """
    final_answer = ""
    buffer = b""
    async for chunk in response.aiter_bytes(chunk_size=1):
        if not chunk:
            continue
        buffer += chunk
        # SSE: 每个事件以 \n\n 结尾
        while b"\n\n" in buffer:
            raw_event, buffer = buffer.split(b"\n\n", 1)
            line = raw_event.decode("utf-8", errors="replace")
            if not line.startswith("data: "):
                continue
            try:
                payload = json.loads(line[6:].strip())
            except json.JSONDecodeError:
                continue
            kind = payload.get("type")
            data = payload.get("data", {}) or {}
            event: Dict[str, Any] = {}
            if kind == "thinking":
                event = {"type": "thinking", "data": {"content": data.get("content", "")}}
            elif kind == "action":
                event = {"type": "action", "data": {"tool": data.get("tool", ""), "params": data.get("params", {})}}
            elif kind == "observation":
                event = {"type": "observation", "data": {
                    "tool": data.get("tool", ""),
                    "success": data.get("success", True),
                    "formatted": data.get("formatted", ""),
                }}
            elif kind == "reflection":
                event = {"type": "reflection", "data": {
                    "n": data.get("n", 0),
                    "content": data.get("content", ""),
                }}
            elif kind == "finish":
                # Server emitted the finish event: open the FINAL ANSWER frame
                # BEFORE the assistant_chunk events arrive.
                event = {"type": "finish", "content": payload.get("content", "") or ""}
            elif kind in ("assistant_chunk", "content_chunk"):
                delta = payload.get("content", "") or data.get("content", "")
                if delta:
                    renderer._streaming = True
                    out = delta
                    if not renderer._streaming_started_line:
                        if not out.startswith(" "):
                            out = "  " + out
                        renderer._streaming_started_line = True
                    if "\n" in out:
                        out = out.replace("\n", "\n  ")
                        renderer._streaming_started_line = True
                    sys.stdout.write(out)
                    sys.stdout.flush()
            elif kind == "ask":
                event = {"type": "ask", "data": {"content": data.get("content", "")}}
            elif kind in ("run_done", "done"):
                event = {"type": "done", "data": data}
            elif kind == "title_update":
                new_title = data.get("title") or ""
                if new_title and title_callback:
                    title_callback(new_title)
                continue
            elif kind == "error":
                event = {"type": "error", "data": {"message": data.get("message", "unknown")}}
            else:
                continue

            if event:
                renderer.handle(event)
                if event.get("type") == "finish":
                    final_answer = event.get("content", "") or ""

        if pause_event.is_set():
            break
    return final_answer


async def consume_sse_quick(response: httpx.Response, pause_event) -> str:
    """消费 quick 模式 SSE（纯文本流，无工具）。

    SSE 事件以双换行 \n\n 分隔，按此边界解析才能完整拿到每个 assistant_chunk。
    """
    buffer = b""
    async for chunk in response.aiter_bytes(chunk_size=1):
        if not chunk:
            continue
        buffer += chunk
        # SSE 事件以 \n\n 分隔，找到完整事件再解析
        while b"\n\n" in buffer:
            raw_event, buffer = buffer.split(b"\n\n", 1)
            line = raw_event.decode("utf-8", errors="replace")
            if not line.startswith("data: "):
                continue
            try:
                payload = json.loads(line[6:].strip())
            except json.JSONDecodeError:
                continue
            kind = payload.get("type")
            if kind in ("assistant_chunk", "content_chunk"):
                delta = payload.get("content", "") or payload.get("data", {}).get("content", "")
                if delta:
                    sys.stdout.write(delta)
                    sys.stdout.flush()
            elif kind in ("run_done", "done"):
                break
            elif kind == "error":
                msg = payload.get("data", {}).get("message", "unknown error")
                print(R(f"\n  {chr(0x2717)} {msg}"), flush=True)
                break
        if pause_event.is_set():
            break
    print(flush=True)
    return ""


# ═══ Renderer（结构化输出）══════════════════════════════════════════════════
class AgentRenderer:
    """
    重设计的 Agent 渲染器：结构清晰，每一步可追溯。

    输出结构示例：

    ────────────────────────────────────────────────────────────
    [STEP 1]  thinking  ·  2 tools
    ────────────────────────────────────────────────────────────
      推理内容...

      ▶ web_search  {"query": "..."}
        ✓ 结果摘要...

      ▶ url_fetch  {"url": "...", "focus": "..."}
        ✓ 结果摘要...

    ────────────────────────────────────────────────────────────
    [STEP 2]  thinking  ·  1 tool
    ────────────────────────────────────────────────────────────
      ...

    ────────────────────────────────────────────────────────────
    [STEP 3]  thinking  ·  1 tool
    ────────────────────────────────────────────────────────────
      ...

    ════════════════════════════════════════════════════════════
    FINAL ANSWER
    ════════════════════════════════════════════════════════════
      完整回答内容...

    ────────────────────────────────────────────────────────────
    3 steps  ·  4 tools  ·  model
    ────────────────────────────────────────────────────────────
    """

    def __init__(self):
        self.steps = 0
        self.tool_count = 0
        self.reflect_count = 0
        self.model = ""
        self._finished = False
        # 当前 step 状态
        self._step_open = False
        self._step_thinking = ""
        self._step_actions: List[dict] = []
        # Timing & cumulative stats
        self._started_at = None
        self._tokens_in = 0
        self._tokens_out = 0
        # _streaming is True between the first assistant_chunk after _on_finish
        # and the closing _on_done; we use it to detect "finish without chunks".
        self._streaming = False
        # Tracks whether the next chunk should start a new indented line
        # (used to avoid breaking mid-line indent on every chunk).
        self._streaming_started_line = False

    def set_model(self, model: str):
        self.model = model

    def handle(self, event: Dict[str, Any]):
        kind = event.get("type")
        if self._started_at is None and kind in ("thinking", "action", "observation", "finish", "ask", "done", "error", "assistant_chunk"):
            self._started_at = time.monotonic()
        if kind == "thinking":
            self._on_thinking(event.get("data") or {})
        elif kind == "action":
            self._on_action(event.get("data") or {})
        elif kind == "observation":
            self._on_observation(event.get("data") or {})
        elif kind == "reflection":
            self._on_reflection(event.get("data") or {})
        elif kind == "finish":
            # _on_finish owns the _finished flag (it sets it to True after
            # opening the frame). Do NOT pre-set _finished here or _on_finish
            # would return immediately without printing anything.
            self._on_finish(event.get("content", "") or "")
        elif kind == "ask":
            self._on_ask(event.get("data", {}) or {})
        elif kind in ("run_done", "done"):
            self._on_done(event.get("data") or {})
        elif kind == "error":
            self._on_error(event.get("data") or {})
        try:
            sys.stdout.flush()
        except Exception:
            pass

    # ── 核心状态机 ──────────────────────────────────────────
    #
    #  SSE 事件顺序（固定）：
    #    thinking → action → obs → thinking → action → obs → ... → finish
    #
    #  关键不变式：
    #    - thinking 到达时，当前 step 的 header 尚未打印
    #    - action 到达时，才开始打印 header（含上一个 thinking）
    #    - observation 立即打印（紧跟其 action）
    #
    # ──────────────────────────────────────────────────────

    def _begin_step(self, tool: str, params: dict):
        """开始一个新 step：打印 header（含当前缓存的 thinking），再打印 action。"""
        self.steps += 1
        self._step_open = True
        saved_thinking = self._step_thinking
        self._step_thinking = ""
        self._step_actions = []

        params_str = json.dumps(params, ensure_ascii=False)
        if len(params_str) > 100:
            params_str = params_str[:100] + "..."

        print(f"\n  {K('─' * (PANEL_W - 4))}", flush=True)
        tool_label = f"1 tool"
        print(f"  {X(G('[STEP ' + str(self.steps) + ']'))}  {M('thinking')}  ·  {B(tool_label)}", flush=True)
        print(f"  {K('─' * (PANEL_W - 4))}", flush=True)
        if saved_thinking:
            paragraphs = saved_thinking.strip().split("\n\n")
            first = True
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                wrapped = wrap_text(para, indent="    ◆ " if first else "       ")
                for ln in wrapped.split("\n"):
                    print(f"  {M(ln)}", flush=True)
                first = False
        print(f"  {X(B('  ▶ ' + tool))}  {C(params_str)}", flush=True)

    def _print_step(self):
        """关闭当前 step（仅清除状态，无需额外打印，obs 已立即打印）。"""
        if not self._step_open:
            return
        self._step_open = False
        self._step_thinking = ""

    def _on_thinking(self, data: dict):
        content = (data.get("content") or "").strip()
        if not content:
            return
        # Strip <think>...</think> blocks (some models inline their CoT here).
        import re as _re
        content = _re.sub(r"<think>.*?</think>", "", content, flags=_re.DOTALL).strip()
        if not content:
            return
        # 如果当前无 open 的 step，thinking 属于上一个 step，缓存
        # 如果当前已有 open 的 step，thinking 属于下一个 step，也缓存
        # 总之总是缓存，等 action 到来时自然被打印
        self._step_thinking = content

    def _on_action(self, data: dict):
        tool = data.get("tool") or "?"
        params = data.get("params") or {}
        self.tool_count += 1

        if self._step_open:
            # 当前 step 已存在，先关闭它
            self._print_step()

        # 开始新 step（此时 self._step_thinking 是上一个 thinking）
        self._begin_step(tool, params)
        self._step_actions.append({"tool": tool, "params": params, "obs": None})

    def _on_observation(self, data: dict):
        formatted = (data.get("formatted") or "").rstrip()
        tool = data.get("tool") or "?"
        success = bool(data.get("success", True))
        mark = G("✓") if success else R("✗")

        # 找到最后一个无 obs 的对应 action
        for act in reversed(self._step_actions):
            if act["tool"] == tool and act["obs"] is None:
                act["obs"] = formatted
                break
        else:
            return

        if formatted:
            for ln in formatted.split("\n"):
                ln = ln.strip()
                if not ln:
                    continue
                print(f"  {mark}  {ln}", flush=True)
        else:
            print(f"  {mark}  (无返回内容)", flush=True)

    def _on_reflection(self, data: dict):
        if self._step_open:
            self._print_step()
        n = int(data.get("n") or 0)
        raw = (data.get("content") or "").strip()
        if not raw:
            return
        # 去除 <排除>thinking 标签，只保留正文
        import re as _re
        content = _re.sub(r"<排除>.*?</排除>", "", raw, flags=_re.DOTALL).strip()
        if not content:
            content = raw  # fallback to raw if stripping emptied it
        self.reflect_count = max(self.reflect_count, n)
        print(f"\n  {K('═' * (PANEL_W - 4))}", flush=True)
        print(f"  {X(Y('  ⚙ REFLECTION #' + str(n)))}", flush=True)
        print(f"  {K('─' * (PANEL_W - 4))}", flush=True)
        print(wrap_text(content, indent="    "), flush=True)

    def _on_finish(self, content: str):
        """Print the opening frame of the FINAL ANSWER box.

        The content is streamed by consume_sse_agent via assistant_chunk
        events, so we only print the frame here. We also stash the content
        in self._last_answer for later use (/copy etc.).
        """
        if self._finished:
            return
        self._finished = True
        if self._step_open:
            self._print_step()
        bar = "═" * (PANEL_W - 4)
        print(f"\n  {G(bar)}", flush=True)
        print(f"  {X(G('✓ FINAL ANSWER'))}", flush=True)
        print(f"  {G(bar)}", flush=True)
        self._last_answer = content or ""
        self._streaming_started_line = False
        # If the server sent finish without any chunks (rare), the CLI consumer
        # will print the content as a fallback. _on_done also handles this.

    def _on_ask(self, data: dict):
        content = (data.get("content") or "") or (data.get("question") or "")
        if not content.strip():
            return
        if self._step_open:
            self._print_step()
        print(f"\n  {K('─' * (PANEL_W - 4))}", flush=True)
        print(f"  {X(Y('  ? ASK USER'))}", flush=True)
        print(f"  {K('─' * (PANEL_W - 4))}", flush=True)
        print(wrap_text(content, indent="    "), flush=True)

    def _on_done(self, data: dict):
        if self._step_open:
            self._print_step()
        # If the frame was opened but no chunks arrived (server-side bug),
        # print the stashed content here as a fallback.
        if self._finished and not self._streaming and self._last_answer.strip():
            wrapped = wrap_text(self._last_answer, indent="", width=PANEL_W - 4)
            for ln in wrapped.split("\n"):
                print(f"  {ln}", flush=True)
        # Close the FINAL ANSWER box if it was opened and we streamed.
        if self._finished and self._streaming:
            bar = "═" * (PANEL_W - 4)
            print(f"\n  {G(bar)}", flush=True)
        self._streaming = False
        elapsed = self._elapsed_str()
        ref_label = f"  ·  {Y(str(self.reflect_count) + ' reflection' + ('s' if self.reflect_count > 1 else ''))}" if self.reflect_count else ""
        print(f"\n  {K('─' * (PANEL_W - 4))}", flush=True)
        label = (f"  {G(str(self.steps))} {DIM('steps')}  ·  "
                 f"{B(str(self.tool_count))} {DIM('tools')}"
                 f"{ref_label}"
                 f"  ·  {DIM(self.model)}"
                 f"  ·  {K(elapsed)}")
        print(label, flush=True)
        print(f"  {K('─' * (PANEL_W - 4))}", flush=True)

    def _on_error(self, data: dict):
        msg = data.get("message") or "unknown error"
        self._finished = True
        if self._step_open:
            self._print_step()
        elapsed = self._elapsed_str()
        print(f"\n  {K('─' * (PANEL_W - 4))}", flush=True)
        print(f"  {R('✗ ERROR:')} {R(msg)}", flush=True)
        ref_label = f"  ·  {Y(str(self.reflect_count) + ' reflection' + ('s' if self.reflect_count > 1 else ''))}" if self.reflect_count else ""
        label = (f"  {G(str(self.steps))} {DIM('steps')}  ·  "
                 f"{B(str(self.tool_count))} {DIM('tools')}"
                 f"{ref_label}"
                 f"  ·  {DIM(self.model)}"
                 f"  ·  {K(elapsed)}")
        print(f"  {K('─' * (PANEL_W - 4))}", flush=True)
        print(label, flush=True)

    def _on_step_complete(self, data: dict):
        """Optional explicit step-complete event (currently unused but ready)."""
        pass

    def _elapsed_str(self) -> str:
        if not self._started_at:
            return ""
        dt = time.monotonic() - self._started_at
        if dt < 60:
            return f"{dt:.1f}s"
        m, s = divmod(dt, 60)
        return f"{int(m)}m{s:04.1f}s"


# ═══ 交互式选择器 ────────────────────────────────────────────────────────────
async def _interactive_model_pick(client: XBotClient, current: str) -> Optional[str]:
    models = await client.list_models()
    if not models:
        print(f"  {R(chr(0x2717))}  没有可用模型", flush=True)
        return None

    display_models = []
    for m in models:
        mid = m.get("id", "")
        name = m.get("name") or m.get("id", "")
        provider = m.get("provider", "")
        desc = (m.get("description") or "")[:50]
        display_models.append({
            "id": mid,
            "display": f"{B(provider + ':')}{name}" if provider else name,
            "extra": f"    {K(desc)}" if desc else "",
        })

    print(flush=True)
    print(hr(), flush=True)
    print(f"  {X('Select Model')}  {K('(current: ' + current + ')')}", flush=True)
    print(flush=True)

    for i, m in enumerate(display_models):
        mark = G(chr(0x25cf)) if m["id"] == current else "  "
        print(f"  {mark} {X(str(i + 1))}.  {m['display']}", flush=True)
        if m["extra"]:
            print(f"       {K(m['extra'])}", flush=True)

    print(flush=True)
    print(f"  {K('Enter')} 确认 · {K('q')} 取消", flush=True)

    while True:
        try:
            raw = input(C(f"  {chr(0x203a)} ")).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if raw.lower() in ("q", "quit", "c", "cancel", ""):
            return None
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(display_models):
                return display_models[idx]["id"]
        except ValueError:
            pass


async def _interactive_conv_manager(client: XBotClient, current_id: str,
                                     conv_title: str) -> Optional[tuple[str, dict, str]]:
    """
    交互式会话管理器。
    返回 (new_conversation_id, conversation_obj, new_title) 或 None（取消）。
    """
    convs = await client.list_conversations()

    print(flush=True)
    print(hr(), flush=True)
    print(f"  {X('Conversations')}  {K(str(len(convs)) + ' total')}", flush=True)
    print(flush=True)

    for i, c in enumerate(convs[:20]):
        cid = c.get("id", "")
        title = c.get("title") or "(no title)"
        is_current = cid == current_id
        mark = G(chr(0x25cf)) if is_current else "  "
        short_cid = cid[:8]
        updated = (c.get("updated_at") or "")[:10]
        extra = f"  {K(updated)}" if updated else ""
        title_colored = G(title) if is_current else title
        print(f"  {mark} {X(str(i + 1))}.  {title_colored}{extra}  {K('(' + short_cid + '...)')}", flush=True)

    if len(convs) > 20:
        print(f"  {K('  ... and')}", flush=True)

    print(flush=True)
    print(f"  {K('Enter')} 选择 · {K('n')} 新建 · {K('r')} 重命名当前 · {K('d')} 删除 · {K('q')} 取消", flush=True)

    while True:
        try:
            raw = input(C(f"  {chr(0x203a)} ")).strip()
        except (EOFError, KeyboardInterrupt):
            return None

        lower = raw.lower()
        if lower in ("q", "quit", "cancel", ""):
            return None
        if lower == "n":
            title = input(C(f"  {chr(0x2192)}  标题: ")).strip() or "New Chat"
            try:
                conv = await client.create_conversation(title)
                print(f"  {G(chr(0x2713))} 新建: {conv.get('title')}", flush=True)
                return conv["id"], conv, conv.get("title", "New Chat")
            except Exception as e:
                print(f"  {R(chr(0x2717))} {e}", flush=True)
                continue
        if lower == "r":
            new_title = input(C(f"  {chr(0x2192)}  新标题 [{conv_title}]: ")).strip()
            if new_title:
                try:
                    conv = await client.update_conversation(current_id, new_title)
                    print(f"  {G(chr(0x2713))} 重命名为: {new_title}", flush=True)
                    return current_id, conv, new_title
                except Exception as e:
                    print(f"  {R(chr(0x2717))} {e}", flush=True)
            continue
        if lower == "d":
            print(flush=True)
            print(f"  {K('输入编号删除 (1-{})'.format(min(20, len(convs))))}", flush=True)
            try:
                raw2 = input(C(f"  {chr(0x203a)} ")).strip()
            except (EOFError, KeyboardInterrupt):
                continue
            if raw2.lower() in ("q", ""):
                continue
            try:
                idx = int(raw2) - 1
                if 0 <= idx < len(convs):
                    to_del = convs[idx]
                    confirm = input(C(f"  {chr(0x2192)}  确认删除 '{to_del.get('title', '?')}'? (y/n): ")).strip().lower()
                    if confirm == "y":
                        await client.delete_conversation(to_del["id"])
                        print(f"  {G(chr(0x2713))} 已删除", flush=True)
                        if to_del["id"] == current_id:
                            remaining = [c for c in convs if c["id"] != to_del["id"]]
                            if remaining:
                                return remaining[0]["id"], remaining[0], remaining[0].get("title", "New Chat")
                            return None
            except Exception as e:
                print(f"  {R(chr(0x2717))} {e}", flush=True)
            continue
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(convs):
                c = convs[idx]
                return c["id"], c, c.get("title", "New Chat")
        except ValueError:
            pass


# ═══ 状态栏 Prompt ───────────────────────────────────────────────────────────
def _prompt(model: str, mode: str, conv_title: str) -> str:
    """生成状态感知的 prompt 前缀。"""
    mode_tag = M(f"[{mode}]") if mode == "agent" else C(f"[{mode}]")
    model_short = model.split(":")[-1] if ":" in model else model
    return f"{mode_tag} {K(model_short)} · {Y(conv_title[:20])} {C(chr(0x203a) + ' ')}"


# ═══ 主循环 ──────────────────────────────────────────────────────────────────
HELP_TEXT = (
    "\n"
    "XBot HTTP CLI - 命令说明\n"
    "------------------------\n"
    "\n"
    "  直接输入任务     通过 HTTP API 调用后端\n"
    "\n"
    "  命令:\n"
    "    /new              新建会话（交互式标题）\n"
    "    /conv             切换 / 新建 / 重命名 / 删除会话\n"
    "    /model            交互式模型切换\n"
    "    /model <id>       直接切换模型\n"
    "    /agent            切换到 Agent 模式（ReAct + 工具 + 反思）\n"
    "    /quick            切换到 Quick 模式（普通 LLM，无工具）\n"
    "    /rename           重命名当前会话\n"
    "    /info             显示当前会话信息\n"
    "    /clear            清空本地历史\n"
    "    /history          查看本地历史大小\n"
    "    /token            显示当前 token\n"
    "    /help             显示此帮助\n"
    "    /quit             退出\n"
    "\n"
    "  模式说明:\n"
    "    agent             ReAct 循环 + 工具调用 + 自我反思（默认）\n"
    "    quick             普通 LLM 对话，纯流式输出，响应更快\n"
    "\n"
    "  快捷键:\n"
    "    Ctrl-C            中断当前请求\n"
    "    /pause            暂停\n"
)

_pause_event: Optional[asyncio.Event] = None


def request_pause(reason: str = "user") -> None:
    if _pause_event and not _pause_event.is_set():
        _pause_event.set()
        print(R(f"\n  ⏸  pause requested ({reason})"), flush=True)


async def run_one(client: XBotClient, conversation_id: str,
                  user_input: str, model: str,
                  agent_mode: bool, renderer: AgentRenderer,
                  title_callback=None, resume: bool = False) -> None:
    global _pause_event
    _pause_event = asyncio.Event()

    print(flush=True)

    try:
        async with client.send_message_stream(
            conversation_id=conversation_id,
            content=user_input,
            model=model,
            enable_agent=agent_mode,
            resume=resume,
        ) as response:

            if response.status_code == 401:
                print(R(f"\n  {chr(0x2717)}  认证失败，请重新登录"), flush=True)
                return
            if response.status_code == 403:
                print(R(f"\n  {chr(0x2717)}  权限不足"), flush=True)
                return
            if response.status_code >= 400:
                print(R(f"\n  {chr(0x2717)}  HTTP {response.status_code}: {response.text[:300]}"), flush=True)
                return

            if agent_mode:
                renderer.set_model(model)
                await consume_sse_agent(response, renderer, _pause_event, title_callback)
            else:
                await consume_sse_quick(response, _pause_event)

    except httpx.TimeoutException:
        print(R(f"\n  {chr(0x2717)}  请求超时（120s）"), flush=True)
    except Exception as e:
        print(R(f"\n  {chr(0x2717)}  {e}"), flush=True)
    finally:
        _pause_event = None


async def main() -> None:
    parser = argparse.ArgumentParser(description="XBot HTTP CLI", add_help=False)
    parser.add_argument("--url", default=_BASE_URL)
    parser.add_argument("--email", default=_EMAIL)
    parser.add_argument("--password", default=_PASSWORD)
    parser.add_argument("--conv-id")
    parser.add_argument("--model", default="deepseek:deepseek-v4-flash")
    parser.add_argument("--new-conv", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Start in quick mode")
    args = parser.parse_args()

    print(flush=True)
    title = X("  XBot · HTTP CLI · v1.2")
    pad = max(0, (PANEL_W - _visual_width(title)) // 2)
    print((" " * pad) + title, flush=True)
    print(hr(), flush=True)
    print(K("  /help 查看命令 · /quit 退出"), flush=True)
    print(flush=True)

    email = args.email
    password = args.password
    agent_mode = not args.quick  # default to agent unless --quick flag

    async with XBotClient(base_url=args.url) as client:
        # ── 登录 ──
        if email and password:
            print(f"  {K(chr(0x2192))} 登录中: {email}", flush=True)
            try:
                await client.login(email, password)
                me = await client.get_me()
                print(f"  {G(chr(0x2713))} 已登录: {me.get('email', email)}", flush=True)
            except Exception as e:
                print(R(f"  {chr(0x2717)} 登录失败: {e}"), flush=True)
                print(Y("  继续以未登录状态"), flush=True)
        else:
            env_token = os.getenv("XBOTS_TOKEN")
            if env_token:
                client.set_token(env_token)
                try:
                    me = await client.get_me()
                    print(f"  {G(chr(0x2713))} 已通过 env token 登录: {me.get('email')}", flush=True)
                except Exception:
                    print(Y("  env token 无效"), flush=True)
                    client.token = None

        print(flush=True)

        # ── Conversation ──
        conversation_id: Optional[str] = None
        conv_title = "New Chat"
        if args.conv_id:
            conversation_id, conv = await client.get_or_create_conversation(args.conv_id)
            conv_title = conv.get("title", "New Chat")
            print(f"  {K(chr(0x2192))} 复用: {conv_title}", flush=True)
        elif args.new_conv:
            conversation_id, conv = await client.get_or_create_conversation()
            conv_title = conv.get("title", "New Chat")
            print(f"  {G(chr(0x2713))} 新建: {conv_title}", flush=True)
        else:
            conversation_id, conv = await client.get_or_create_conversation()
            conv_title = conv.get("title", "New Chat")
            print(f"  {K(chr(0x2192))} 当前: {conv_title}", flush=True)

        model = args.model
        history: List[dict] = []

        # ── REPL 循环 ──
        while True:
            prompt_prefix = _prompt(model, "agent" if agent_mode else "quick", conv_title)
            try:
                user = input(C(prompt_prefix))
            except (EOFError, KeyboardInterrupt):
                print(K("\n  bye"), flush=True)
                break

            user_raw = user.strip()
            if not user_raw:
                continue

            cmd = user_raw.lstrip("/").lower()

            # ── / 命令 ──
            if user_raw.startswith("/"):
                if cmd in ("quit", "exit"):
                    print(K("  bye"), flush=True)
                    break

                if cmd == "help":
                    print(HELP_TEXT, flush=True)
                    continue

                if cmd == "kb" or cmd.startswith("kb "):
                    parts = user_raw.split(None, 2)
                    sub = parts[1].lower() if len(parts) > 1 else "list"
                    try:
                        if sub == "list":
                            docs = await client.kb_list()
                            if not docs:
                                print(K("  (empty)"), flush=True)
                            else:
                                print(B("  " + str(len(docs)) + " documents:"), flush=True)
                                for d in docs:
                                    src = d.get('metadata', {}).get('source', '')
                                    print("    " + d['doc_id'][:12] + "...  (" + str(d['chunk_count']) + " chunks)  " + src, flush=True)
                        elif sub == "add":
                            text = parts[2] if len(parts) > 2 else ""
                            if not text:
                                print(R("  usage: /kb add <text>"), flush=True)
                            else:
                                result = await client.kb_add(text)
                                print(G("  + added (" + str(result['chunk_count']) + " chunks)"), flush=True)
                        elif sub == "search":
                            query = parts[2] if len(parts) > 2 else ""
                            if not query:
                                print(R("  usage: /kb search <query>"), flush=True)
                            else:
                                results = await client.kb_search(query, top_k=3)
                                if not results:
                                    print(K("  (no matches)"), flush=True)
                                else:
                                    print(B("  " + str(len(results)) + " results:"), flush=True)
                                    for r in results:
                                        print("    [" + str(round(r['score'], 3)) + "] " + r['content'][:80] + "...", flush=True)
                        elif sub == "clear":
                            await client.kb_clear()
                            print(G("  cleared"), flush=True)
                        else:
                            print(K("  usage: /kb [list|add|search|clear]"), flush=True)
                    except Exception as e:
                        print(R("  " + str(e)), flush=True)
                    continue

                if cmd == "new":
                    title = input(C(f"  {chr(0x2192)}  标题: ")).strip() or "New Chat"
                    try:
                        conv = await client.create_conversation(title)
                        conversation_id, conv_title = conv["id"], conv.get("title", "New Chat")
                        history = []
                        print(f"  {G(chr(0x2713))} 新建: {conv_title}", flush=True)
                    except Exception as e:
                        print(f"  {R(chr(0x2717))} {e}", flush=True)
                    continue

                if cmd == "conv" or cmd.startswith("conv"):
                    result = await _interactive_conv_manager(client, conversation_id, conv_title)
                    if result is not None:
                        conversation_id, conv, conv_title = result
                        history = []
                        print(f"  {G(chr(0x2713))} 切换: {conv_title}", flush=True)
                    continue

                if cmd == "rename":
                    new_title = input(C(f"  {chr(0x2192)}  新标题 [{conv_title}]: ")).strip()
                    if new_title:
                        try:
                            conv = await client.update_conversation(conversation_id, new_title)
                            conv_title = new_title
                            print(f"  {G(chr(0x2713))} 重命名: {conv_title}", flush=True)
                        except Exception as e:
                            print(f"  {R(chr(0x2717))} {e}", flush=True)
                    continue

                if cmd == "info":
                    print(flush=True)
                    print(f"  {K('conversation:')} {Y(conv_title)}  {K('(' + conversation_id[:8] + '...)')}", flush=True)
                    print(f"  {K('model:')}       {B(model)}", flush=True)
                    print(f"  {K('mode:')}        {'agent (ReAct + tools + reflection)' if agent_mode else 'quick (plain LLM)'}", flush=True)
                    print(f"  {K('history:')}     {len(history)//2} turns · {len(history)} messages", flush=True)
                    print(flush=True)
                    continue

                if cmd == "clear":
                    history = []
                    print(f"  {G(chr(0x2713))} history cleared", flush=True)
                    continue

                if cmd == "history":
                    n = len(history) // 2
                    print(K(f"  {n} turns · {len(history)} messages"), flush=True)
                    continue

                if cmd == "token":
                    if client.token:
                        print(f"  {K(client.token[:24] + '...')}", flush=True)
                    else:
                        print(f"  {K('no token')}", flush=True)
                    continue

                if cmd == "model" or cmd.startswith("model"):
                    rest = user_raw[len("/model"):].strip()
                    if rest:
                        model = rest
                        print(f"  {G(chr(0x2713))} model = {model}", flush=True)
                    else:
                        new_model = await _interactive_model_pick(client, model)
                        if new_model is not None:
                            model = new_model
                            print(f"  {G(chr(0x2713))} model = {model}", flush=True)
                        else:
                            print(f"  {K('model unchanged: ' + model)}", flush=True)
                    continue

                if cmd == "agent":
                    if not agent_mode:
                        agent_mode = True
                        print(f"  {G(chr(0x2713))} 切换到 {G('agent')} 模式（ReAct + 工具 + 反思）", flush=True)
                    else:
                        print(f"  {K('already in agent mode')}", flush=True)
                    continue

                if cmd in ("quick", "q") and cmd == "quick" or user_raw == "/q":
                    # /q 或 /quick 切到 quick 模式
                    pass
                if cmd in ("quick", "q"):
                    if agent_mode:
                        agent_mode = False
                        print(f"  {G(chr(0x2713))} 切换到 {C('quick')} 模式（普通 LLM，无工具）", flush=True)
                    else:
                        print(f"  {K('already in quick mode')}", flush=True)
                    continue

                if cmd in ("pause", "stop", "abort"):
                    request_pause(reason=cmd)
                    continue

                # 未知命令
                print(f"  {K('unknown command: /' + cmd)}", flush=True)
                continue

            # ── 普通任务 ──
            renderer = AgentRenderer()

            def on_title_update(new_title: str):
                nonlocal conv_title
                old = conv_title
                conv_title = new_title
                print(f"  {G('✎ title:')} {Y(new_title)}  {K(f'({old} → {new_title})')}", flush=True)

            prev_handler = signal.getsignal(signal.SIGINT)
            def _sigint_interrupt(signum, frame):
                global _interrupted
                _interrupted = True
                request_pause("Ctrl-C")
                signal.signal(signal.SIGINT, prev_handler)
            try:
                signal.signal(signal.SIGINT, _sigint_interrupt)
            except (ValueError, OSError):
                pass

            try:
                await run_one(client, conversation_id, user_raw, model, agent_mode, renderer, on_title_update)
            except KeyboardInterrupt:
                print(R("\n  interrupted"), flush=True)
            finally:
                try:
                    signal.signal(signal.SIGINT, prev_handler)
                except (ValueError, OSError):
                    pass

            history.extend([
                {"role": "user", "content": user_raw},
                {"role": "assistant", "content": "(see output above)"},
            ])
            if len(history) > 12:
                history = history[-12:]

            # After run completes, check if we were interrupted
            global _interrupted
            if _interrupted:
                _interrupted = False
                print(f"\n  {Y(chr(0x26A0))} Interrupted - type new message to continue:", flush=True)
                try:
                    resume_input = input(C("  \u2192  "))
                except (EOFError, KeyboardInterrupt):
                    print(K("\n  bye"), flush=True)
                    break
                resume_raw = resume_input.strip()
                if resume_raw:
                    try:
                        await run_one(client, conversation_id, resume_raw, model, agent_mode, renderer, on_title_update, resume=True)
                    except KeyboardInterrupt:
                        print(R("\n  interrupted"), flush=True)
                    history.extend([
                        {"role": "user", "content": resume_raw},
                        {"role": "assistant", "content": "(see output above)"},
                    ])
                    if len(history) > 12:
                        history = history[-12:]


def _visual_width(s: str) -> int:
    import re as _re
    s = _re.sub(r"\033\[[0-9;]*m", "", s)
    w = 0
    for ch in s:
        o = ord(ch)
        if o > 0x2E80:
            w += 2
        elif ord(ch) < 32:
            pass
        else:
            w += 1
    return w


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

