"""One-time migration from legacy sandbox KB JSON files into MySQL."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models import SessionLocal  # noqa: E402
from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument  # noqa: E402


def migrate_user(user_dir: Path) -> tuple[int, int]:
    try:
        user_id = bytes.fromhex(user_dir.name)
    except ValueError:
        return 0, 0
    if len(user_id) != 16:
        return 0, 0

    chunks_path = user_dir / "index.json"
    documents_path = user_dir / "documents.json"
    if not chunks_path.exists():
        return 0, 0

    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    documents = (
        json.loads(documents_path.read_text(encoding="utf-8"))
        if documents_path.exists()
        else {}
    )

    with SessionLocal() as db:
        db.query(KnowledgeChunk).filter(KnowledgeChunk.user_id == user_id).delete(
            synchronize_session=False
        )
        for start in range(0, len(chunks), 1000):
            db.bulk_insert_mappings(KnowledgeChunk, [
                {
                    "user_id": user_id,
                    "doc_id": item["doc_id"],
                    "chunk_id": int(item.get("chunk_id") or 0),
                    "content": item.get("content") or "",
                    "chunk_metadata": item.get("metadata") or {},
                }
                for item in chunks[start:start + 1000]
            ])

        existing = {
            row.doc_id: row
            for row in db.query(KnowledgeDocument).filter(
                KnowledgeDocument.user_id == user_id
            ).all()
        }
        for doc_id, doc in documents.items():
            metadata = doc.get("metadata") or {}
            row = existing.get(doc_id)
            if row is None:
                row = KnowledgeDocument(user_id=user_id, doc_id=doc_id)
                db.add(row)
            row.title = str(metadata.get("title") or metadata.get("source") or doc_id)[:255]
            row.category = str(metadata.get("category") or "")[:128] or None
            row.source_type = str(metadata.get("source_type") or "")[:64] or None
            row.content_length = int(doc.get("content_length") or 0)
            row.chunk_count = int(doc.get("chunk_count") or 0)
            row.doc_metadata = metadata
        db.commit()
    return len(documents), len(chunks)


def main() -> None:
    kb_root = ROOT / "sandbox" / "kb"
    total_documents = 0
    total_chunks = 0
    for user_dir in kb_root.iterdir() if kb_root.exists() else []:
        if not user_dir.is_dir():
            continue
        documents, chunks = migrate_user(user_dir)
        if documents or chunks:
            print(f"{user_dir.name}: {documents} documents, {chunks} chunks")
        total_documents += documents
        total_chunks += chunks
    print(f"migrated: {total_documents} documents, {total_chunks} chunks")


if __name__ == "__main__":
    main()
