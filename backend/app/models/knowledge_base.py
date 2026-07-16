# -*- coding: utf-8 -*-
from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import BINARY, JSON

from app.models import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BINARY(16), nullable=False, index=True)
    doc_id = Column(String(128), nullable=False)
    title = Column(String(255), nullable=False, default="")
    category = Column(String(128), nullable=True, index=True)
    source_type = Column(String(64), nullable=True)
    content_length = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    doc_metadata = Column(JSON, nullable=True)
    added_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint("user_id", "doc_id", name="uq_kd_user_doc"),
        Index("idx_kd_user_category", "user_id", "category"),
        Index("idx_kd_user_title", "user_id", "title"),
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BINARY(16), nullable=False, index=True)
    doc_id = Column(String(128), nullable=False)
    chunk_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    chunk_metadata = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "doc_id", "chunk_id", name="uq_kc_user_doc_chunk"),
        Index("idx_kc_user_doc", "user_id", "doc_id"),
    )
