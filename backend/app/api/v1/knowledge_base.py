# -*- coding: utf-8 -*-
"""Knowledge Base (RAG) API endpoints - frontend can call these directly."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime

from app.models import get_db
from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument
from app.schemas.user import User as UserSchema
from app.dependencies.auth import get_current_user
from app.utils.uuid import uuid_string_to_bytes
from app.services.rag_service import get_kb
from app.services.knowledge_scope import (
    SYSTEM_KB_USER_ID,
    knowledge_scope,
    readable_owner_ids,
    resolve_document_owner,
)

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


class DocumentCreate(BaseModel):
    doc_id: Optional[str] = None
    content: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None


class DocumentInfo(BaseModel):
    doc_id: str
    content_length: int
    chunk_count: int
    metadata: Dict[str, Any]
    added_at: str
    scope: str = "private"
    read_only: bool = False


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(3, ge=1, le=10)


class SearchHit(BaseModel):
    doc_id: str
    chunk_id: int
    content: str
    score: float
    bm25_score: Optional[float] = None
    semantic_score: Optional[float] = None
    phrase_score: Optional[float] = None
    expanded_chunk_ids: Optional[List[int]] = None
    metadata: Dict[str, Any]


def _parse_added_at(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _document_info_from_row(row: KnowledgeDocument, user_id: bytes) -> DocumentInfo:
    scope = knowledge_scope(row.user_id, user_id)
    return DocumentInfo(
        doc_id=row.doc_id,
        content_length=row.content_length or 0,
        chunk_count=row.chunk_count or 0,
        metadata=row.doc_metadata or {},
        added_at=(row.added_at or row.updated_at or datetime.utcnow()).isoformat(),
        scope=scope,
        read_only=scope == "public",
    )


def _sync_document_to_db(db: Session, user_id: bytes, kb, doc_id: str) -> None:
    doc = kb.documents.get(doc_id)
    if not doc:
        return
    meta = doc.get("metadata", {}) or {}
    row = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.user_id == user_id,
        KnowledgeDocument.doc_id == doc_id,
    ).first()
    if not row:
        row = KnowledgeDocument(user_id=user_id, doc_id=doc_id)
        db.add(row)
    row.title = str(meta.get("title") or meta.get("source") or doc_id)[:255]
    row.category = str(meta.get("category") or "")[:128] or None
    row.source_type = str(meta.get("source_type") or "")[:64] or None
    row.content_length = int(doc.get("content_length") or 0)
    row.chunk_count = int(doc.get("chunk_count") or 0)
    row.doc_metadata = meta
    row.added_at = _parse_added_at(doc.get("added_at"))

    db.query(KnowledgeChunk).filter(
        KnowledgeChunk.user_id == user_id,
        KnowledgeChunk.doc_id == doc_id,
    ).delete(synchronize_session=False)
    for chunk in [c for c in kb.chunks if c.doc_id == doc_id]:
        db.add(KnowledgeChunk(
            user_id=user_id,
            doc_id=doc_id,
            chunk_id=chunk.chunk_id,
            content=chunk.content,
            chunk_metadata=chunk.metadata or {},
        ))
    db.commit()


def _sync_legacy_kb_to_db(db: Session, user_id: bytes, kb) -> None:
    existing = {
        row.doc_id
        for row in db.query(KnowledgeDocument.doc_id).filter(KnowledgeDocument.user_id == user_id).all()
    }
    missing = [doc_id for doc_id in kb.documents.keys() if doc_id not in existing]
    for doc_id in missing:
        _sync_document_to_db(db, user_id, kb, doc_id)


def _search_public_documents(
    db: Session,
    query: str,
    top_k: int,
    excluded_doc_ids: set[str],
) -> List[Dict[str, Any]]:
    """Search the shared catalog in MySQL without loading every public chunk."""
    keyword = query.strip()
    pattern = f"%{keyword}%"
    rows = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.user_id == SYSTEM_KB_USER_ID,
        KnowledgeDocument.content_length > 0,
        or_(
            KnowledgeDocument.title.like(pattern),
            KnowledgeDocument.category.like(pattern),
        ),
    ).order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())\
        .limit(max(top_k * 4, top_k)).all()

    documents = {row.doc_id: row for row in rows if row.doc_id not in excluded_doc_ids}
    if len(documents) < top_k:
        chunk_rows = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.user_id == SYSTEM_KB_USER_ID,
            KnowledgeChunk.content.like(pattern),
        ).order_by(KnowledgeChunk.id.asc()).limit(max(top_k * 4, top_k)).all()
        missing_ids = {
            row.doc_id for row in chunk_rows
            if row.doc_id not in documents and row.doc_id not in excluded_doc_ids
        }
        if missing_ids:
            for row in db.query(KnowledgeDocument).filter(
                KnowledgeDocument.user_id == SYSTEM_KB_USER_ID,
                KnowledgeDocument.doc_id.in_(missing_ids),
            ).all():
                documents[row.doc_id] = row

    doc_ids = list(documents)[:max(top_k * 2, top_k)]
    first_chunks: Dict[str, KnowledgeChunk] = {}
    if doc_ids:
        for chunk in db.query(KnowledgeChunk).filter(
            KnowledgeChunk.user_id == SYSTEM_KB_USER_ID,
            KnowledgeChunk.doc_id.in_(doc_ids),
        ).order_by(KnowledgeChunk.doc_id.asc(), KnowledgeChunk.chunk_id.asc()).all():
            first_chunks.setdefault(chunk.doc_id, chunk)

    normalized_query = keyword.lower()
    results = []
    for rank, doc_id in enumerate(doc_ids, start=1):
        row = documents[doc_id]
        chunk = first_chunks.get(doc_id)
        if not chunk:
            continue
        title = str(row.title or "")
        category = str(row.category or "")
        if title.lower() == normalized_query:
            score = 0.95
        elif normalized_query in title.lower():
            score = 0.88
        elif normalized_query in category.lower():
            score = 0.72
        else:
            score = 0.6
        score = max(0.3, score - (rank - 1) * 0.01)
        metadata = dict(row.doc_metadata or chunk.chunk_metadata or {})
        metadata.update({
            "title": metadata.get("title") or title or doc_id,
            "category": metadata.get("category") or category,
            "knowledge_scope": "public",
        })
        results.append({
            "doc_id": doc_id,
            "chunk_id": chunk.chunk_id,
            "content": chunk.content,
            "score": round(score, 6),
            "bm25_score": 0.0,
            "semantic_score": 0.0,
            "phrase_score": round(score, 6),
            "expanded_chunk_ids": [chunk.chunk_id],
            "metadata": metadata,
        })
        if len(results) >= top_k:
            break
    return results


@router.post("/documents", response_model=DocumentInfo)
def add_document(
    doc: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Add a document to user's knowledge base."""
    user_id = uuid_string_to_bytes(current_user.id)
    kb = get_kb(user_id)

    # Validate content is not whitespace-only
    if not doc.content or not doc.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty or whitespace")

    # Limit content size (10MB max)
    if len(doc.content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Content too large (max 10MB)")

    import uuid as uuid_mod
    doc_id = doc.doc_id or uuid_mod.uuid4().hex

    chunks_added = kb.add_document(doc_id, doc.content.strip(), doc.metadata or {})
    info = kb.list_documents()
    for d in info:
        if d["doc_id"] == doc_id:
            return DocumentInfo(**d)
    raise HTTPException(status_code=500, detail="Failed to retrieve document info")


@router.get("/documents", response_model=List[DocumentInfo])
def list_documents(
    include_public: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """List all documents in user's knowledge base."""
    user_id = uuid_string_to_bytes(current_user.id)
    owner_ids = readable_owner_ids(user_id) if include_public else (user_id,)
    rows = db.query(KnowledgeDocument).filter(KnowledgeDocument.user_id.in_(owner_ids))\
        .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc()).limit(limit).all()
    if not rows:
        kb = get_kb(user_id)
        _sync_legacy_kb_to_db(db, user_id, kb)
        rows = db.query(KnowledgeDocument).filter(KnowledgeDocument.user_id.in_(owner_ids))\
            .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc()).limit(limit).all()
    seen = set()
    result = []
    for row in sorted(rows, key=lambda item: item.user_id != user_id):
        if row.doc_id in seen:
            continue
        seen.add(row.doc_id)
        result.append(_document_info_from_row(row, user_id))
    return result


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Delete a document."""
    user_id = uuid_string_to_bytes(current_user.id)
    kb = get_kb(user_id)
    if kb.delete_document(doc_id):
        db.query(KnowledgeChunk).filter(KnowledgeChunk.user_id == user_id, KnowledgeChunk.doc_id == doc_id).delete(synchronize_session=False)
        db.query(KnowledgeDocument).filter(KnowledgeDocument.user_id == user_id, KnowledgeDocument.doc_id == doc_id).delete(synchronize_session=False)
        db.commit()
        return {"deleted": doc_id}
    raise HTTPException(status_code=404, detail="Document not found")


@router.post("/search", response_model=List[SearchHit])
def search(
    req: SearchRequest,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Search the user's private knowledge base and the shared public library."""
    user_id = uuid_string_to_bytes(current_user.id)
    # Validate query is not empty
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty or whitespace")
    private_doc_ids = {
        row.doc_id for row in db.query(KnowledgeDocument.doc_id).filter(
            KnowledgeDocument.user_id == user_id,
        ).all()
    }
    results = []
    seen = set()
    for hit in get_kb(user_id).search(req.query.strip(), req.top_k):
        key = (hit.get("doc_id"), hit.get("chunk_id"))
        seen.add(key)
        payload = dict(hit)
        metadata = dict(payload.get("metadata") or {})
        metadata["knowledge_scope"] = "private"
        payload["metadata"] = metadata
        results.append(payload)
    for hit in _search_public_documents(db, req.query, req.top_k, private_doc_ids):
        key = (hit.get("doc_id"), hit.get("chunk_id"))
        if key in seen:
            continue
        seen.add(key)
        results.append(hit)
    results.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    results = results[:req.top_k]
    return [SearchHit(**r) for r in results]


@router.get("/documents/{doc_id}/chunks/{chunk_id}")
def get_document_chunk(
    doc_id: str,
    chunk_id: int,
    neighbors: int = Query(1, ge=0, le=3),
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Get one source chunk plus nearby chunks for evidence preview."""
    user_id = uuid_string_to_bytes(current_user.id)
    owner_id = resolve_document_owner(db, user_id, doc_id)
    if owner_id is None:
        raise HTTPException(status_code=404, detail="Document not found")
    target_doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.user_id == owner_id,
        KnowledgeDocument.doc_id == doc_id,
    ).first()
    start = max(0, chunk_id - neighbors)
    end = chunk_id + neighbors
    rows = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.user_id == owner_id,
        KnowledgeChunk.doc_id == doc_id,
        KnowledgeChunk.chunk_id >= start,
        KnowledgeChunk.chunk_id <= end,
    ).order_by(KnowledgeChunk.chunk_id.asc()).all()
    chunks = [
        type("ChunkView", (), {
            "chunk_id": row.chunk_id,
            "content": row.content,
            "metadata": row.chunk_metadata or {},
        })()
        for row in rows
    ]

    if not chunks:
        raise HTTPException(status_code=404, detail="Chunk not found")

    chunks.sort(key=lambda c: int(c.chunk_id))
    metadata = target_doc.doc_metadata or {}
    source_url = (
        metadata.get("url")
        or metadata.get("source_url")
        or metadata.get("source")
        or metadata.get("link")
    )
    if source_url and not str(source_url).startswith(("http://", "https://")):
        source_url = None

    return {
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "title": metadata.get("title") or metadata.get("source") or doc_id,
        "category": metadata.get("category") or "",
        "source_url": source_url,
        "scope": knowledge_scope(owner_id, user_id),
        "read_only": owner_id == SYSTEM_KB_USER_ID,
        "chunks": [
            {
                "chunk_id": int(c.chunk_id),
                "content": c.content,
                "active": int(c.chunk_id) == int(chunk_id),
            }
            for c in chunks
        ],
    }


@router.delete("/")
def clear_kb(
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Clear all documents from user's knowledge base."""
    user_id = uuid_string_to_bytes(current_user.id)
    kb = get_kb(user_id)
    kb.clear()
    return {"cleared": True}

@router.get("/documents/{doc_id}/content")
def get_document_content(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Get full document content by combining all chunks."""
    user_id = uuid_string_to_bytes(current_user.id)
    owner_id = resolve_document_owner(db, user_id, doc_id)
    if owner_id is None:
        raise HTTPException(status_code=404, detail="Document not found")
    target = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.user_id == owner_id,
        KnowledgeDocument.doc_id == doc_id,
    ).first()
    all_chunks = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.user_id == owner_id,
        KnowledgeChunk.doc_id == doc_id,
    ).order_by(KnowledgeChunk.chunk_id.asc()).all()
    full_content = "\n\n".join(chunk.content for chunk in all_chunks)
    metadata = target.doc_metadata or {}

    return {
        "doc_id": doc_id,
        "title": metadata.get("title") or target.title or doc_id,
        "category": metadata.get("category") or target.category or "",
        "content": full_content,
        "chunk_count": len(all_chunks),
        "scope": knowledge_scope(owner_id, user_id),
        "read_only": owner_id == SYSTEM_KB_USER_ID,
    }
