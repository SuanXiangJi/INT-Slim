# -*- coding: utf-8 -*-
"""
RAG service
===========

User-scoped knowledge base with a dependency-light hybrid retriever:

- sentence-aware chunking with overlap
- BM25 lexical retrieval
- character n-gram similarity for Chinese/English fuzzy matching
- phrase and metadata boosts
- reciprocal-rank fusion
- MMR reranking to reduce duplicate chunks
- optional neighboring chunk expansion for better answer context

The storage format stays compatible with the previous JSON index.
"""
from __future__ import annotations

import json
import logging
import math
import pickle
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


KB_ROOT = Path(__file__).parent.parent.parent / "sandbox" / "kb"
CHROMA_ROOT = Path(__file__).parent.parent.parent / "sandbox" / "chroma"


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
_WORD_RE = re.compile(r"[a-zA-Z0-9_]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\u3002\uff01\uff1f!?;\uff1b\n])")


class DocumentChunk:
    """A chunk of a document with metadata."""

    def __init__(
        self,
        doc_id: str,
        chunk_id: int,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.doc_id = doc_id
        self.chunk_id = chunk_id
        self.content = content
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "content": self.content,
            "metadata": self.metadata,
        }


class KnowledgeBase:
    """User-scoped knowledge base backed by MySQL and indexed by Chroma."""

    CHUNK_SIZE = 900
    CHUNK_OVERLAP = 140
    BM25_K1 = 1.5
    BM25_B = 0.75
    RRF_K = 60

    def __init__(self, user_id: bytes):
        self.user_id = user_id
        self.kb_dir = KB_ROOT / self._user_id_hex()
        self.index_file = self.kb_dir / "index.json"
        self.docs_file = self.kb_dir / "documents.json"
        self.retrieval_index_file = self.kb_dir / "retrieval_index.pkl"
        self.chunks: List[DocumentChunk] = []
        self.documents: Dict[str, Dict[str, Any]] = {}
        self._retrieval_index: Optional[Dict[str, Any]] = None
        self._load()
        self._chroma_collection = None
        # Do not migrate legacy documents here. Chroma's default embedding
        # function can load a sizeable model, and doing that on a chat request
        # blocks the first response for an unbounded amount of time.

    def _user_id_hex(self) -> str:
        import binascii

        return binascii.hexlify(self.user_id).decode("ascii")

    def _load(self) -> None:
        """Load canonical documents and chunks from MySQL, with legacy fallback."""
        try:
            from app.models import SessionLocal
            from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument

            with SessionLocal() as db:
                doc_rows = db.query(KnowledgeDocument).filter(
                    KnowledgeDocument.user_id == self.user_id,
                ).all()
                self.documents = {
                    row.doc_id: {
                        "doc_id": row.doc_id,
                        "content_length": int(row.content_length or 0),
                        "chunk_count": int(row.chunk_count or 0),
                        "metadata": row.doc_metadata or {},
                        "added_at": (row.added_at or row.updated_at or datetime.now()).isoformat(),
                    }
                    for row in doc_rows
                }
                chunk_rows = db.query(KnowledgeChunk).filter(
                    KnowledgeChunk.user_id == self.user_id,
                ).order_by(KnowledgeChunk.doc_id, KnowledgeChunk.chunk_id).all()
                self.chunks = [
                    DocumentChunk(row.doc_id, row.chunk_id, row.content, row.chunk_metadata or {})
                    for row in chunk_rows
                ]
        except Exception as e:
            logger.error("Failed to load KB from MySQL: %s", e)
            self.documents = {}
            self.chunks = []

        # This fallback is removed naturally after the one-time migration.
        if not self.chunks and self.index_file.exists():
            try:
                self.chunks = [
                    DocumentChunk(**item)
                    for item in json.loads(self.index_file.read_text(encoding="utf-8"))
                ]
            except Exception as e:
                logger.warning("Failed to load legacy KB chunks: %s", e)
        if not self.documents and self.docs_file.exists():
            try:
                self.documents = json.loads(self.docs_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Failed to load legacy KB documents: %s", e)
        self._retrieval_index = None

    def _persist_document(self, doc_id: str, chunks: List[DocumentChunk]) -> None:
        from app.models import SessionLocal
        from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument

        doc = self.documents[doc_id]
        metadata = doc.get("metadata") or {}
        with SessionLocal() as db:
            row = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.user_id == self.user_id,
                KnowledgeDocument.doc_id == doc_id,
            ).first() or KnowledgeDocument(user_id=self.user_id, doc_id=doc_id)
            db.add(row)
            row.title = str(metadata.get("title") or metadata.get("source") or doc_id)[:255]
            row.category = str(metadata.get("category") or "")[:128] or None
            row.source_type = str(metadata.get("source_type") or "")[:64] or None
            row.content_length = int(doc.get("content_length") or 0)
            row.chunk_count = len(chunks)
            row.doc_metadata = metadata
            try:
                row.added_at = datetime.fromisoformat(doc.get("added_at") or "")
            except ValueError:
                row.added_at = datetime.now()
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.user_id == self.user_id,
                KnowledgeChunk.doc_id == doc_id,
            ).delete(synchronize_session=False)
            db.add_all([
                KnowledgeChunk(
                    user_id=self.user_id,
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    chunk_metadata=chunk.metadata,
                )
                for chunk in chunks
            ])
            db.commit()

    def _invalidate(self, drop_persisted: bool = False) -> None:
        self._retrieval_index = None
        if drop_persisted and self.retrieval_index_file.exists():
            try:
                self.retrieval_index_file.unlink()
            except OSError as e:
                logger.warning("Failed to remove persisted RAG index: %s", e)

    def _collection_name(self) -> str:
        return f"xbots_kb_{self._user_id_hex()}"

    def _collection(self):
        if self._chroma_collection is not None:
            return self._chroma_collection
        try:
            import chromadb

            CHROMA_ROOT.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(CHROMA_ROOT))
            self._chroma_collection = client.get_or_create_collection(
                name=self._collection_name(),
                metadata={"hnsw:space": "cosine"},
            )
            return self._chroma_collection
        except Exception as e:
            logger.error("Failed to initialize Chroma collection: %s", e)
            raise

    @staticmethod
    def _point_id(doc_id: str, chunk_id: int) -> str:
        safe_doc_id = re.sub(r"[^a-zA-Z0-9_.:-]", "_", doc_id)
        return f"{safe_doc_id}::{chunk_id}"

    @staticmethod
    def _flatten_metadata(doc_id: str, chunk_id: int, metadata: Dict[str, Any]) -> Dict[str, Any]:
        meta = metadata or {}
        return {
            "doc_id": doc_id,
            "chunk_id": int(chunk_id),
            "title": str(meta.get("title") or meta.get("source") or doc_id),
            "category": str(meta.get("category") or ""),
            "source_type": str(meta.get("source_type") or ""),
            "metadata_json": json.dumps(meta, ensure_ascii=False),
        }

    def _delete_chroma_doc(self, doc_id: str) -> None:
        try:
            self._collection().delete(where={"doc_id": doc_id})
        except Exception as e:
            logger.warning("Failed to delete Chroma doc %s: %s", doc_id, e)

    def _upsert_chroma_chunks(self, chunks: List[DocumentChunk]) -> None:
        if not chunks:
            return
        try:
            collection = self._collection()
            for start in range(0, len(chunks), 256):
                batch = chunks[start:start + 256]
                collection.upsert(
                    ids=[self._point_id(c.doc_id, c.chunk_id) for c in batch],
                    documents=[c.content for c in batch],
                    metadatas=[self._flatten_metadata(c.doc_id, c.chunk_id, c.metadata) for c in batch],
                )
        except Exception as e:
            logger.error("Failed to upsert Chroma chunks: %s", e)
            raise

    def _ensure_chroma_synced(self) -> None:
        """Migrate legacy JSON chunks into Chroma if the collection is empty."""
        if not self.chunks:
            return
        try:
            collection = self._collection()
            if collection.count() < len(self.chunks):
                self._upsert_chroma_chunks(self.chunks)
        except Exception as e:
            logger.warning("Failed to sync legacy KB into Chroma: %s", e)

    def _source_version(self) -> float:
        """Cheap content signature used only to validate the local search cache."""
        return float(sum(len(chunk.content) for chunk in self.chunks))

    @staticmethod
    def _normalize(text: str) -> str:
        text = (text or "").lower()
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        """Tokenize Chinese and English into retrieval-friendly features."""
        normalized = cls._normalize(text)
        tokens: List[str] = []

        for match in _WORD_RE.finditer(normalized):
            word = match.group(0)
            tokens.append(word)
            if len(word) > 4:
                for i in range(len(word) - 2):
                    tokens.append(word[i : i + 3])

        for match in _CJK_RE.finditer(normalized):
            chars = match.group(0)
            tokens.extend(chars)
            for n in (2, 3):
                if len(chars) >= n:
                    tokens.extend(chars[i : i + n] for i in range(len(chars) - n + 1))

        return tokens

    @classmethod
    def _semantic_features(cls, text: str) -> Counter:
        """Character n-gram features used as a lightweight semantic fallback."""
        normalized = re.sub(r"\s+", "", cls._normalize(text))
        features: Counter = Counter(cls._tokenize(text))
        for n in (2, 3, 4):
            if len(normalized) >= n:
                features.update(normalized[i : i + n] for i in range(len(normalized) - n + 1))
        return features

    @staticmethod
    def _cosine(a: Counter, b: Counter) -> float:
        if not a or not b:
            return 0.0
        if len(a) > len(b):
            a, b = b, a
        dot = sum(value * b.get(key, 0.0) for key, value in a.items())
        if dot <= 0:
            return 0.0
        norm_a = math.sqrt(sum(value * value for value in a.values()))
        norm_b = math.sqrt(sum(value * value for value in b.values()))
        return float(dot / (norm_a * norm_b)) if norm_a and norm_b else 0.0

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into sentence-aware chunks with a small overlap."""
        text = re.sub(r"\r\n?", "\n", text or "").strip()
        if not text:
            return []

        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
        chunks: List[str] = []
        current = ""

        for sentence in sentences:
            if not current:
                current = sentence
                continue
            if len(current) + 1 + len(sentence) <= self.CHUNK_SIZE:
                current = current + "\n" + sentence
            else:
                chunks.extend(self._split_long_chunk(current))
                overlap = current[-self.CHUNK_OVERLAP :] if self.CHUNK_OVERLAP else ""
                current = (overlap + "\n" + sentence).strip()

        if current:
            chunks.extend(self._split_long_chunk(current))
        return [chunk for chunk in chunks if chunk.strip()]

    def _split_long_chunk(self, text: str) -> List[str]:
        if len(text) <= self.CHUNK_SIZE:
            return [text]
        chunks = []
        start = 0
        step = max(1, self.CHUNK_SIZE - self.CHUNK_OVERLAP)
        while start < len(text):
            chunk = text[start : start + self.CHUNK_SIZE].strip()
            if chunk:
                chunks.append(chunk)
            start += step
        return chunks

    def add_document(self, doc_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """Add or replace a document. Returns chunk count."""
        self.chunks = [c for c in self.chunks if c.doc_id != doc_id]
        self._delete_chroma_doc(doc_id)

        text_chunks = self._chunk_text(content)
        new_chunks: List[DocumentChunk] = []
        for i, chunk_text in enumerate(text_chunks):
            new_chunks.append(
                DocumentChunk(doc_id=doc_id, chunk_id=i, content=chunk_text, metadata=metadata or {})
            )
        self.chunks.extend(new_chunks)

        self.documents[doc_id] = {
            "doc_id": doc_id,
            "content_length": len(content),
            "chunk_count": len(text_chunks),
            "metadata": metadata or {},
            "added_at": datetime.now().isoformat(),
        }
        self._persist_document(doc_id, new_chunks)
        self._upsert_chroma_chunks(new_chunks)
        self._invalidate(drop_persisted=True)
        return len(text_chunks)

    def delete_document(self, doc_id: str) -> bool:
        """Remove a document."""
        if doc_id not in self.documents:
            return False
        self.chunks = [c for c in self.chunks if c.doc_id != doc_id]
        del self.documents[doc_id]
        from app.models import SessionLocal
        from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument
        with SessionLocal() as db:
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.user_id == self.user_id,
                KnowledgeChunk.doc_id == doc_id,
            ).delete(synchronize_session=False)
            db.query(KnowledgeDocument).filter(
                KnowledgeDocument.user_id == self.user_id,
                KnowledgeDocument.doc_id == doc_id,
            ).delete(synchronize_session=False)
            db.commit()
        self._delete_chroma_doc(doc_id)
        self._invalidate(drop_persisted=True)
        return True

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all documents."""
        return list(self.documents.values())

    def _build_retrieval_index(self) -> Dict[str, Any]:
        if self._retrieval_index is not None:
            return self._retrieval_index
        persisted = self._load_persisted_retrieval_index()
        if persisted is not None:
            self._retrieval_index = persisted
            return persisted

        postings: Dict[str, Dict[int, int]] = {}
        lengths: List[int] = []

        for index, chunk in enumerate(self.chunks):
            full_text = self._chunk_full_text(chunk)
            tokens = self._tokenize(full_text)
            counts = Counter(tokens)
            lengths.append(len(tokens))
            for token, tf in counts.items():
                postings.setdefault(token, {})[index] = int(tf)

        total = max(1, len(self.chunks))
        avg_len = sum(lengths) / total if lengths else 0.0
        idf = {
            token: math.log(1 + (total - freq + 0.5) / (freq + 0.5))
            for token, freq in ((token, len(docs)) for token, docs in postings.items())
        }

        by_doc: Dict[str, Dict[int, int]] = {}
        for index, chunk in enumerate(self.chunks):
            by_doc.setdefault(chunk.doc_id, {})[chunk.chunk_id] = index

        self._retrieval_index = {
            "postings": postings,
            "idf": idf,
            "lengths": lengths,
            "avg_len": avg_len,
            "by_doc": by_doc,
        }
        self._save_persisted_retrieval_index(self._retrieval_index)
        return self._retrieval_index

    def _load_persisted_retrieval_index(self) -> Optional[Dict[str, Any]]:
        if not self.retrieval_index_file.exists():
            return None
        try:
            with open(self.retrieval_index_file, "rb") as file:
                payload = pickle.load(file)
            if payload.get("chunk_count") != len(self.chunks):
                return None
            if payload.get("source_version") != self._source_version():
                return None
            index = payload.get("index")
            return index if isinstance(index, dict) and "postings" in index else None
        except Exception as e:
            logger.warning("Failed to load persisted RAG index: %s", e)
            return None

    def _save_persisted_retrieval_index(self, index: Dict[str, Any]) -> None:
        try:
            self.kb_dir.mkdir(parents=True, exist_ok=True)
            with open(self.retrieval_index_file, "wb") as file:
                pickle.dump({
                    "version": 3,
                    "chunk_count": len(self.chunks),
                    "source_version": self._source_version(),
                    "index": index,
                }, file, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            logger.warning("Failed to persist RAG index: %s", e)

    @staticmethod
    def _chunk_full_text(chunk: DocumentChunk) -> str:
        metadata_text = " ".join(str(v) for v in (chunk.metadata or {}).values() if v is not None)
        return f"{chunk.content}\n{metadata_text}"

    def _bm25_scores(
        self,
        query_terms: Iterable[str],
        index: Dict[str, Any],
        candidate_ids: Optional[Iterable[int]] = None,
    ) -> Dict[int, float]:
        query_counts = Counter(query_terms)
        scores: Dict[int, float] = {}
        avg_len = index["avg_len"] or 1.0

        candidate_set = set(candidate_ids) if candidate_ids is not None else None
        for term, query_tf in query_counts.items():
            posting = index["postings"].get(term)
            if not posting:
                continue
            idf = index["idf"].get(term, 0.0)
            query_weight = 1 + math.log(query_tf)
            for i, tf in posting.items():
                if candidate_set is not None and i not in candidate_set:
                    continue
                doc_len = index["lengths"][i] or 1
                denom = tf + self.BM25_K1 * (1 - self.BM25_B + self.BM25_B * doc_len / avg_len)
                scores[i] = scores.get(i, 0.0) + float(
                    idf * (tf * (self.BM25_K1 + 1) / denom) * query_weight
                )
        return scores

    def _phrase_score(self, query: str, chunk: DocumentChunk) -> float:
        normalized_query = self._normalize(query)
        normalized_content = self._normalize(chunk.content)
        metadata = chunk.metadata or {}
        metadata_text = self._normalize(" ".join(str(v) for v in metadata.values() if v is not None))

        score = 0.0
        if normalized_query and normalized_query in normalized_content:
            score += 2.5
        if normalized_query and normalized_query in metadata_text:
            score += 1.5

        terms = [t for t in set(self._tokenize(query)) if len(t) > 1]
        if terms:
            content_hits = sum(1 for term in terms if term in normalized_content)
            metadata_hits = sum(1 for term in terms if term in metadata_text)
            score += content_hits / len(terms)
            score += 0.6 * metadata_hits / len(terms)
        return float(score)

    def _rank_by_score(self, scores: Dict[int, float]) -> List[int]:
        return [idx for idx, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]

    def _rrf(self, rankings: List[List[int]]) -> Dict[int, float]:
        fused: Dict[int, float] = {}
        for ranking in rankings:
            for rank, idx in enumerate(ranking, start=1):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (self.RRF_K + rank)
        return fused

    def _mmr(
        self,
        candidate_ids: List[int],
        relevance: Dict[int, float],
        vectors: Dict[int, Counter],
        top_k: int,
        diversity: float,
    ) -> List[int]:
        selected: List[int] = []
        remaining = list(candidate_ids)

        while remaining and len(selected) < top_k:
            best_id = remaining[0]
            best_score = -float("inf")
            for idx in remaining:
                redundancy = max((self._cosine(vectors[idx], vectors[s]) for s in selected), default=0.0)
                score = diversity * relevance.get(idx, 0.0) - (1 - diversity) * redundancy
                if score > best_score:
                    best_score = score
                    best_id = idx
            selected.append(best_id)
            remaining.remove(best_id)
        return selected

    def _expanded_content(self, idx: int, max_chars: int = 1800) -> Tuple[str, List[int]]:
        """Attach neighboring chunks from the same doc when space allows."""
        chunk = self.chunks[idx]
        index = self._build_retrieval_index()
        doc_map = index["by_doc"].get(chunk.doc_id, {})
        pieces: List[Tuple[int, str]] = [(chunk.chunk_id, chunk.content)]

        for neighbor_id in (chunk.chunk_id - 1, chunk.chunk_id + 1):
            neighbor_idx = doc_map.get(neighbor_id)
            if neighbor_idx is None:
                continue
            neighbor = self.chunks[neighbor_idx]
            merged_len = sum(len(piece) for _, piece in pieces) + len(neighbor.content)
            if merged_len <= max_chars:
                pieces.append((neighbor.chunk_id, neighbor.content))

        pieces.sort(key=lambda item: item[0])
        content = "\n\n".join(piece for _, piece in pieces)
        return content[:max_chars], [chunk_id for chunk_id, _ in pieces]

    def _search_lexical(self, query: str, top_k: int, candidate_k: int, mmr_lambda: float) -> List[Dict[str, Any]]:
        """Fast hybrid fallback used until a Chroma collection is already warm."""
        index = self._build_retrieval_index()
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        bm25 = self._bm25_scores(query_terms, index)
        candidate_ids = self._rank_by_score(bm25)[:max(candidate_k, top_k)]
        if not candidate_ids:
            return []

        query_vector = self._semantic_features(query)
        vectors = {
            idx: self._semantic_features(self._chunk_full_text(self.chunks[idx]))
            for idx in candidate_ids
        }
        semantic = {idx: self._cosine(query_vector, vector) for idx, vector in vectors.items()}
        phrase = {idx: self._phrase_score(query, self.chunks[idx]) for idx in candidate_ids}
        rankings = [
            self._rank_by_score({idx: bm25.get(idx, 0.0) for idx in candidate_ids}),
            self._rank_by_score(semantic),
            self._rank_by_score(phrase),
        ]
        relevance = self._rrf(rankings)
        selected = self._mmr(candidate_ids, relevance, vectors, top_k, mmr_lambda)
        rrf_max = len(rankings) / (self.RRF_K + 1)

        results = []
        for idx in selected:
            chunk = self.chunks[idx]
            content, expanded_chunk_ids = self._expanded_content(idx)
            results.append({
                "doc_id": chunk.doc_id,
                "chunk_id": chunk.chunk_id,
                "content": content,
                "score": round(min(1.0, relevance.get(idx, 0.0) / rrf_max), 6),
                "score_type": "normalized_rrf",
                "bm25_score": round(bm25.get(idx, 0.0), 6),
                "semantic_score": round(semantic.get(idx, 0.0), 6),
                "phrase_score": round(phrase.get(idx, 0.0), 6),
                "expanded_chunk_ids": expanded_chunk_ids,
                "metadata": chunk.metadata,
            })
        return results

    def search(
        self,
        query: str,
        top_k: int = 3,
        *,
        candidate_k: int = 40,
        expand_neighbors: bool = True,
        mmr_lambda: float = 0.72,
    ) -> List[Dict[str, Any]]:
        """Search the knowledge base without making chat wait for Chroma warmup."""
        query = (query or "").strip()
        if not self.chunks or not query:
            return []

        # A collection created during document import is safe to use directly.
        # Legacy JSON documents use the persisted hybrid index on the first
        # chat request instead of triggering a full vector migration.
        try:
            collection = self._collection()
            if collection.count() != len(self.chunks):
                return self._search_lexical(query, top_k, candidate_k, mmr_lambda)
            raw = collection.query(
                query_texts=[query],
                n_results=max(top_k, 1),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error("Chroma search failed: %s", e)
            return self._search_lexical(query, top_k, candidate_k, mmr_lambda)

        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        by_doc_chunk = {(c.doc_id, c.chunk_id): idx for idx, c in enumerate(self.chunks)}
        results = []
        for result_id, content, metadata, distance in zip(ids, documents, metadatas, distances):
            metadata = metadata or {}
            doc_id = str(metadata.get("doc_id") or "").strip()
            chunk_id = int(metadata.get("chunk_id") or 0)
            idx = by_doc_chunk.get((doc_id, chunk_id))
            expanded_chunk_ids = [chunk_id]
            final_content = content or ""
            if idx is not None and expand_neighbors:
                final_content, expanded_chunk_ids = self._expanded_content(idx)

            try:
                original_metadata = json.loads(metadata.get("metadata_json") or "{}")
            except Exception:
                original_metadata = {
                    "title": metadata.get("title"),
                    "category": metadata.get("category"),
                    "source_type": metadata.get("source_type"),
                }

            score = 1.0 / (1.0 + float(distance or 0.0))
            results.append({
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "content": final_content,
                "score": round(score, 6),
                "score_type": "chroma_cosine",
                "bm25_score": 0.0,
                "semantic_score": round(score, 6),
                "phrase_score": 0.0,
                "expanded_chunk_ids": expanded_chunk_ids,
                "metadata": original_metadata,
            })
        return results

    def clear(self) -> None:
        """Remove all documents."""
        from app.models import SessionLocal
        from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument
        with SessionLocal() as db:
            db.query(KnowledgeChunk).filter(KnowledgeChunk.user_id == self.user_id).delete(synchronize_session=False)
            db.query(KnowledgeDocument).filter(KnowledgeDocument.user_id == self.user_id).delete(synchronize_session=False)
            db.commit()
        self.chunks = []
        self.documents = {}
        self._invalidate(drop_persisted=True)


_kb_cache: Dict[str, KnowledgeBase] = {}


def get_kb(user_id: bytes) -> KnowledgeBase:
    """Get or create KB for a user."""
    import binascii

    uid_hex = binascii.hexlify(user_id).decode("ascii") if user_id else "anonymous"
    if uid_hex not in _kb_cache:
        _kb_cache[uid_hex] = KnowledgeBase(user_id or b"anonymous")
    return _kb_cache[uid_hex]


def format_retrieval_context(results: List[Dict[str, Any]], max_chars: int = 7000) -> str:
    """Format retrieval results for LLM context with compact source metadata."""
    if not results:
        return ""

    parts = [
        "[Knowledge Base Context]",
        "Use these retrieved sources when they are relevant. Prefer them over memory.",
    ]
    used_chars = sum(len(part) for part in parts)

    for i, result in enumerate(results, 1):
        meta = result.get("metadata", {}) or {}
        source = meta.get("title") or meta.get("source") or result.get("doc_id", "unknown")
        category = meta.get("category")
        header = (
            f"\n--- Source {i}: {source}"
            f" | doc_id={result.get('doc_id')}"
            f" | chunk={result.get('chunk_id')}"
            f" | relevance={round(float(result.get('score', 0.0)), 3)}"
        )
        if category:
            header += f" | category={category}"
        header += " ---\n"

        content = str(result.get("content", "")).strip()
        remaining = max_chars - used_chars - len(header) - len("\n[End Knowledge Base Context]")
        if remaining <= 0:
            break
        if len(content) > remaining:
            content = content[:remaining].rstrip() + "\n...[truncated]"

        parts.append(header + content)
        used_chars += len(header) + len(content)

    parts.append("\n[End Knowledge Base Context]")
    return "\n".join(parts)
