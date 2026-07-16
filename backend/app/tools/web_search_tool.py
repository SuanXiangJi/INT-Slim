"""
Web Search Tool - Using Tavily API for unified web search
"""
from app.tools.base import BaseTool, register_tool


@register_tool
class WebSearchTool(BaseTool):
    """Web Search - Unified search using Tavily API"""

    @property
    def id(self) -> str:
        return "web_search"

    @property
    def name(self) -> str:
        return "互联网搜索"

    @property
    def description(self) -> str:
        return """【互联网搜索】用于搜索最新信息、查找资料、了解时事新闻等。
适用场景：
- 用户说"搜索"、"查找"、"帮我找"
- 用户说"最新消息"、"最近发生了什么"
- 用户说"帮我查一下"、"了解一下"
- 用户要求查找论文、资料、新闻等

参数：query 是搜索关键词，limit 是返回结果数量（默认5条）"""

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词/问题"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量，默认5条",
                    "default": 5
                }
            },
            "required": ["query"]
        }

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        """执行搜索；可见来源随消息元数据持久化，不重复写入沙盒。"""
        try:
            from tavily import TavilyClient
            from app.config import settings

            api_key = settings.tavily_api_key
            if not api_key:
                return {"success": False, "error": "tavily_api_key is not configured (set TAVILY_API_KEY in backend/.env)", "source": "tavily"}
            client = TavilyClient(api_key)

            query = params.get("query", "")
            limit = params.get("limit", 5)

            if not query:
                return {"error": "query parameter is required"}

            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=limit
            )

            # 格式化结果（简化版，用于返回给 Agent）
            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", "")[:500] if item.get("content") else ""
                })

            return {
                "results": results,
                "query": query,
                "count": len(results),
                "source": "tavily",
                "raw_file": None,
                "raw_data_saved": False,
            }

        except ImportError:
            return {"error": "tavily-python library not installed. Run: pip install tavily-python"}
        except Exception as e:
            return {"error": str(e), "source": "tavily"}
