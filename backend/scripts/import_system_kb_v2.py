"""Validate, curate, and import an external XBots KB v2 package."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models import SessionLocal  # noqa: E402
from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument  # noqa: E402
from app.services.knowledge_scope import SYSTEM_KB_USER_ID  # noqa: E402
from app.services.rag_service import CHROMA_ROOT, KnowledgeBase  # noqa: E402


DROP_EXACT_URLS = {
    "https://git-scm.com/",
    "https://git-scm.com/about",
    "https://git-scm.com/about/trademark",
    "http://git-scm.com/docs",
    "https://go.dev/blog",
    "https://huggingface.co/chat",
    "https://huggingface.co/collections",
    "https://huggingface.co/datasets",
    "https://huggingface.co/docs",
    "https://pandas.pydata.org/",
    "https://pytorch.org/",
    "https://redis.io/blog",
    "https://redis.io/chat",
    "https://tensorflow.org/",
    "https://tensorflow.org/api",
    "https://dev.mysql.com/",
    "https://docs.docker.com/guides",
    "https://docs.docker.com/manuals",
    "https://huggingface.co/blog/zh",
    "https://numpy.org/",
}

DROP_URL_PARTS = (
    "/contents.html",
    "/genindex.html",
    "/bugs.html",
    "/llms-full.txt",
    "/llms.txt",
    "/latest-v13.x/",
    "/api/r1.15",
    "/api/r2.0",
    "/api/r2.1",
    "/_sources/index.md.txt",
    "/cloud-partners/",
)

DROP_LINE_EXACT = {
    "Back",
    "Ask Gordon",
    "Copy Markdown",
    "Download Markdown",
    "View Markdown",
    "Copy Page",
    "Responses",
    "Was this helpful?",
}

DROP_LINE_PATTERNS = (
    re.compile(r"^\[?(?:Edit this page|Edit on GitHub)\]?", re.I),
    re.compile(r"^(?:Skip to content|Table of contents)$", re.I),
    re.compile(r"^\[English\s*.*\]\(.*\)$", re.I),
)

GENERIC_TITLES = {
    "git", "reference", "documentation", "introduction", "book", "manuals",
    "guides", "collections", "transformers", "the n", "ecosystem", "join us",
    "index.md.txt", "google code", "multi",
}


def read_jsonl_files(directory: Path) -> list[dict]:
    records = []
    for path in sorted(directory.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at {path}:{line_number}: {exc}") from exc
    return records


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def should_drop_document(document: dict) -> tuple[bool, str]:
    url = str(document.get("canonical_url") or "").rstrip("/")
    normalized_with_slash = str(document.get("canonical_url") or "")
    if normalized_with_slash in DROP_EXACT_URLS or url in {item.rstrip("/") for item in DROP_EXACT_URLS}:
        return True, "non_learning_landing_page"
    if any(part in normalized_with_slash.lower() for part in DROP_URL_PARTS):
        return True, "aggregate_outdated_or_marketing_page"
    return False, ""


def clean_markdown(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value or "")).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch) != "Cc")
    lines = text.split("\n")
    output: list[str] = []
    in_fence = False
    skip_toc_level = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            output.append(line.rstrip())
            continue
        if in_fence:
            output.append(line.rstrip())
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if skip_toc_level:
            if heading and len(heading.group(1)) <= skip_toc_level:
                skip_toc_level = 0
            else:
                continue
        if re.match(r"^#{1,6}\s+(?:On this page|Table of Contents)\s*$", stripped, re.I):
            skip_toc_level = len(stripped) - len(stripped.lstrip("#"))
            continue
        if re.match(r"^\*\*(?:On this page|Table of Contents)\*\*\s*$", stripped, re.I):
            skip_toc_level = 2
            continue
        if stripped in DROP_LINE_EXACT or any(pattern.search(stripped) for pattern in DROP_LINE_PATTERNS):
            continue
        if re.match(r"^[-*]\s+\[(?:Manuals|Get started|Guides|Reference)\]\([^)]*\)\s*$", stripped, re.I):
            continue
        if output and stripped and stripped == output[-1].strip():
            continue
        output.append(line.rstrip())

    cleaned = "\n".join(output)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def detect_language(text: str) -> str:
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    letters = sum(character.isalpha() for character in prose)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", prose))
    return "zh-CN" if letters and cjk / letters >= 0.08 else "en"


def clean_title(document: dict) -> str:
    title = re.sub(r"\s+#\s*$", "", str(document.get("title") or "")).strip()
    title = re.sub(r"\s+Stay organized with collections.*$", "", title, flags=re.I).strip()
    url = str(document.get("canonical_url") or "")
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1]

    if title.lower() == "git" and slug.startswith("git-"):
        return slug
    if title.lower() == "transformers" and "/model_doc/" in path:
        return f"Transformers: {slug.upper()}"
    if title.lower() == "transformers" and slug not in {"transformers", "index"}:
        return f"Transformers: {slug.replace('_', ' ').title()}"
    if title.lower() == "the n" and "ndarray" in path:
        return "NumPy ndarray"
    if title.endswith(" --"):
        return f"{title[:-3].strip()} 模块"
    if title.lower() in GENERIC_TITLES and slug and slug not in {"docs", "doc", "index", "en", "zh"}:
        return slug.replace("-", " ").replace("_", " ").strip().title()
    return title or slug or str(document.get("document_id"))


def token_count(text: str, encoding) -> int:
    return len(encoding.encode(text, disallowed_special=()))


def is_navigation_only(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    links = len(re.findall(r"\[[^]]+\]\([^)]+\)", stripped))
    non_link = re.sub(r"\[[^]]+\]\([^)]+\)", "", stripped)
    words = len(re.findall(r"[A-Za-z\u4e00-\u9fff]{2,}", non_link))
    return links >= 8 and words < 25


def curate(source: Path) -> tuple[list[dict], list[dict], dict]:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    raw_documents = read_jsonl_files(source / "documents")
    raw_chunks = read_jsonl_files(source / "chunks")
    if len(raw_documents) != int(manifest.get("document_count") or -1):
        raise ValueError("Document count does not match manifest")
    if len(raw_chunks) != int(manifest.get("chunk_count") or -1):
        raise ValueError("Chunk count does not match manifest")

    encoding = tiktoken.get_encoding("cl100k_base")
    dropped_reasons = Counter()
    dropped_documents: list[dict] = []
    documents_by_id: dict[str, dict] = {}
    for raw in raw_documents:
        expected_hash = str(raw.get("content_sha256") or "")
        if expected_hash and sha256_text(str(raw.get("content_markdown") or "")) != expected_hash:
            raise ValueError(f"Document hash mismatch: {raw.get('document_id')}")
        drop, reason = should_drop_document(raw)
        if drop:
            dropped_reasons[reason] += 1
            dropped_documents.append({"title": raw.get("title"), "url": raw.get("canonical_url"), "reason": reason})
            continue
        content = clean_markdown(raw.get("content_markdown") or "")
        if len(content) < 800:
            dropped_reasons["cleaned_content_too_short"] += 1
            dropped_documents.append({"title": raw.get("title"), "url": raw.get("canonical_url"), "reason": "cleaned_content_too_short"})
            continue
        document = dict(raw)
        document["title"] = clean_title(raw)[:255]
        document["content_markdown"] = content
        document["language"] = detect_language(content)
        document["content_sha256"] = sha256_text(content)
        document["description"] = clean_markdown(raw.get("description") or "")[:300]
        documents_by_id[document["document_id"]] = document

    chunks_by_doc: dict[str, list[dict]] = defaultdict(list)
    for raw in raw_chunks:
        document = documents_by_id.get(raw.get("document_id"))
        if not document:
            continue
        expected_hash = str(raw.get("content_sha256") or "")
        if expected_hash and sha256_text(str(raw.get("content") or "")) != expected_hash:
            raise ValueError(f"Chunk hash mismatch: {raw.get('chunk_id')}")
        content = clean_markdown(raw.get("content") or "")
        if is_navigation_only(content):
            dropped_reasons["navigation_only_chunk"] += 1
            continue
        item = dict(raw)
        item["content"] = content
        item["title"] = document["title"]
        item["language"] = document["language"]
        item["token_count"] = token_count(content, encoding)
        item["char_count"] = len(content)
        item["content_sha256"] = sha256_text(content)
        chunks_by_doc[item["document_id"]].append(item)

    curated_documents: list[dict] = []
    curated_chunks: list[dict] = []
    for document_id, document in sorted(documents_by_id.items()):
        source_chunks = sorted(chunks_by_doc.get(document_id, []), key=lambda item: int(item.get("chunk_index") or 0))
        if not source_chunks:
            dropped_reasons["document_without_useful_chunks"] += 1
            dropped_documents.append({"title": document.get("title"), "url": document.get("canonical_url"), "reason": "document_without_useful_chunks"})
            continue

        merged: list[dict] = []
        for item in source_chunks:
            if item["token_count"] < 120 and merged:
                combined = f"{merged[-1]['content']}\n\n{item['content']}".strip()
                combined_tokens = token_count(combined, encoding)
                if combined_tokens <= 900:
                    merged[-1]["content"] = combined
                    merged[-1]["token_count"] = combined_tokens
                    merged[-1]["char_count"] = len(combined)
                    merged[-1]["content_sha256"] = sha256_text(combined)
                    continue
            merged.append(item)
        if len(merged) > 1 and merged[0]["token_count"] < 120:
            combined = f"{merged[0]['content']}\n\n{merged[1]['content']}".strip()
            if token_count(combined, encoding) <= 900:
                merged[1]["content"] = combined
                merged[1]["token_count"] = token_count(combined, encoding)
                merged[1]["char_count"] = len(combined)
                merged[1]["content_sha256"] = sha256_text(combined)
                merged.pop(0)

        for index, item in enumerate(merged):
            item["chunk_index"] = index
            item["chunk_id"] = f"{document_id}#{index:04d}"
            item["content_sha256"] = sha256_text(item["content"])
            curated_chunks.append(item)
        document["chunk_count"] = len(merged)
        curated_documents.append(document)

    report = {
        "dataset_id": manifest.get("dataset_id"),
        "source_documents": len(raw_documents),
        "source_chunks": len(raw_chunks),
        "curated_documents": len(curated_documents),
        "curated_chunks": len(curated_chunks),
        "dropped": dict(dropped_reasons),
        "dropped_documents": dropped_documents,
        "languages": dict(Counter(item["language"] for item in curated_documents)),
        "categories": dict(Counter(item.get("category") for item in curated_documents)),
        "domains": dict(Counter(item.get("source_domain") for item in curated_documents)),
        "short_chunks": sum(item["token_count"] < 120 for item in curated_chunks),
        "oversized_chunks": sum(item["token_count"] > 900 for item in curated_chunks),
    }
    return curated_documents, curated_chunks, report


def import_database(documents: list[dict], chunks: list[dict], dataset_id: str) -> None:
    chunks_by_doc = Counter(item["document_id"] for item in chunks)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with SessionLocal() as db:
        try:
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.user_id == SYSTEM_KB_USER_ID
            ).delete(synchronize_session=False)
            db.query(KnowledgeDocument).filter(
                KnowledgeDocument.user_id == SYSTEM_KB_USER_ID
            ).delete(synchronize_session=False)

            document_rows = []
            for item in documents:
                metadata = {
                    key: item.get(key) for key in (
                        "title", "description", "canonical_url", "source_domain", "source_name",
                        "source_type", "language", "category", "tags", "published_at", "updated_at",
                        "crawled_at", "content_version", "license", "content_sha256",
                    )
                }
                metadata.update({
                    "source_url": item.get("canonical_url"),
                    "dataset_id": dataset_id,
                    "knowledge_scope": "public",
                })
                document_rows.append({
                    "user_id": SYSTEM_KB_USER_ID,
                    "doc_id": item["document_id"],
                    "title": item["title"][:255],
                    "category": str(item.get("category") or "")[:128] or None,
                    "source_type": str(item.get("source_type") or "")[:64] or None,
                    "content_length": len(item["content_markdown"]),
                    "chunk_count": chunks_by_doc[item["document_id"]],
                    "doc_metadata": metadata,
                    "added_at": now,
                    "updated_at": now,
                })
            for start in range(0, len(document_rows), 500):
                db.bulk_insert_mappings(KnowledgeDocument, document_rows[start:start + 500])

            chunk_rows = []
            for item in chunks:
                metadata = {
                    key: item.get(key) for key in (
                        "title", "heading_path", "language", "category", "tags", "source_url",
                        "source_domain", "source_type", "content_version", "char_count", "token_count",
                        "content_sha256",
                    )
                }
                metadata.update({
                    "external_chunk_id": item.get("chunk_id"),
                    "dataset_id": dataset_id,
                    "knowledge_scope": "public",
                })
                chunk_rows.append({
                    "user_id": SYSTEM_KB_USER_ID,
                    "doc_id": item["document_id"],
                    "chunk_id": int(item["chunk_index"]),
                    "content": item["content"],
                    "chunk_metadata": metadata,
                })
            for start in range(0, len(chunk_rows), 1000):
                db.bulk_insert_mappings(KnowledgeChunk, chunk_rows[start:start + 1000])
            db.commit()
        except Exception:
            db.rollback()
            raise


def rebuild_chroma() -> int:
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_ROOT))
    collection_name = KnowledgeBase(SYSTEM_KB_USER_ID)._collection_name()
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    knowledge_base = KnowledgeBase(SYSTEM_KB_USER_ID)
    knowledge_base._upsert_chroma_chunks(knowledge_base.chunks)
    return knowledge_base._collection().count()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    documents, chunks, report = curate(source)
    if report["curated_documents"] == 0 or report["curated_chunks"] == 0:
        raise ValueError("Curated dataset is empty")
    if report["oversized_chunks"]:
        raise ValueError("Curated dataset contains oversized chunks")

    if args.apply:
        import_database(documents, chunks, str(report["dataset_id"] or source.name))
        report["chroma_count"] = rebuild_chroma()
        report["applied_at"] = datetime.now(timezone.utc).isoformat()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
