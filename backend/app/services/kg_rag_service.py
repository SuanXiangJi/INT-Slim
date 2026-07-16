# -*- coding: utf-8 -*-
"""
KG + RAG Service - 知识图谱与向量检索服务

Provides:
1. Knowledge Graph: skill relationships, prerequisite chains
2. Vector Search: semantic search over KB content
3. Hybrid Retrieval: combine KG + vector for best results

Fallback to keyword/TF-IDF when vector DB is unavailable.
"""
from __future__ import annotations
import json
import logging
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from heapq import nlargest

logger = logging.getLogger(__name__)

# ── Data structures ──────────────────────────────────────────────────

@dataclass
class KGRelation:
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    relation: str  # prerequisite / next / related


@dataclass
class SearchHit:
    content: str
    score: float
    source: str  # course name
    title: str
    hit_type: str = "keyword"  # keyword / vector / hybrid


@dataclass
class RetrievalResult:
    hits: List[SearchHit] = field(default_factory=list)
    relations: List[KGRelation] = field(default_factory=list)
    total_hits: int = 0
    method: str = "keyword"


# ── TF-IDF Index (lightweight, no external deps) ────────────────────

class TfidfIndex:
    """Simple in-memory TF-IDF index over KB documents."""

    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.doc_count: int = 0
        self.df: Counter = Counter()  # document frequency
        self.term_doc_map: Dict[str, List[int]] = defaultdict(list)
        self._built = False

    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> None:
        idx = self.doc_count
        self.documents.append({"id": doc_id, "text": text, "metadata": metadata})
        terms = set(self._tokenize(text))
        for term in terms:
            self.df[term] += 1
            self.term_doc_map[term].append(idx)
        self.doc_count += 1

    def build(self) -> None:
        self._built = True
        logger.info("TF-IDF index built: %d documents, %d unique terms",
                    self.doc_count, len(self.df))

    def _tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        text = text.lower()
        # Chinese char bigrams + English words
        tokens = []
        # English words
        for w in re.findall(r"[a-zA-Z_]\w*", text):
            tokens.append(w)
        # Chinese characters as unigrams
        for ch in text:
            if "\u4e00" <= ch <= "\u9fff":
                tokens.append(ch)
        return tokens

    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        if not self._built or self.doc_count == 0:
            return []
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # Score documents by TF-IDF
        scores = Counter()
        for term in query_terms:
            if term not in self.df:
                continue
            idf = 1.0 + (self.doc_count / (1 + self.df[term]))
            for doc_idx in self.term_doc_map[term]:
                doc_text = self.documents[doc_idx]["text"].lower()
                tf = doc_text.count(term) / max(1, len(doc_text))
                scores[doc_idx] += tf * idf

        return nlargest(top_k, scores.items(), key=lambda x: x[1])


# ── Knowledge Graph Builder ─────────────────────────────────────────

class KnowledgeGraph:
    """In-memory knowledge graph of skill relations."""

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []

    def add_node(self, node_id: str, name: str, category: str = "",
                 description: str = "", difficulty: float = 0.5) -> None:
        self.nodes[node_id] = {
            "id": node_id, "name": name, "category": category,
            "description": description, "difficulty": difficulty,
        }

    def add_edge(self, source_id: str, target_id: str,
                 relation: str = "prerequisite") -> None:
        self.edges.append({
            "source": source_id, "target": target_id, "relation": relation,
        })

    def get_prerequisites(self, node_id: str) -> List[str]:
        return [e["source"] for e in self.edges
                if e["target"] == node_id and e["relation"] == "prerequisite"]

    def get_next_skills(self, node_id: str) -> List[str]:
        return [e["target"] for e in self.edges
                if e["source"] == node_id and e["relation"] == "prerequisite"]

    def find_path(self, target_id: str) -> List[str]:
        """BFS to find learning path to target."""
        from collections import deque
        if target_id not in self.nodes:
            return []
        visited = set()
        q = deque([(target_id, [target_id])])
        while q:
            current, path = q.popleft()
            if current in visited:
                continue
            visited.add(current)
            prereqs = self.get_prerequisites(current)
            if not prereqs:
                return path
            for p in prereqs:
                if p not in visited:
                    q.append((p, [p] + path))
        return []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
        }


# ── KG + RAG Service ────────────────────────────────────────────────

class KGRagService:
    """Main hybrid retrieval service combining KG + keyword search."""

    def __init__(self):
        self.tfidf = TfidfIndex()
        self.graph = KnowledgeGraph()
        self._initialized = False

    async def initialize(self, kb_path: str = "") -> None:
        """Load KB data and build indexes."""
        if self._initialized:
            return

        # 1. Build TF-IDF index from KB JSON files
        if kb_path and os.path.isdir(kb_path):
            courses_dir = os.path.join(kb_path, "courses")
            if os.path.isdir(courses_dir):
                import glob
                for fn in sorted(glob.glob(os.path.join(courses_dir, "*.json"))):
                    try:
                        with open(fn, "r", encoding="utf-8") as f:
                            course = json.load(f)
                        cid = course.get("id", "")
                        cname = course.get("name", "")
                        for page in course.get("pages", []):
                            text = f"{page.get('title', '')} {page.get('summary', '')} {page.get('content', '')}"
                            self.tfidf.add_document(
                                f"{cid}/{page.get('slug', '')}",
                                text,
                                {"course": cname, "title": page.get("title", ""), "slug": page.get("slug", "")})
                    except Exception as e:
                        logger.warning("Skipping %s: %s", fn, e)
                self.tfidf.build()

        # 2. Build KG from DB
        try:
            from app.models import SessionLocal
            db = SessionLocal()
            from app.crud.learning.knowledge_point import list_kps, get_prerequisites
            from app.crud.learning.course import list_courses

            kps = list_kps(db)
            for kp in kps:
                self.graph.add_node(kp.id, kp.name, kp.category or "",
                                    kp.description or "", kp.difficulty)

            for kp in kps:
                prereqs = get_prerequisites(db, kp.id)
                for p in prereqs:
                    if p:
                        self.graph.add_edge(p.id, kp.id, "prerequisite")

            db.close()
            logger.info("KG built: %d nodes, %d edges", len(self.graph.nodes), len(self.graph.edges))
        except Exception as e:
            logger.warning("Could not build KG from DB: %s", e)

        self._initialized = True

    async def search(self, query: str, top_k: int = 5) -> RetrievalResult:
        """Hybrid search: keyword + KG relations."""
        if not self._initialized:
            return RetrievalResult()

        result = RetrievalResult()

        # 1. TF-IDF keyword search
        scored = self.tfidf.search(query, top_k)
        for doc_idx, score in scored:
            doc = self.tfidf.documents[doc_idx]
            result.hits.append(SearchHit(
                content=doc["text"][:300],
                score=score,
                source=doc["metadata"].get("course", ""),
                title=doc["metadata"].get("title", ""),
                hit_type="keyword",
            ))
        result.total_hits = len(result.hits)

        # 2. KG: find related nodes
        query_lower = query.lower()
        for nid, node in self.graph.nodes.items():
            if query_lower in node["name"].lower():
                prereqs = self.graph.get_prerequisites(nid)
                nexts = self.graph.get_next_skills(nid)
                for pid in prereqs:
                    if pid in self.graph.nodes:
                        pn = self.graph.nodes[pid]
                        result.relations.append(KGRelation(
                            pid, pn["name"], nid, node["name"], "prerequisite"))
                for nid2 in nexts:
                    if nid2 in self.graph.nodes:
                        nn = self.graph.nodes[nid2]
                        result.relations.append(KGRelation(
                            nid, node["name"], nid2, nn["name"], "next"))

        result.method = "hybrid" if result.hits else "keyword"
        return result


# ── Singleton ──
_kg_rag_service: Optional[KGRagService] = None


def get_kg_rag_service() -> KGRagService:
    global _kg_rag_service
    if _kg_rag_service is None:
        _kg_rag_service = KGRagService()
    return _kg_rag_service