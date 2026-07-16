"""Export or restore the shared system knowledge base as JSONL.

Usage:
    python scripts/system_kb_backup.py export --output <directory>
    python scripts/system_kb_backup.py restore --input <directory>
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models import SessionLocal  # noqa: E402
from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument  # noqa: E402
from app.services.knowledge_scope import SYSTEM_KB_USER_ID  # noqa: E402


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _open_text(path: Path, mode: str):
    if path.suffix == ".gz":
        return gzip.open(path, mode + "t", encoding="utf-8", newline="\n")
    return path.open(mode, encoding="utf-8", newline="\n")


def export_backup(output: Path, compress: bool = False) -> None:
    output.mkdir(parents=True, exist_ok=False)
    suffix = ".jsonl.gz" if compress else ".jsonl"
    documents_path = output / f"knowledge_documents{suffix}"
    chunks_path = output / f"knowledge_chunks{suffix}"

    with SessionLocal() as db:
        documents = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.user_id == SYSTEM_KB_USER_ID
        ).order_by(KnowledgeDocument.doc_id).all()
        chunks = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.user_id == SYSTEM_KB_USER_ID
        ).order_by(KnowledgeChunk.doc_id, KnowledgeChunk.chunk_id).all()

        with _open_text(documents_path, "w") as handle:
            for row in documents:
                payload = {
                    "doc_id": row.doc_id,
                    "title": row.title,
                    "category": row.category,
                    "source_type": row.source_type,
                    "content_length": row.content_length,
                    "chunk_count": row.chunk_count,
                    "doc_metadata": row.doc_metadata,
                    "added_at": row.added_at,
                    "updated_at": row.updated_at,
                }
                handle.write(json.dumps(payload, ensure_ascii=False, default=_json_default) + "\n")

        with _open_text(chunks_path, "w") as handle:
            for row in chunks:
                payload = {
                    "doc_id": row.doc_id,
                    "chunk_id": row.chunk_id,
                    "content": row.content,
                    "chunk_metadata": row.chunk_metadata,
                }
                handle.write(json.dumps(payload, ensure_ascii=False, default=_json_default) + "\n")

    manifest = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_id_hex": SYSTEM_KB_USER_ID.hex(),
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "files": {
            documents_path.name: _sha256(documents_path),
            chunks_path.name: _sha256(chunks_path),
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    with _open_text(path, "r") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at {path}:{line_number}: {exc}") from exc
    return records


def _parse_datetime(value):
    if not value or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def restore_backup(source: Path) -> None:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected in manifest.get("files", {}).items():
        actual = _sha256(source / filename)
        if actual != expected:
            raise ValueError(f"Checksum mismatch for {filename}")

    documents_name = next(name for name in manifest["files"] if name.startswith("knowledge_documents."))
    chunks_name = next(name for name in manifest["files"] if name.startswith("knowledge_chunks."))
    documents = _read_jsonl(source / documents_name)
    chunks = _read_jsonl(source / chunks_name)
    if len(documents) != int(manifest["document_count"]):
        raise ValueError("Document count does not match manifest")
    if len(chunks) != int(manifest["chunk_count"]):
        raise ValueError("Chunk count does not match manifest")

    with SessionLocal() as db:
        try:
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.user_id == SYSTEM_KB_USER_ID
            ).delete(synchronize_session=False)
            db.query(KnowledgeDocument).filter(
                KnowledgeDocument.user_id == SYSTEM_KB_USER_ID
            ).delete(synchronize_session=False)

            for start in range(0, len(documents), 500):
                db.bulk_insert_mappings(KnowledgeDocument, [
                    {
                        "user_id": SYSTEM_KB_USER_ID,
                        **{key: item.get(key) for key in (
                            "doc_id", "title", "category", "source_type",
                            "content_length", "chunk_count", "doc_metadata",
                        )},
                        "added_at": _parse_datetime(item.get("added_at")),
                        "updated_at": _parse_datetime(item.get("updated_at")),
                    }
                    for item in documents[start:start + 500]
                ])
            for start in range(0, len(chunks), 1000):
                db.bulk_insert_mappings(KnowledgeChunk, [
                    {
                        "user_id": SYSTEM_KB_USER_ID,
                        "doc_id": item["doc_id"],
                        "chunk_id": int(item["chunk_id"]),
                        "content": item["content"],
                        "chunk_metadata": item.get("chunk_metadata") or {},
                    }
                    for item in chunks[start:start + 1000]
                ])
            db.commit()
        except Exception:
            db.rollback()
            raise
    print(json.dumps({"restored_documents": len(documents), "restored_chunks": len(chunks)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--output", type=Path, required=True)
    export_parser.add_argument("--compress", action="store_true")
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "export":
        export_backup(args.output.resolve(), compress=args.compress)
    else:
        restore_backup(args.input.resolve())


if __name__ == "__main__":
    main()
