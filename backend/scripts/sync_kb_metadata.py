# -*- coding: utf-8 -*-
"""Sync legacy file-based KB document metadata into MySQL.

This script intentionally syncs document metadata only. Chunks remain in Chroma
and the legacy KB files for content reconstruction; the learning workspace only
needs fast document-level listing and category aggregation.
"""
from __future__ import annotations

import binascii
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models import SessionLocal  # noqa: E402
from app.models.knowledge_base import KnowledgeDocument  # noqa: E402
from app.services.rag_service import KB_ROOT  # noqa: E402


def parse_added_at(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def sync() -> int:
    db = SessionLocal()
    count = 0
    try:
        for docs_file in KB_ROOT.glob("*/documents.json"):
            try:
                user_id = binascii.unhexlify(docs_file.parent.name)
            except Exception:
                continue
            try:
                docs = json.loads(docs_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(docs, dict):
                continue

            for doc_id, doc in docs.items():
                if not isinstance(doc, dict):
                    continue
                meta = doc.get("metadata", {}) or {}
                title = str(meta.get("title") or meta.get("source") or doc_id)
                if not title or int(doc.get("content_length") or 0) <= 50:
                    continue
                row = db.query(KnowledgeDocument).filter(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeDocument.doc_id == doc_id,
                ).first()
                if not row:
                    row = KnowledgeDocument(user_id=user_id, doc_id=doc_id)
                    db.add(row)
                row.title = title[:255]
                row.category = str(meta.get("category") or "")[:128] or None
                row.source_type = str(meta.get("source_type") or "")[:64] or None
                row.content_length = int(doc.get("content_length") or 0)
                row.chunk_count = int(doc.get("chunk_count") or 0)
                row.doc_metadata = meta
                row.added_at = parse_added_at(doc.get("added_at"))
                count += 1
        db.commit()
        return count
    finally:
        db.close()


if __name__ == "__main__":
    print(f"synced={sync()}")
