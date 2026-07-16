import glob
import json
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

from app.tools.base import BaseTool, register_tool

logger = logging.getLogger(__name__)
SYSTEM_KB_USER_ID = b"\x00" * 16

_DEMO_KB = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "..",
        "sandbox",
        "demo_kb",
        "knowledge",
    )
)


@register_tool
class KnowledgeSearchTool(BaseTool):
    """Search learning knowledge sources."""

    @property
    def id(self) -> str:
        return "knowledge_search"

    @property
    def name(self) -> str:
        return "\u77e5\u8bc6\u68c0\u7d22"

    @property
    def description(self) -> str:
        return (
            "\u4ece\u8bfe\u7a0b\u5e93\u3001\u6587\u6863\u3001\u77e5\u8bc6\u56fe\u8c31\u3001\u89c4\u5219\u5e93\u68c0\u7d22\u4fe1\u606f\u3002"
            "operation \u652f\u6301: search, list_courses, get_course, query_graph, get_rules, list_sources."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "search",
                        "list_courses",
                        "get_course",
                        "query_graph",
                        "get_rules",
                        "list_sources",
                    ],
                    "description": "\u8981\u6267\u884c\u7684\u64cd\u4f5c",
                },
                "query": {"type": "string", "description": "\u641c\u7d22\u5173\u952e\u8bcd"},
                "course_id": {"type": "string", "description": "\u8bfe\u7a0bID"},
                "limit": {"type": "integer", "default": 5, "description": "\u7ed3\u679c\u4e0a\u9650"},
                "rule_categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "\u89c4\u5219\u7c7b\u522b\u8fc7\u6ee4",
                },
            },
            "required": ["operation"],
        }

    def _kb_path(self, sandbox_path: str) -> str:
        if self._has_db_courses():
            return ""
        if os.path.isdir(_DEMO_KB):
            return _DEMO_KB
        for path in [
            os.path.join(sandbox_path, "knowledge"),
            os.path.join(os.path.dirname(sandbox_path), "demo_kb", "knowledge"),
        ]:
            if os.path.isdir(path):
                return path
        fallback = os.path.join(sandbox_path, "knowledge")
        for subdir in ("", "courses", "docs"):
            os.makedirs(os.path.join(fallback, subdir), exist_ok=True)
        return fallback

    def _tokenize(self, text: str) -> list[str]:
        text = (text or "").lower()
        tokens = re.findall(r"[a-zA-Z0-9_]+", text)
        cjk = "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
        tokens.extend(cjk)
        for n in (2, 3):
            if len(cjk) >= n:
                tokens.extend(cjk[i : i + n] for i in range(len(cjk) - n + 1))
        return [token for token in tokens if token]

    def _expand_query_terms(self, query: str) -> set[str]:
        terms = set(self._tokenize(query))
        normalized = (query or "").lower()
        if "\u5165\u95e8" in normalized:
            terms.update([
                "\u5165\u95e8",
                "\u7b80\u4ecb",
                "\u57fa\u7840",
                "\u57fa\u672c",
                "\u73af\u5883",
                "\u914d\u7f6e",
            ])
        if "\u57fa\u7840" in normalized:
            terms.update([
                "\u57fa\u7840",
                "\u57fa\u672c",
                "\u7b80\u4ecb",
                "\u8bed\u6cd5",
            ])
        return terms

    def _contains_term(self, text: str, term: str) -> bool:
        text = (text or "").lower()
        term = (term or "").lower()
        if not term:
            return False
        if re.fullmatch(r"[a-zA-Z0-9_]+", term):
            return re.search(rf"(?<![a-zA-Z0-9_]){re.escape(term)}\d*(?![a-zA-Z_])", text) is not None
        return term in text

    def _score_page(self, query: str, query_terms: set[str], course: dict, page: dict) -> float:
        course_name = str(course.get("name", ""))
        slug = str(page.get("slug", ""))
        title = str(page.get("title", ""))
        summary = str(page.get("summary", ""))
        tags = " ".join(str(tag) for tag in page.get("tags", []))
        haystack = f"{course_name} {course.get('description', '')} {slug} {title} {summary} {tags}".lower()
        normalized_query = (query or "").lower().strip()
        subject_terms = [
            term for term in self._tokenize(query)
            if re.fullmatch(r"[a-zA-Z0-9_]+", term)
        ]
        if subject_terms and not any(self._contains_term(haystack, term) for term in subject_terms):
            return 0.0

        score = 0.0
        if normalized_query and normalized_query in haystack:
            score += 12.0
        for term in query_terms:
            if not term:
                continue
            if self._contains_term(title, term):
                score += 5.0
            if self._contains_term(course_name, term):
                score += 4.0
            if self._contains_term(tags, term):
                score += 3.0
            if self._contains_term(summary, term):
                score += 1.5

        if "\u5165\u95e8" in normalized_query or "\u57fa\u7840" in normalized_query:
            title_lower = title.lower()
            slug_lower = slug.lower()
            if any(marker in title_lower for marker in (
                "\u5165\u95e8",
                "\u7b80\u4ecb",
                "\u57fa\u7840",
                "\u57fa\u672c",
                "\u73af\u5883\u914d\u7f6e",
                "\u5f00\u53d1\u73af\u5883",
            )):
                score += 8.0
            if any(marker in slug_lower for marker in ("intro", "basic", "syntax", "setup", "install", "environment")):
                score += 6.0
            if "\u5b9e\u4f8b" in title:
                score -= 4.0
        return score

    def _page_priority(self, page: dict) -> int:
        slug = str(page.get("slug", "")).lower()
        title = str(page.get("title", ""))
        if "intro" in slug or "\u7b80\u4ecb" in title:
            return 50
        if "environment" in slug or "setup" in slug or "\u73af\u5883" in title or "\u914d\u7f6e" in title:
            return 45
        if "basic-syntax" in slug or "\u57fa\u7840\u8bed\u6cd5" in title:
            return 44
        if "basic" in slug or "\u57fa\u7840" in title or "\u57fa\u672c" in title:
            return 40
        if "\u5b9e\u4f8b" in title:
            return -20
        return 0

    def _load_json(self, path: str) -> Any:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _load_db_courses(self) -> list[dict]:
        """Load the shared course catalog from the MySQL system knowledge base."""
        try:
            from app.models import SessionLocal
            from app.models.knowledge_base import KnowledgeDocument
            with SessionLocal() as db:
                rows = db.query(KnowledgeDocument).filter(
                    KnowledgeDocument.user_id == SYSTEM_KB_USER_ID,
                ).all()
            grouped: dict[str, dict] = {}
            for row in rows:
                meta = row.doc_metadata or {}
                remainder = row.doc_id[len("cainiao_"):] if row.doc_id.startswith("cainiao_") else row.doc_id
                course_id, _, slug = remainder.partition("_")
                course_id = str(row.category or meta.get("category") or course_id or "unknown")
                source_url = str(
                    meta.get("source_url") or meta.get("canonical_url") or meta.get("url") or ""
                )
                if not slug and source_url:
                    slug = urlparse(source_url).path.rstrip("/").rsplit("/", 1)[-1]
                course = grouped.setdefault(course_id, {
                    "id": course_id,
                    "name": str(meta.get("category_label") or course_id.upper()),
                    "description": str(meta.get("description") or f"{course_id.upper()} 学习资料"),
                    "page_count": 0,
                    "pages": [],
                })
                if not source_url and slug:
                    source_url = f"http://www.runoob.com/{course_id}/{slug}.html"
                description = str(meta.get("description") or "").strip()
                source_line = f"> 来源: [{source_url}]({source_url})" if source_url else ""
                course["pages"].append({
                    "slug": slug,
                    "title": row.title or meta.get("title") or row.doc_id,
                    "summary": "\n\n".join(part for part in (description, source_line) if part),
                    "tags": list(meta.get("tags") or [course_id]),
                    "word_count": int(row.content_length or 0),
                })
                course["page_count"] += 1
            return list(grouped.values())
        except Exception as exc:
            logger.warning("Failed to load system courses from MySQL: %s", exc)
            return []

    def _has_db_courses(self) -> bool:
        try:
            from app.models import SessionLocal
            from app.models.knowledge_base import KnowledgeDocument
            with SessionLocal() as db:
                return db.query(KnowledgeDocument.id).filter(
                    KnowledgeDocument.user_id == SYSTEM_KB_USER_ID,
                ).first() is not None
        except Exception:
            return False

    def _course_records(self, kb_root: str) -> list[dict]:
        courses = self._load_db_courses()
        if courses:
            return courses
        records = []
        for filename in sorted(glob.glob(os.path.join(kb_root, "courses", "*.json"))):
            records.append(self._load_json(filename))
        return records

    async def execute(self, params: dict, sandbox_path: str) -> dict:
        operation = params.get("operation", "")
        kb_root = self._kb_path(sandbox_path)
        try:
            if operation == "search":
                return self._search(params, kb_root)
            if operation == "list_courses":
                return self._list_courses(kb_root)
            if operation == "get_course":
                return self._get_course(params, kb_root)
            if operation == "query_graph":
                return self._query_graph(params, kb_root)
            if operation == "get_rules":
                return self._get_rules(params, kb_root)
            if operation == "list_sources":
                return self._list_sources(kb_root)
            return {"success": False, "error": f"Unknown operation: {operation}"}
        except Exception as exc:
            logger.error("knowledge_search error: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}

    def search_sync(self, query: str, limit: int = 5, sandbox_path: str = "") -> dict:
        """Search project course data from synchronous orchestration nodes."""
        return self._search(
            {"query": query, "limit": limit},
            self._kb_path(sandbox_path),
        )

    def _search(self, params: dict, kb_root: str) -> dict:
        raw_query = params.get("query") or ""
        query = raw_query.strip()
        if not query:
            return {"success": False, "error": "query required"}

        db_courses = self._load_db_courses()
        courses_path = os.path.join(kb_root, "courses.json") if kb_root else ""
        if not db_courses and not os.path.exists(courses_path):
            return {
                "success": True,
                "results": [],
                "total_courses_with_matches": 0,
                "message": "No course data found",
            }

        limit = int(params.get("limit", 5))
        query_terms = self._expand_query_terms(query)
        results = []

        for course in db_courses or self._course_records(kb_root):
            course_id = str(course.get("id") or "unknown")
            scored_pages = []
            for page in course.get("pages", []):
                score = self._score_page(query, query_terms, course, page)
                if score > 0:
                    scored_pages.append((score, self._page_priority(page), page))

            scored_pages.sort(key=lambda item: (item[0], item[1]), reverse=True)
            if scored_pages:
                pages = [
                    {**page, "_search_score": score, "_search_priority": priority}
                    for score, priority, page in scored_pages[:limit]
                ]
                results.append({
                    "course_id": course_id,
                    "course_name": course.get("name", course_id),
                    "page_count": len(scored_pages),
                    "score": round(scored_pages[0][0], 3),
                    "pages": [
                        {
                            "slug": page.get("slug"),
                            "title": page.get("title"),
                            "summary": page.get("summary", "")[:150],
                            "score": page.get("_search_score", 0.0),
                            "priority": page.get("_search_priority", 0),
                        }
                        for page in pages
                    ],
                })

        results.sort(key=lambda item: (item.get("score", 0), item["page_count"]), reverse=True)
        return {
            "success": True,
            "results": results[:limit],
            "total_courses_with_matches": len(results),
            "query": raw_query,
        }

    def _list_courses(self, kb_root: str) -> dict:
        db_courses = self._load_db_courses()
        if db_courses:
            courses = [{
                "id": course["id"],
                "name": course.get("name", course["id"]),
                "page_count": course.get("page_count", 0),
            } for course in db_courses]
            return {
                "success": True,
                "courses": courses,
                "total": len(courses),
                "total_pages": sum(item["page_count"] for item in courses),
            }
        courses_path = os.path.join(kb_root, "courses.json")
        if os.path.exists(courses_path):
            index = self._load_json(courses_path)
            return {
                "success": True,
                "courses": index.get("courses", []),
                "total": index.get("total_courses", 0),
                "total_pages": index.get("total_pages", 0),
            }

        courses = []
        courses_dir = os.path.join(kb_root, "courses")
        for filename in sorted(glob.glob(os.path.join(courses_dir, "*.json"))):
            course = self._load_json(filename)
            courses.append({
                "id": course["id"],
                "name": course.get("name", course["id"]),
                "page_count": course.get("page_count", 0),
            })
        return {"success": True, "courses": courses, "total": len(courses)}

    def _get_course(self, params: dict, kb_root: str) -> dict:
        course_id = params.get("course_id", "")
        db_course = next(
            (course for course in self._load_db_courses() if course.get("id") == course_id),
            None,
        )
        if db_course:
            return {
                "success": True,
                "course": {
                    "id": db_course["id"],
                    "name": db_course.get("name"),
                    "page_count": db_course.get("page_count", 0),
                    "pages": db_course.get("pages", []),
                },
            }
        course_path = os.path.join(kb_root, "courses", f"{course_id}.json")
        if not os.path.exists(course_path):
            return {"success": False, "error": f"course {course_id} not found"}

        course = self._load_json(course_path)
        return {
            "success": True,
            "course": {
                "id": course["id"],
                "name": course.get("name"),
                "page_count": course.get("page_count", 0),
                "pages": [
                    {
                        "slug": page.get("slug"),
                        "title": page.get("title"),
                        "summary": page.get("summary", "")[:200],
                    }
                    for page in course.get("pages", [])
                ],
            },
        }

    def _query_graph(self, params: dict, kb_root: str) -> dict:
        graph_path = os.path.join(kb_root, "graph.json")
        if not os.path.exists(graph_path):
            return {"success": True, "nodes": [], "edges": []}

        graph = self._load_json(graph_path)
        query = (params.get("query") or "").lower()
        limit = int(params.get("limit", 5))
        nodes = graph.get("nodes", [])
        if query:
            nodes = [
                node
                for node in nodes
                if query in node.get("name", "").lower() or query in node.get("label", "").lower()
            ]
        return {
            "success": True,
            "nodes": nodes[:limit],
            "edges": graph.get("edges", [])[:limit],
            "total_nodes": len(nodes),
        }

    def _get_rules(self, params: dict, kb_root: str) -> dict:
        rules_path = os.path.join(kb_root, "rules.json")
        if not os.path.exists(rules_path):
            return {"success": True, "rules": [], "total": 0}

        data = self._load_json(rules_path)
        rules = data.get("rules", [])
        categories = params.get("rule_categories", [])
        if categories:
            rules = [rule for rule in rules if rule.get("category") in categories]
        return {
            "success": True,
            "rules": rules[: int(params.get("limit", 20))],
            "total": len(rules),
        }

    def _list_sources(self, kb_root: str) -> dict:
        result = {"doc_count": 0, "graph_nodes": 0, "rules_count": 0}

        db_courses = self._load_db_courses()
        if db_courses:
            result["courses"] = len(db_courses)
            result["pages"] = sum(course.get("page_count", 0) for course in db_courses)

        courses_path = os.path.join(kb_root, "courses.json")
        if os.path.exists(courses_path):
            index = self._load_json(courses_path)
            result["courses"] = index.get("total_courses", 0)
            result["pages"] = index.get("total_pages", 0)

        graph_path = os.path.join(kb_root, "graph.json")
        if os.path.exists(graph_path):
            result["graph_nodes"] = len(self._load_json(graph_path).get("nodes", []))

        rules_path = os.path.join(kb_root, "rules.json")
        if os.path.exists(rules_path):
            result["rules_count"] = len(self._load_json(rules_path).get("rules", []))

        return {"success": True, **result}
