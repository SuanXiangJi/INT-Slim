"""
URL Fetch Tool - 抓取网页并用 LLM 围绕 focus 提炼核心信息。

调用者（autonomous_agent service）可以调用 `set_tool_llm_model(...)`
来指定 url_fetch 内部 LLM 调用所使用的模型。
"""
import requests
from bs4 import BeautifulSoup

from app.tools.base import BaseTool, register_tool
from app.services.llm_service import llm_service


# 默认模型；可被 set_tool_llm_model() 覆盖
_TOOL_LLM_MODEL = "deepseek:deepseek-chat"


def set_tool_llm_model(model: str) -> None:
    """由调用方设置 url_fetch 内部 LLM 调用的模型。"""
    global _TOOL_LLM_MODEL
    _TOOL_LLM_MODEL = model


def get_tool_llm_model() -> str:
    return _TOOL_LLM_MODEL


@register_tool
class UrlFetchTool(BaseTool):
    """URL Fetch - 抓取网页并用 LLM 围绕用户关注点提炼信息。"""

    @property
    def id(self) -> str:
        return "url_fetch"

    @property
    def name(self) -> str:
        return "网页抓取与提炼"

    @property
    def description(self) -> str:
        return (
            "【网页抓取与提炼】当用户提供 URL、希望了解网页内容时使用。\n"
            "使用场景：\n"
            "- 用户给出一个链接，希望总结、翻译或回答有关内容的提问\n"
            "- 用户希望调研某个网页的具体方面（定价 / 技术 / 融资等）\n\n"
            "参数：\n"
            "- url: 必填，目标网页地址（必须以 http:// 或 https:// 开头）\n"
            "- focus: 可选，描述你想从页面里提炼的方向，例如「定价」「技术架构」"
            "「融资历程」。留空则提炼主要内容。\n"
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "目标网页 URL（必须以 http:// 或 https:// 开头）",
                },
                "focus": {
                    "type": "string",
                    "description": "提炼方向 / 关注点，例如「定价」「融资历程」",
                    "default": "主要内容",
                },
                "max_length": {
                    "type": "integer",
                    "description": "抓取的原始正文最大字符数",
                    "default": 12000,
                },
            },
            "required": ["url"],
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        url = (params.get("url") or "").strip()
        focus = (params.get("focus") or "主要内容").strip() or "主要内容"
        max_length = int(params.get("max_length") or 12000)

        if not url:
            return {"success": False, "error": "url parameter is required"}
        if not url.startswith(("http://", "https://")):
            return {"success": False, "error": "URL 必须以 http:// 或 https:// 开头"}

        # ── 1. 抓取原始 HTML ──
        try:
            headers = {
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/120.0.0.0 Safari/537.36"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            return {"success": False, "error": f"请求超时：{url}"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": f"连接失败：{url}"}
        except requests.exceptions.HTTPError as e:
            code = getattr(e.response, "status_code", "?")
            return {"success": False, "error": f"HTTP {code}: {url}"}
        except Exception as e:
            return {"success": False, "error": f"抓取失败：{e}"}

        # ── 2. 解析正文 ──
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer",
                          "header", "aside", "noscript", "iframe"]):
            tag.decompose()

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        title = title or "无标题"

        content = soup.get_text(separator="\n", strip=True)
        lines = [ln for ln in content.split("\n") if ln.strip()]
        raw_text = "\n".join(lines)[:max_length]

        if not raw_text:
            return {"success": False, "error": "网页正文为空或全由噪音构成", "url": url}

        # ── 3. LLM 提炼 ──
        summary = await self._llm_summarize(raw_text, title, url, focus)

        return {
            "success": True,
            "url": url,
            "title": title,
            "focus": focus,
            "summary": summary,
            "raw_length": len(raw_text),
        }

    @staticmethod
    async def _llm_summarize(raw_text: str, title: str,
                                url: str, focus: str) -> str:
        """围绕 focus 用 LLM 提炼正文。优先返回结构化 JSON，失败时降级返回纯文本。"""
        prompt = (
            "你是一个网页内容提炼助手。基于用户关注点从长网页里提取"
            "真正有价值的信息。\n\n"
            "# 用户关注点\n"
            f"{focus}\n\n"
            "# 网页元信息\n"
            f"- 标题: {title}\n"
            f"- URL: {url}\n\n"
            "# 网页正文（已截断）\n"
            f"{raw_text}\n\n"
            "# 输出格式要求\n"
            "输出一个有效的 JSON 对象（不含 markdown 代码块），格式如下：\n"
            '{\n  "summary": "1-2句概括页面内容",\n  "key_points": ["要点1", "要点2", "要点3"],\n  "numbers": ["标题: 数值", "标题: 数值"],  // 可选，页面中的关键数字\n'
            '  "conclusion": "一句话结论或直接回答用户问题"  // 可选\n'
            "}\n"
            "要求：\n"
            "1. summary 控制在 100 字以内\n"
            "2. key_points 只保留与「用户关注点」直接相关的 2-5 个要点\n"
            "3. numbers 列出页面中的关键数据（如价格、百分比、排名等），格式「标签: 数值」\n"
            "4. 保持原文事实绝不编造；无法提取时对应字段填 null\n"
            "5. conclusion 直接回答用户问题（如用户问价格就给价格，问涨跌就给涨跌）\n"
            "6. 总输出控制在 800 字以内 JSON 字符串\n"
        )
        try:
            resp = llm_service.call_model_with_tools(
                messages=[
                    {"role": "system",
                     "content": "你是网页内容提炼助手。严格输出 JSON 格式，字段只填有效内容。"},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=get_tool_llm_model(),
                stream=False,
                max_tokens=2000,
            )
            raw = (resp.get("content", "")
                   if isinstance(resp, dict) else str(resp)).strip()

            # 尝试解析 JSON
            import json as _json
            # 去除可能的 markdown 代码块包装
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(lines[1:] if len(lines) > 2 else lines)
            data = _json.loads(raw)
            summary = data.get("summary", "")
            key_points = data.get("key_points") or []
            numbers = data.get("numbers") or []
            conclusion = data.get("conclusion") or ""

            # 组装为易读格式
            parts = [summary]
            if key_points:
                parts.append("【要点】")
                for p in key_points:
                    parts.append(f"· {p}")
            if numbers:
                parts.append("【数据】")
                for n in numbers:
                    parts.append(f"· {n}")
            if conclusion and conclusion != summary:
                parts.append(f"【结论】{conclusion}")
            return "\n".join(parts)

        except Exception as e:
            # 降级：尝试提取纯文本摘要
            fallback = await UrlFetchTool._llm_summarize_fallback(
                raw_text, title, url, focus
            )
            return fallback

    @staticmethod
    async def _llm_summarize_fallback(raw_text: str, title: str,
                                        url: str, focus: str) -> str:
        """降级提炼：不用 JSON，直接返回结构化纯文本。"""
        prompt = (
            "你是网页内容提炼助手。任务是从网页正文中提取与「"
            + focus + "」相关的信息。\n\n"
            "要求：\n"
            "1. 先写 1-2 句概括\n"
            "2. 然后用「·」列出 3-5 个关键要点\n"
            "3. 如有数字/价格/涨跌幅等，单独列出\n"
            "4. 绝不编造，控制在 600 字以内\n"
            "5. 删除导航、广告、版权等噪音\n\n"
            f"网页标题：{title}\n"
            f"用户关注点：{focus}\n\n"
            f"正文：\n{raw_text[:8000]}"
        )
        try:
            resp = llm_service.call_model_with_tools(
                messages=[
                    {"role": "system",
                     "content": "输出简洁、结构化、忠于原文的中文内容。"},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=get_tool_llm_model(),
                stream=False,
                max_tokens=1500,
            )
            content = (resp.get("content", "")
                       if isinstance(resp, dict) else str(resp)).strip()
            if content:
                return content
            return f"(无法提炼，页面片段：{raw_text[:300]})"
        except Exception as e:
            return f"[提炼失败: {e}]\n原文片段：{raw_text[:500]}"
