"""Persistent state for the chapter-based learning and practice flow."""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.mysql import BINARY, ENUM, JSON

from app.models import Base


class ChapterProgress(Base):
    __tablename__ = "chapter_progress"

    id = Column(BINARY(16), primary_key=True)
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_key = Column(String(128), nullable=False)
    chapter_doc_id = Column(String(128), nullable=False)
    assistant_conversation_id = Column(BINARY(16), nullable=True)
    status = Column(ENUM("not_started", "reading", "ready_for_quiz", "passed", name="chapter_progress_status"), nullable=False, default="not_started")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("uq_chapter_progress_user_chapter", "user_id", "chapter_doc_id", unique=True),
        Index("idx_chapter_progress_user_course", "user_id", "course_key"),
    )


class LearningAssessment(Base):
    """One generated, user-owned question set. It remains reusable until submitted."""
    __tablename__ = "learning_assessments"

    id = Column(BINARY(16), primary_key=True)
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_key = Column(String(128), nullable=False)
    chapter_doc_id = Column(String(128), nullable=True)
    exam_id = Column(BINARY(16), ForeignKey("exams.id", ondelete="CASCADE"), nullable=True)
    assessment_type = Column(ENUM("chapter_quiz", "course_exam", "code_practice", name="learning_assessment_type"), nullable=False)
    status = Column(ENUM("active", "submitted", "passed", "failed", name="learning_assessment_status"), nullable=False, default="active")
    passing_score = Column(Float, nullable=False, default=60)
    question_count = Column(Integer, nullable=False, default=0)
    blueprint = Column(JSON, nullable=True)
    generated_at = Column(DateTime, server_default=func.current_timestamp())
    submitted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_learning_assessment_user_scope", "user_id", "course_key", "chapter_doc_id", "assessment_type", "status"),
    )


class AssessmentSubmission(Base):
    __tablename__ = "assessment_submissions"

    id = Column(BINARY(16), primary_key=True)
    assessment_id = Column(BINARY(16), ForeignKey("learning_assessments.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    answers = Column(JSON, nullable=False)
    result = Column(JSON, nullable=False)
    score = Column(Float, nullable=False)
    passed = Column(Integer, nullable=False, default=0)
    submitted_at = Column(DateTime, server_default=func.current_timestamp())

    __table_args__ = (Index("idx_assessment_submission_user", "user_id", "assessment_id"),)


class CodeSubmission(Base):
    __tablename__ = "code_submissions"

    id = Column(BINARY(16), primary_key=True)
    assessment_id = Column(BINARY(16), ForeignKey("learning_assessments.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    language = Column(ENUM("python", "c", "cpp", "java", name="practice_code_language"), nullable=False)
    mode = Column(ENUM("acm", "leetcode", name="practice_code_mode"), nullable=False)
    code = Column(Text, nullable=False)
    score = Column(Float, nullable=False, default=0)
    passed = Column(Integer, nullable=False, default=0)
    verdict = Column(String(64), nullable=False, default="pending")
    feedback = Column(JSON, nullable=True)
    submitted_at = Column(DateTime, server_default=func.current_timestamp())

    __table_args__ = (Index("idx_code_submission_user", "user_id", "assessment_id"),)


class LearningMistake(Base):
    __tablename__ = "learning_mistakes"

    id = Column(BINARY(16), primary_key=True)
    user_id = Column(BINARY(16), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(ENUM("quiz", "code", name="learning_mistake_source_type"), nullable=False)
    assessment_id = Column(BINARY(16), ForeignKey("learning_assessments.id", ondelete="CASCADE"), nullable=False)
    question_key = Column(String(128), nullable=True)
    title = Column(String(255), nullable=False)
    prompt = Column(Text, nullable=False)
    user_answer = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    status = Column(ENUM("open", "reviewed", name="learning_mistake_status"), nullable=False, default="open")
    created_at = Column(DateTime, server_default=func.current_timestamp())

    __table_args__ = (Index("idx_learning_mistake_user_source", "user_id", "source_type", "status"),)
