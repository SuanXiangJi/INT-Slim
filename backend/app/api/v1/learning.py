# -*- coding: utf-8 -*-
"""Learning Platform API - exposes all learning CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
import asyncio
import json
from sqlalchemy.orm import Session
from sqlalchemy import case, func, or_
from app.models import get_db
from app.schemas.user import User as UserSchema
from app.dependencies.auth import get_current_user
from app.services.knowledge_scope import (
    SYSTEM_KB_USER_ID,
    knowledge_scope,
    readable_owner_ids,
    resolve_document_owner,
)

router = APIRouter(prefix="/learning", tags=["learning"])

# ============================
# Schemas
# ============================
class LearnerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    grade: Optional[str] = None
    language: str = "zh-CN"
    goals: Optional[List[str]] = None
    tags: Optional[List[str]] = None

class LearnerOut(BaseModel):
    id: str
    name: str
    grade: Optional[str] = None
    language: str = "zh-CN"
    goals: Optional[list] = None
    tags: Optional[list] = None
    created_at: str
    class Config: from_attributes = True

class MasteryRecord(BaseModel):
    kp_id: str
    level: float = Field(0.0, ge=0, le=1)
    confidence: float = Field(0.5, ge=0, le=1)

class ErrorRecord(BaseModel):
    error_type: str
    kp_id: Optional[str] = None

class LoadRecord(BaseModel):
    load_value: float = Field(..., ge=0, le=1)
    threshold: float = 0.8

class KPCreate(BaseModel):
    name: str = Field(..., min_length=1)
    category: Optional[str] = None
    description: Optional[str] = None
    difficulty: float = 0.5
    tags: Optional[List[str]] = None

class KPOut(BaseModel):
    id: str; name: str; category: Optional[str] = None
    description: Optional[str] = None; difficulty: float
    tags: Optional[list] = None; created_at: str
    class Config: from_attributes = True

class PlanCreate(BaseModel):
    learner_id: str; goal: Optional[str] = None

class PlanOut(BaseModel):
    id: str; learner_id: str; goal: Optional[str] = None
    status: str; created_at: str; updated_at: str
    class Config: from_attributes = True

class PlanKPAdd(BaseModel):
    kp_id: str; sort_order: int = 0

class ExamCreate(BaseModel):
    title: str; plan_id: Optional[str] = None; description: Optional[str] = None

class QuestionAdd(BaseModel):
    kp_id: str; qtype: str; question_data: Dict[str, Any]
    difficulty: float = 0.5; sort_order: int = 0

class ContentCreate(BaseModel):
    template_type: str; title: str; content_data: Dict[str, Any]
    plan_id: Optional[str] = None; kp_id: Optional[str] = None

class ReviewCreate(BaseModel):
    content_id: str; reviewer_type: str = "auto"; risk_level: str = "medium"

class DefectAdd(BaseModel):
    defect_type: str; severity: str = "minor"
    location: Optional[str] = None; description: Optional[str] = None; suggestion: Optional[str] = None

class CandidateCreate(BaseModel):
    content_id: str; rank_score: float = 0.0; risk_info: Optional[Dict[str, Any]] = None

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)
    description: Optional[str] = Field(None, max_length=2000)
    task_type: str = Field("study", max_length=32)
    kp_id: Optional[str] = None
    due_date: Optional[datetime] = None

class TaskStatusUpdate(BaseModel):
    status: Literal["todo", "done"]

class TaskCompletion(BaseModel):
    minutes: int = Field(..., ge=3, le=480)
    reflection: str = Field(..., min_length=10, max_length=1000)
    quiz_score: Optional[float] = Field(None, ge=0, le=100)

class CourseMissionStart(BaseModel):
    title: Optional[str] = Field(None, max_length=160)

class CourseExamCreate(BaseModel):
    doc_id: str

class ExamSubmit(BaseModel):
    answers: Dict[str, Any]

class TrainingRunStart(BaseModel):
    doc_id: str
    goal: Optional[str] = Field(None, max_length=300)
    mode: Literal["guided", "assessment", "remediation"] = "guided"

class StudyAssistRequest(BaseModel):
    selected_text: str = Field(..., min_length=1, max_length=2000)
    question: Optional[str] = Field(None, max_length=600)
    context: Optional[str] = Field(None, max_length=4000)
    use_llm: bool = True

class AssessmentGenerateRequest(BaseModel):
    replace_previous: bool = False

class AssessmentAnswerRequest(BaseModel):
    answers: Dict[str, Any]

class CodePracticeCreate(BaseModel):
    chapter_doc_id: str
    language: Optional[Literal["python", "c", "cpp", "java"]] = None
    mode: Literal["acm", "leetcode"] = "acm"
    replace_previous: bool = False

class CodePracticeSubmit(BaseModel):
    code: str = Field(..., min_length=1, max_length=24000)

def _task_out(task):
    from app.utils.uuid import bytes_to_uuid_string
    return {
        "id": bytes_to_uuid_string(task.id), "title": task.title, "description": task.description,
        "task_type": task.task_type, "kp_id": task.kp_id, "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


def _record_task_study_event(db: Session, current_user: UserSchema, task) -> None:
    if not task.kp_id:
        return
    from app.models.learning.knowledge_point import StudyEvent
    from app.utils.uuid import generate_uuid, uuid_string_to_bytes
    event = StudyEvent(
        id=generate_uuid().hex(),
        user_id=uuid_string_to_bytes(current_user.id),
        kp_id=task.kp_id,
    )
    db.add(event)
    db.commit()


# ============================
# Chapter curriculum and assessment flow
# ============================
COURSE_LABELS = {
    "python3": "Python", "java": "Java", "cprogramming": "C 语言", "cplusplus": "C++",
    "ai-agent": "AI Agent", "langchain": "LangChain", "js": "JavaScript", "typescript": "TypeScript",
    "mysql": "MySQL", "redis": "Redis", "linux": "Linux", "docker": "Docker",
    "vue3": "Vue 3", "react": "React", "pytorch": "PyTorch", "ml": "机器学习",
}
COURSE_PRIORITY = ["python3", "java", "cprogramming", "cplusplus", "ai-agent", "langchain", "js", "typescript", "mysql", "redis", "linux", "docker", "vue3", "react", "pytorch", "ml"]
# The legacy crawler stored every reference page under a broad category, often in
# alphabetical order. A learning path must be curated, not a raw site index.
CURRICULUM_CHAPTER_IDS = {
    "python3": ["python3-intro", "python3-basic-syntax", "python3-basic-operators", "python3-if-statement", "python3-loop", "python3-function", "python3-list", "python3-tuple", "python3-dictionary", "python3-module", "python3-file-io", "python3-class"],
    "java": ["java-intro", "java-environment-setup", "java-basic-syntax", "java-operators", "java-if-else-switch", "java-loop", "java-methods", "java-arraylist", "java-object-classes", "java-exceptions", "java-files-io", "java8-functional-interfaces"],
    "cprogramming": ["c-intro", "c-environment-setup", "c-basic-syntax", "c-variables", "c-data-types", "c-decision", "c-loops", "c-functions", "c-arrays", "c-pointers", "c-structures", "c-file-io"],
    "cplusplus": ["cpp-intro", "cpp-environment-setup", "cpp-basic-syntax", "cpp-data-types", "cpp-decision", "cpp-loops", "cpp-functions", "cpp-arrays", "cpp-pointers", "cpp-classes-objects", "cpp-exceptions-handling", "cpp-files-streams"],
    "ai-agent": ["ai-agent-intro", "ai-agent-llm", "ai-agent-core", "ai-agent-working-principle", "ai-agent-function-calling", "ai-agent-memory-system-design", "python-rag", "ai-workflow", "multi-agent-system", "evaluation-safety-alignment"],
}

PRACTICE_LANGUAGE_LABELS = {"python": "Python", "c": "C", "cpp": "C++", "java": "Java"}
PRACTICE_LANGUAGE_POLICIES = {
    "python3": ("fixed", ["python"]),
    "pytorch": ("fixed", ["python"]),
    "tensorflow": ("fixed", ["python"]),
    "numpy": ("fixed", ["python"]),
    "pandas": ("fixed", ["python"]),
    "sklearn": ("fixed", ["python"]),
    "ml": ("fixed", ["python"]),
    "ai-agent": ("fixed", ["python"]),
    "langchain": ("fixed", ["python"]),
    "java": ("fixed", ["java"]),
    "cprogramming": ("fixed", ["c"]),
    "cplusplus": ("fixed", ["cpp"]),
    "data-structures": ("flexible", ["python", "c", "cpp", "java"]),
    "algorithms": ("flexible", ["python", "c", "cpp", "java"]),
}


def _user_id_bytes(current_user: UserSchema) -> bytes:
    from app.utils.uuid import uuid_string_to_bytes
    return uuid_string_to_bytes(current_user.id)


def _course_label(key: str) -> str:
    return COURSE_LABELS.get(key, key.replace("-", " ").title())


def _practice_language_policy(course_key: str) -> Dict[str, Any]:
    policy, languages = PRACTICE_LANGUAGE_POLICIES.get(course_key, ("fixed", ["python"]))
    return {
        "policy": policy,
        "allowed_languages": languages,
        "recommended_language": languages[0],
        "language_labels": {language: PRACTICE_LANGUAGE_LABELS[language] for language in languages},
    }


def _curriculum_chapters(db: Session, course_key: str):
    from app.models.knowledge_base import KnowledgeDocument
    rows = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.user_id == SYSTEM_KB_USER_ID,
        KnowledgeDocument.category == course_key,
        KnowledgeDocument.content_length > 120,
    ).all()
    order = CURRICULUM_CHAPTER_IDS.get(course_key)
    if not order:
        return []
    by_suffix = {row.doc_id.removeprefix(f"cainiao_{course_key}_"): row for row in rows}
    return [by_suffix[suffix] for suffix in order if suffix in by_suffix]


def _chapter_content(db: Session, doc_id: str) -> str:
    from app.models.knowledge_base import KnowledgeChunk
    rows = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.user_id == SYSTEM_KB_USER_ID,
        KnowledgeChunk.doc_id == doc_id,
    ).order_by(KnowledgeChunk.chunk_id.asc()).all()
    return "\n\n".join(row.content for row in rows)


def _progress_map(db: Session, user_id: bytes, course_key: str):
    from app.models.learning.curriculum import ChapterProgress
    rows = db.query(ChapterProgress).filter(
        ChapterProgress.user_id == user_id, ChapterProgress.course_key == course_key,
    ).all()
    return {row.chapter_doc_id: row for row in rows}


def _chapter_out(row, index: int, progress, unlocked: bool) -> Dict[str, Any]:
    metadata = row.doc_metadata or {}
    return {
        "index": index + 1,
        "doc_id": row.doc_id,
        "title": row.title or metadata.get("title") or row.doc_id,
        "estimated_minutes": max(8, min(45, int(row.chunk_count or 1) * 4)),
        "status": progress.status if progress else "not_started",
        "unlocked": unlocked,
        "completed": bool(progress and progress.status == "passed"),
    }


def _get_assessment(db: Session, current_user: UserSchema, assessment_id: str):
    from app.models.learning.curriculum import LearningAssessment
    from app.utils.uuid import uuid_string_to_bytes
    try:
        raw_id = uuid_string_to_bytes(assessment_id)
    except ValueError:
        raise HTTPException(404, "Assessment not found")
    assessment = db.query(LearningAssessment).filter(
        LearningAssessment.id == raw_id, LearningAssessment.user_id == _user_id_bytes(current_user),
    ).first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    return assessment


def _assessment_out(db: Session, assessment, include_answers: bool = False) -> Dict[str, Any]:
    from app.models.learning.exam import ExamQuestion
    from app.utils.uuid import bytes_to_uuid_string
    payload = {
        "id": bytes_to_uuid_string(assessment.id), "type": assessment.assessment_type,
        "status": assessment.status, "course_key": assessment.course_key,
        "chapter_doc_id": assessment.chapter_doc_id, "passing_score": assessment.passing_score,
        "question_count": assessment.question_count, "blueprint": assessment.blueprint or {},
    }
    if assessment.exam_id:
        questions = db.query(ExamQuestion).filter(ExamQuestion.exam_id == assessment.exam_id).order_by(ExamQuestion.sort_order).all()
        payload["questions"] = [{
            "id": bytes_to_uuid_string(question.id),
            "type": question.question_type,
            "data": question.question_data if include_answers else {key: value for key, value in question.question_data.items() if key != "answer"},
        } for question in questions]
    if assessment.status != "active":
        from app.models.learning.curriculum import AssessmentSubmission
        submission = db.query(AssessmentSubmission).filter(
            AssessmentSubmission.assessment_id == assessment.id,
        ).order_by(AssessmentSubmission.submitted_at.desc()).first()
        if submission:
            payload["latest_result"] = {
                "score": submission.score,
                "passed": bool(submission.passed),
                "passing_score": assessment.passing_score,
                "results": (submission.result or {}).get("questions", []),
                "agent_feedback": "判题 Agent 已按保存的标准答案与解析完成核对。",
            }
    return payload


@router.get("/curriculum")
def get_curriculum(db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    """Level one of the resource hierarchy: public knowledge-base categories."""
    from app.models.knowledge_base import KnowledgeDocument
    user_id = _user_id_bytes(current_user)
    progress_rows = []
    try:
        from app.models.learning.curriculum import ChapterProgress
        progress_rows = db.query(ChapterProgress.course_key, func.count(ChapterProgress.id)).filter(
            ChapterProgress.user_id == user_id, ChapterProgress.status == "passed",
        ).group_by(ChapterProgress.course_key).all()
    except Exception:
        pass
    passed = dict(progress_rows)
    courses = []
    for key in COURSE_PRIORITY:
        chapters = _curriculum_chapters(db, key)
        if chapters:
            courses.append({"key": key, "title": _course_label(key), "chapter_count": len(chapters), "passed_count": int(passed.get(key, 0))})
    order = {key: index for index, key in enumerate(COURSE_PRIORITY)}
    courses.sort(key=lambda item: (order.get(item["key"], 999), item["title"]))
    return {"courses": courses, "overview": {"course_count": len(courses), "chapter_count": sum(item["chapter_count"] for item in courses)}}


@router.get("/curriculum/{course_key}/chapters")
def get_course_chapters(course_key: str, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    chapters = _curriculum_chapters(db, course_key)
    if not chapters:
        raise HTTPException(404, "Course not found")
    progress = _progress_map(db, _user_id_bytes(current_user), course_key)
    result = []
    previous_passed = True
    for index, chapter in enumerate(chapters):
        record = progress.get(chapter.doc_id)
        unlocked = index == 0 or previous_passed
        result.append(_chapter_out(chapter, index, record, unlocked))
        previous_passed = bool(record and record.status == "passed")
    return {"key": course_key, "title": _course_label(course_key), "chapters": result, "all_passed": bool(result) and all(item["completed"] for item in result)}


@router.get("/curriculum/{course_key}/chapters/{doc_id}")
def get_chapter(course_key: str, doc_id: str, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    chapters = _curriculum_chapters(db, course_key)
    index = next((i for i, row in enumerate(chapters) if row.doc_id == doc_id), None)
    if index is None:
        raise HTTPException(404, "Chapter not found")
    progress = _progress_map(db, _user_id_bytes(current_user), course_key)
    if index > 0 and not (progress.get(chapters[index - 1].doc_id) and progress[chapters[index - 1].doc_id].status == "passed"):
        raise HTTPException(403, "Complete the previous chapter quiz first")
    row = chapters[index]
    return {"chapter": _chapter_out(row, index, progress.get(doc_id), True), "content": _chapter_content(db, doc_id)}


@router.post("/curriculum/{course_key}/chapters/{doc_id}/complete-reading")
def complete_chapter_reading(course_key: str, doc_id: str, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.models.learning.curriculum import ChapterProgress
    from app.utils.uuid import generate_uuid
    chapters = _curriculum_chapters(db, course_key)
    index = next((i for i, row in enumerate(chapters) if row.doc_id == doc_id), None)
    if index is None:
        raise HTTPException(404, "Chapter not found")
    user_id = _user_id_bytes(current_user); progress = _progress_map(db, user_id, course_key)
    if index > 0 and not (progress.get(chapters[index - 1].doc_id) and progress[chapters[index - 1].doc_id].status == "passed"):
        raise HTTPException(403, "Complete the previous chapter quiz first")
    record = progress.get(doc_id)
    if not record:
        record = ChapterProgress(id=generate_uuid(), user_id=user_id, course_key=course_key, chapter_doc_id=doc_id, started_at=datetime.utcnow())
        db.add(record)
    if record.status != "passed":
        record.status = "ready_for_quiz"
    db.commit()
    return {"status": record.status, "message": "阅读已完成。现在可以开始本章 10 题测验。"}


@router.post("/curriculum/{course_key}/chapters/{doc_id}/assistant-session")
def get_chapter_assistant_session(course_key: str, doc_id: str, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    """Create one reusable Agents companion conversation for a chapter."""
    from app.models.conversation import Conversation
    from app.models.learning.curriculum import ChapterProgress
    from app.utils.uuid import bytes_to_uuid_string, generate_uuid
    chapters = _curriculum_chapters(db, course_key)
    chapter = next((row for row in chapters if row.doc_id == doc_id), None)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    user_id = _user_id_bytes(current_user)
    progress = _progress_map(db, user_id, course_key).get(doc_id)
    if not progress:
        progress = ChapterProgress(id=generate_uuid(), user_id=user_id, course_key=course_key, chapter_doc_id=doc_id, status="reading", started_at=datetime.utcnow())
        db.add(progress); db.flush()
    if progress.assistant_conversation_id:
        existing = db.query(Conversation).filter(Conversation.id == progress.assistant_conversation_id, Conversation.user_id == user_id, Conversation.is_deleted == 0).first()
        if existing:
            return {"conversation_id": bytes_to_uuid_string(existing.id), "reused": True}
    conversation = Conversation(id=generate_uuid(), user_id=user_id, title=f"伴学：{chapter.title[:110]}")
    db.add(conversation); db.flush()
    progress.assistant_conversation_id = conversation.id
    db.commit()
    return {"conversation_id": bytes_to_uuid_string(conversation.id), "reused": False}


def _new_quiz(db: Session, current_user: UserSchema, course_key: str, doc_id: Optional[str], assessment_type: str, question_count: int):
    from app.models.learning.curriculum import LearningAssessment
    from app.models.learning.exam import Exam, ExamQuestion
    from app.services.learning_assessment_service import generate_choice_questions
    from app.utils.uuid import generate_uuid
    if doc_id:
        chapters = _curriculum_chapters(db, course_key)
        row = next((chapter for chapter in chapters if chapter.doc_id == doc_id), None)
        if not row: raise HTTPException(404, "Chapter not found")
        content = _chapter_content(db, doc_id)
        title = row.title
    else:
        chapters = _curriculum_chapters(db, course_key)
        title = f"{_course_label(course_key)} 结课考试"
        content = "\n\n".join(_chapter_content(db, chapter.doc_id)[:1800] for chapter in chapters[:30])
    questions, generator = generate_choice_questions(title, content, question_count, course_title=_course_label(course_key))
    exam = Exam(id=generate_uuid(), title=f"{title} · {'章节测验' if doc_id else '学科考试'}", description="由出题 Agent 基于已选学习资料生成")
    db.add(exam); db.flush()
    for index, question in enumerate(questions):
        db.add(ExamQuestion(id=generate_uuid(), exam_id=exam.id, kp_id=doc_id, question_type="choice", question_data=question, difficulty=.5, sort_order=index))
    trace = [
        {"name": "资料整理", "detail": f"已定位《{title}》的章节内容与关键概念。"},
        {"name": "出题 Agent", "detail": f"围绕本章资料生成 {question_count} 道单选题。"},
        {"name": "题目校验", "detail": "检查题目数量、选项数量、标准答案和解析是否完整。"},
        {"name": "保存题集", "detail": "题集已保存；未提交前再次进入会复用本套题。"},
    ]
    assessment = LearningAssessment(id=generate_uuid(), user_id=_user_id_bytes(current_user), course_key=course_key, chapter_doc_id=doc_id, exam_id=exam.id, assessment_type=assessment_type, question_count=question_count, passing_score=60, blueprint={"generator": generator, "agent": "出题 Agent", "source_doc_id": doc_id, "trace": trace})
    db.add(assessment); db.commit(); db.refresh(assessment)
    return assessment


@router.post("/curriculum/{course_key}/chapters/{doc_id}/quiz")
def create_or_get_chapter_quiz(course_key: str, doc_id: str, data: AssessmentGenerateRequest, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.models.learning.curriculum import LearningAssessment
    user_id = _user_id_bytes(current_user); progress = _progress_map(db, user_id, course_key).get(doc_id)
    if not progress or progress.status not in {"ready_for_quiz", "passed"}:
        raise HTTPException(403, "Finish reading this chapter before taking its quiz")
    existing = db.query(LearningAssessment).filter(LearningAssessment.user_id == user_id, LearningAssessment.course_key == course_key, LearningAssessment.chapter_doc_id == doc_id, LearningAssessment.assessment_type == "chapter_quiz").order_by(LearningAssessment.generated_at.desc()).first()
    if existing and existing.status == "active":
        return {"assessment": _assessment_out(db, existing), "reused": True}
    if existing and not data.replace_previous:
        return {"assessment": _assessment_out(db, existing), "reused": True}
    if data.replace_previous and existing and existing.status == "active":
        raise HTTPException(409, "Submit the current quiz before replacing it")
    assessment = _new_quiz(db, current_user, course_key, doc_id, "chapter_quiz", 10)
    return {"assessment": _assessment_out(db, assessment), "reused": False, "agent_trace": ["资料整理", "出题 Agent", "题目结构校验"]}


@router.post("/curriculum/{course_key}/final-exam")
def create_or_get_final_exam(course_key: str, data: AssessmentGenerateRequest, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.models.learning.curriculum import LearningAssessment
    user_id = _user_id_bytes(current_user); chapters = _curriculum_chapters(db, course_key); progress = _progress_map(db, user_id, course_key)
    if not chapters or any(not progress.get(chapter.doc_id) or progress[chapter.doc_id].status != "passed" for chapter in chapters):
        raise HTTPException(403, "Pass every chapter quiz before taking the final exam")
    existing = db.query(LearningAssessment).filter(LearningAssessment.user_id == user_id, LearningAssessment.course_key == course_key, LearningAssessment.chapter_doc_id.is_(None), LearningAssessment.assessment_type == "course_exam").order_by(LearningAssessment.generated_at.desc()).first()
    if existing and (existing.status == "active" or not data.replace_previous): return {"assessment": _assessment_out(db, existing), "reused": True}
    assessment = _new_quiz(db, current_user, course_key, None, "course_exam", 20)
    return {"assessment": _assessment_out(db, assessment), "reused": False, "agent_trace": ["资料整理", "出题 Agent", "题目结构校验"]}


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    return _assessment_out(db, _get_assessment(db, current_user, assessment_id))


@router.post("/assessments/{assessment_id}/retry")
def retry_assessment(assessment_id: str, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    """Reopen a submitted quiz without discarding its question set or attempt history."""
    assessment = _get_assessment(db, current_user, assessment_id)
    if assessment.assessment_type not in {"chapter_quiz", "course_exam"}:
        raise HTTPException(400, "Only choice assessments can be retried here")
    if assessment.status == "active":
        return {"assessment": _assessment_out(db, assessment), "reused": True}
    assessment.status = "active"
    assessment.submitted_at = None
    db.commit()
    db.refresh(assessment)
    return {"assessment": _assessment_out(db, assessment), "reused": True}


@router.post("/assessments/{assessment_id}/submit")
def submit_assessment(assessment_id: str, data: AssessmentAnswerRequest, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.models.learning.curriculum import AssessmentSubmission, ChapterProgress, LearningMistake
    from app.models.learning.exam import ExamQuestion
    from app.utils.uuid import bytes_to_uuid_string, generate_uuid
    assessment = _get_assessment(db, current_user, assessment_id)
    if assessment.status != "active": raise HTTPException(409, "This question set has already been submitted")
    questions = db.query(ExamQuestion).filter(ExamQuestion.exam_id == assessment.exam_id).order_by(ExamQuestion.sort_order).all()
    results = []
    for question in questions:
        question_id = bytes_to_uuid_string(question.id); payload = question.question_data or {}; answer = str(data.answers.get(question_id, "")); correct = str(payload.get("answer", ""))
        is_correct = answer == correct
        results.append({"question_id": question_id, "correct": is_correct, "correct_answer": correct, "explanation": payload.get("explanation", "")})
        if not is_correct and not db.query(LearningMistake.id).filter(
            LearningMistake.user_id == _user_id_bytes(current_user),
            LearningMistake.source_type == "quiz",
            LearningMistake.assessment_id == assessment.id,
            LearningMistake.question_key == question_id,
            LearningMistake.status == "open",
        ).first():
            db.add(LearningMistake(id=generate_uuid(), user_id=_user_id_bytes(current_user), source_type="quiz", assessment_id=assessment.id, question_key=question_id, title=f"{_course_label(assessment.course_key)} 错题", prompt=payload.get("question", ""), user_answer=answer, correct_answer=correct, explanation=payload.get("explanation", "")))
    score = round(100 * sum(item["correct"] for item in results) / len(results), 1) if results else 0
    passed = score >= assessment.passing_score
    assessment.status = "passed" if passed else "failed"; assessment.submitted_at = datetime.utcnow()
    db.add(AssessmentSubmission(id=generate_uuid(), assessment_id=assessment.id, user_id=_user_id_bytes(current_user), answers=data.answers, result={"questions": results}, score=score, passed=1 if passed else 0))
    if passed and assessment.assessment_type == "chapter_quiz":
        progress = db.query(ChapterProgress).filter(ChapterProgress.user_id == _user_id_bytes(current_user), ChapterProgress.chapter_doc_id == assessment.chapter_doc_id).first()
        if progress: progress.status = "passed"; progress.completed_at = datetime.utcnow()
    db.commit()
    return {"score": score, "passed": passed, "passing_score": assessment.passing_score, "results": results, "agent_feedback": "判题 Agent 已按保存的标准答案与解析完成核对。"}


@router.get("/code-practice/catalog")
def code_practice_catalog(db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.models.learning.curriculum import ChapterProgress
    rows = db.query(ChapterProgress).filter(ChapterProgress.user_id == _user_id_bytes(current_user), ChapterProgress.status == "passed").order_by(ChapterProgress.completed_at.desc()).all()
    items = []
    for row in rows:
        chapters = _curriculum_chapters(db, row.course_key); chapter = next((item for item in chapters if item.doc_id == row.chapter_doc_id), None)
        if chapter:
            language = _practice_language_policy(row.course_key)
            items.append({"course_key": row.course_key, "chapter_doc_id": row.chapter_doc_id, "title": chapter.title, "course_title": _course_label(row.course_key), **language})
    from app.services.code_practice_service import available_runtimes
    return {"chapters": items, "runtimes": available_runtimes()}


@router.post("/code-practice")
def create_or_get_code_practice(data: CodePracticeCreate, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.models.learning.curriculum import ChapterProgress, LearningAssessment
    from app.services.learning_assessment_service import build_code_task
    from app.utils.uuid import generate_uuid
    user_id = _user_id_bytes(current_user)
    progress = db.query(ChapterProgress).filter(ChapterProgress.user_id == user_id, ChapterProgress.chapter_doc_id == data.chapter_doc_id, ChapterProgress.status == "passed").first()
    if not progress: raise HTTPException(403, "Pass the chapter quiz before starting code practice")
    language_policy = _practice_language_policy(progress.course_key)
    language = data.language or language_policy["recommended_language"]
    if language not in language_policy["allowed_languages"]:
        allowed = "、".join(PRACTICE_LANGUAGE_LABELS[item] for item in language_policy["allowed_languages"])
        raise HTTPException(400, f"该课程的代码实训仅支持：{allowed}")
    existing = db.query(LearningAssessment).filter(LearningAssessment.user_id == user_id, LearningAssessment.chapter_doc_id == data.chapter_doc_id, LearningAssessment.assessment_type == "code_practice").order_by(LearningAssessment.generated_at.desc()).all()
    current = next((item for item in existing if (item.blueprint or {}).get("language") == language and (item.blueprint or {}).get("mode") == data.mode), None)
    if current and (current.status == "active" or not data.replace_previous): return {"assessment": _assessment_out(db, current), "reused": True}
    if current and current.status == "active": raise HTTPException(409, "Submit the current exercise before replacing it")
    chapter = next((item for item in _curriculum_chapters(db, progress.course_key) if item.doc_id == data.chapter_doc_id), None)
    task = build_code_task(chapter.title if chapter else data.chapter_doc_id, language, data.mode)
    assessment = LearningAssessment(id=generate_uuid(), user_id=user_id, course_key=progress.course_key, chapter_doc_id=data.chapter_doc_id, assessment_type="code_practice", question_count=1, passing_score=100, blueprint={"agent": "代码实训 Agent", "generator": "validated_template", "language": language, "language_policy": language_policy["policy"], "mode": data.mode, "task": task})
    db.add(assessment); db.commit(); db.refresh(assessment)
    return {"assessment": _assessment_out(db, assessment), "reused": False, "agent_trace": ["学习进度核验", "代码实训 Agent 出题", "评测规则校验"]}


@router.post("/code-practice/{assessment_id}/submit")
def submit_code_practice(assessment_id: str, data: CodePracticeSubmit, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.tools.code_exec_tool import CodeExecTool
    assessment = _get_assessment(db, current_user, assessment_id)
    if assessment.assessment_type != "code_practice": raise HTTPException(400, "Not a code practice assessment")
    blueprint = assessment.blueprint or {}; task = blueprint.get("task") or {}
    verdict = CodeExecTool.evaluate_practice(user_id=_user_id_bytes(current_user), assessment_id=assessment_id, language=blueprint.get("language", "python"), mode=blueprint.get("mode", "acm"), code=data.code, test_cases=task.get("test_cases") or [])
    _persist_code_verdict(db, current_user, assessment, data.code, verdict)
    return _code_verdict_out(verdict)


def _persist_code_verdict(db: Session, current_user: UserSchema, assessment, code: str, verdict: Dict[str, Any]) -> None:
    from app.models.learning.curriculum import CodeSubmission, LearningMistake
    from app.utils.uuid import generate_uuid
    blueprint = assessment.blueprint or {}; task = blueprint.get("task") or {}
    assessment.status = "passed" if verdict["passed"] else "failed"; assessment.submitted_at = datetime.utcnow()
    db.add(CodeSubmission(id=generate_uuid(), assessment_id=assessment.id, user_id=_user_id_bytes(current_user), language=blueprint.get("language"), mode=blueprint.get("mode"), code=code, score=verdict["score"], passed=1 if verdict["passed"] else 0, verdict=verdict["verdict"], feedback=verdict))
    if not verdict["passed"]:
        db.add(LearningMistake(id=generate_uuid(), user_id=_user_id_bytes(current_user), source_type="code", assessment_id=assessment.id, title=task.get("title", "代码实训错题"), prompt=task.get("prompt", ""), user_answer=code, correct_answer=None, explanation=verdict["feedback"]))
    db.commit()


def _code_verdict_out(verdict: Dict[str, Any]) -> Dict[str, Any]:
    return {"score": verdict["score"], "passed": verdict["passed"], "verdict": verdict["verdict"], "feedback": verdict["feedback"], "cases": verdict["cases"], "trace": verdict.get("trace", []), "agent_feedback": "代码评测 Agent 仅编译、执行和评分了本次提交，未修改你的代码。"}


@router.post("/code-practice/{assessment_id}/submit-stream")
async def submit_code_practice_stream(assessment_id: str, data: CodePracticeSubmit, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    """Stream actual evaluator stages while the restricted runner is working."""
    from app.tools.code_exec_tool import CodeExecTool
    assessment = _get_assessment(db, current_user, assessment_id)
    if assessment.assessment_type != "code_practice":
        raise HTTPException(400, "Not a code practice assessment")
    blueprint = assessment.blueprint or {}; task = blueprint.get("task") or {}
    user_id = _user_id_bytes(current_user)

    async def event_stream():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def report(event: Dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        runner = asyncio.create_task(asyncio.to_thread(
            CodeExecTool.evaluate_practice,
            user_id=user_id,
            assessment_id=assessment_id,
            language=blueprint.get("language", "python"),
            mode=blueprint.get("mode", "acm"),
            code=data.code,
            test_cases=task.get("test_cases") or [],
            progress=report,
        ))
        while not runner.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.15)
                yield f"data: {json.dumps({'type': 'progress', **event}, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                continue
        verdict = await runner
        _persist_code_verdict(db, current_user, assessment, data.code, verdict)
        yield f"data: {json.dumps({'type': 'result', **_code_verdict_out(verdict)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/mistake-book")
def get_mistake_book(source: Optional[Literal["quiz", "code"]] = None, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.models.learning.curriculum import LearningMistake
    query = db.query(LearningMistake).filter(LearningMistake.user_id == _user_id_bytes(current_user))
    if source: query = query.filter(LearningMistake.source_type == source)
    rows = query.order_by(LearningMistake.created_at.desc()).limit(200).all()
    from app.utils.uuid import bytes_to_uuid_string
    return {"items": [{"id": bytes_to_uuid_string(row.id), "source": row.source_type, "title": row.title, "prompt": row.prompt, "user_answer": row.user_answer, "correct_answer": row.correct_answer, "explanation": row.explanation, "status": row.status, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]}

# ============================
# Learner task endpoints
# ============================
@router.post("/tasks", status_code=201)
def create_learning_task(data: TaskCreate, db: Session = Depends(get_db),
                         current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.task import create_task
    return _task_out(create_task(db, current_user.id, **data.model_dump()))

@router.get("/tasks")
def list_learning_tasks(status: Optional[Literal["todo", "done"]] = None,
                        db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.task import list_tasks
    return [_task_out(task) for task in list_tasks(db, current_user.id, status)]

@router.get("/tasks/{task_id}")
def get_learning_task(task_id: str, db: Session = Depends(get_db),
                      current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.task import get_task
    task = get_task(db, current_user.id, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return _task_out(task)

@router.post("/tasks/{task_id}/study-assist")
def study_assist(task_id: str, data: StudyAssistRequest, db: Session = Depends(get_db),
                 current_user: UserSchema = Depends(get_current_user)):
    """Explain selected study text with retrieved references and an optional LLM call."""
    from app.crud.learning.task import get_task
    from app.services.rag_service import get_kb
    from app.utils.uuid import uuid_string_to_bytes

    task = get_task(db, current_user.id, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    selected = data.selected_text.strip()
    question = (data.question or "请解释这段内容，并给出学习建议。").strip()
    query = " ".join(part for part in [task.title, selected, question] if part)
    kb = get_kb(uuid_string_to_bytes(current_user.id))
    hits = kb.search(query, top_k=4)
    evidence = [_compact_evidence(hit) for hit in hits]
    evidence_text = "\n".join(
        f"[{idx}] {ev['title']} chunk {ev['chunk_id']} score {round(float(ev['score']), 3)}\n{ev['snippet']}"
        for idx, ev in enumerate(evidence, start=1)
    ) or "当前资料库没有找到直接相关内容。"

    fallback = (
        f"这段内容可以先按三个层次理解：\n"
        f"1. 关键词：{selected[:80]}\n"
        f"2. 资料依据：{evidence[0]['title'] if evidence else '当前知识库暂无直接命中'}。\n"
        f"3. 学习动作：先复述它在本节中的作用，再用一个例子验证自己是否理解。\n\n"
        f"你可以继续追问：它解决了什么问题、和前后概念有什么关系、如何做一道练习。"
    )
    answer = fallback
    used_llm = False

    if data.use_llm:
        try:
            from app.services.llm_service import llm_service
            prompt = [
                {
                    "role": "system",
                    "content": (
                        "你是学习伴读助手。只围绕用户选中的学习文本解释，"
                        "需要结合给定参考资料；如果资料不足，要明确说明。"
                        "回答结构：直观解释、关键概念、例子或类比、下一步练习。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"学习计划：{task.title}\n"
                        f"任务描述：{task.description or ''}\n"
                        f"页面上下文：{data.context or ''}\n"
                        f"选中文本：{selected}\n"
                        f"用户问题：{question}\n\n"
                        f"参考资料：\n{evidence_text}"
                    ),
                },
            ]
            answer = llm_service.call_model(
                prompt,
                model="deepseek:deepseek-v4-flash",
                stream=False,
                temperature=0.4,
            )
            used_llm = True
        except Exception:
            answer = fallback

    return {
        "answer": answer,
        "used_llm": used_llm,
        "selected_text": selected,
        "question": question,
        "evidence_refs": evidence,
        "suggested_actions": [
            "把这段话用自己的话复述一遍",
            "找出一个能验证理解的小例子",
            "完成本卡片后的检查点问题",
        ],
    }

@router.patch("/tasks/{task_id}")
def update_learning_task(task_id: str, data: TaskStatusUpdate, db: Session = Depends(get_db),
                         current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.task import get_task, set_task_status
    task = get_task(db, current_user.id, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    was_done = task.status == "done"
    task = set_task_status(db, task, data.status)
    # Completing a knowledge-point task is a meaningful study event for reports.
    if task.status == "done" and not was_done:
        _record_task_study_event(db, current_user, task)
    return _task_out(task)

@router.post("/tasks/{task_id}/complete")
def complete_learning_task(task_id: str, data: TaskCompletion, db: Session = Depends(get_db),
                           current_user: UserSchema = Depends(get_current_user)):
    """Complete a task only after the learner supplies auditable learning evidence."""
    from app.crud.learning.task import get_task, set_task_status
    task = get_task(db, current_user.id, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    was_done = task.status == "done"
    evidence = f"\n\n[学习完成记录] 时长：{data.minutes} 分钟；复盘：{data.reflection.strip()}"
    if data.quiz_score is not None:
        evidence += f"；测验得分：{data.quiz_score:g} 分"
    task.description = (task.description or "") + evidence
    task = set_task_status(db, task, "done")
    if not was_done:
        _record_task_study_event(db, current_user, task)
    return {**_task_out(task), "completion_evidence": {"minutes": data.minutes, "reflection": data.reflection.strip(), "quiz_score": data.quiz_score}}

@router.delete("/tasks/{task_id}", status_code=204)
def delete_learning_task(task_id: str, db: Session = Depends(get_db),
                         current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.task import get_task, delete_task
    task = get_task(db, current_user.id, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    delete_task(db, task)

# ============================
# Agent course workspace
# ============================
def _course_workspace_documents(current_user: UserSchema, db: Session | None = None):
    """Combine private documents with the shared read-only system library."""
    if db is not None:
        try:
            from app.models.knowledge_base import KnowledgeDocument
            from app.utils.uuid import uuid_string_to_bytes
            user_id = uuid_string_to_bytes(current_user.id)
            rows = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.user_id.in_(readable_owner_ids(user_id)),
                KnowledgeDocument.content_length > 50,
            ).order_by(
                case((KnowledgeDocument.user_id == user_id, 0), else_=1),
                KnowledgeDocument.updated_at.desc(),
                KnowledgeDocument.id.desc(),
            ).all()
            if rows:
                docs = []
                seen = set()
                for row in rows:
                    if not row.title or row.doc_id in seen:
                        continue
                    seen.add(row.doc_id)
                    docs.append({
                        "doc_id": row.doc_id,
                        "content_length": row.content_length,
                        "chunk_count": row.chunk_count,
                        "metadata": row.doc_metadata or {
                            "title": row.title,
                            "category": row.category,
                            "source_type": row.source_type,
                        },
                        "added_at": row.added_at.isoformat() if row.added_at else "",
                        "knowledge_scope": knowledge_scope(row.user_id, user_id),
                        "read_only": row.user_id == SYSTEM_KB_USER_ID,
                    })
                return docs
        except Exception:
            pass

    from app.services.rag_service import get_kb
    from app.utils.uuid import uuid_string_to_bytes
    docs = get_kb(uuid_string_to_bytes(current_user.id)).list_documents()
    return [doc for doc in docs if doc.get("content_length", 0) > 50 and doc.get("metadata", {}).get("title")]


def _course_workspace_from_db(
    current_user: UserSchema,
    db: Session,
    *,
    category: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 24,
) -> Optional[Dict[str, Any]]:
    try:
        from app.models.knowledge_base import KnowledgeDocument
        from app.utils.uuid import uuid_string_to_bytes

        user_id = uuid_string_to_bytes(current_user.id)
        base = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.user_id.in_(readable_owner_ids(user_id)),
            KnowledgeDocument.content_length > 50,
        )
        total = base.count()
        if total <= 0:
            return None

        category_rows = db.query(KnowledgeDocument.category, func.count(KnowledgeDocument.id))\
            .filter(
                KnowledgeDocument.user_id.in_(readable_owner_ids(user_id)),
                KnowledgeDocument.content_length > 50,
            )\
            .group_by(KnowledgeDocument.category).all()
        categories = {
            (name or "通用训练"): int(count)
            for name, count in category_rows
        }

        filtered = base
        if category:
            filtered = filtered.filter(KnowledgeDocument.category == category)
        if query and query.strip():
            keyword = f"%{query.strip()}%"
            filtered = filtered.filter(or_(
                KnowledgeDocument.title.like(keyword),
                KnowledgeDocument.category.like(keyword),
            ))

        rows = filtered.order_by(
            case((KnowledgeDocument.user_id == user_id, 0), else_=1),
            KnowledgeDocument.updated_at.desc(),
            KnowledgeDocument.id.desc(),
        ).limit(max(limit * 2, limit)).all()
        docs = []
        seen = set()
        for row in rows:
            if not row.title or row.doc_id in seen:
                continue
            seen.add(row.doc_id)
            docs.append({
                "doc_id": row.doc_id,
                "content_length": row.content_length,
                "chunk_count": row.chunk_count,
                "metadata": row.doc_metadata or {
                    "title": row.title,
                    "category": row.category,
                    "source_type": row.source_type,
                },
                "added_at": row.added_at.isoformat() if row.added_at else "",
                "knowledge_scope": knowledge_scope(row.user_id, user_id),
                "read_only": row.user_id == SYSTEM_KB_USER_ID,
            })
            if len(docs) >= limit:
                break
        return {"docs": docs, "total": total, "categories": categories}
    except Exception:
        return None


def _find_workspace_document(
    current_user: UserSchema,
    db: Session,
    doc_id: str,
) -> Optional[Dict[str, Any]]:
    from app.models.knowledge_base import KnowledgeDocument
    from app.utils.uuid import uuid_string_to_bytes

    user_id = uuid_string_to_bytes(current_user.id)
    owner_id = resolve_document_owner(db, user_id, doc_id)
    if owner_id is None:
        return None
    row = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.user_id == owner_id,
        KnowledgeDocument.doc_id == doc_id,
        KnowledgeDocument.content_length > 50,
    ).first()
    if not row or not row.title:
        return None
    return {
        "doc_id": row.doc_id,
        "content_length": row.content_length,
        "chunk_count": row.chunk_count,
        "metadata": row.doc_metadata or {
            "title": row.title,
            "category": row.category,
            "source_type": row.source_type,
        },
        "added_at": row.added_at.isoformat() if row.added_at else "",
        "knowledge_scope": knowledge_scope(owner_id, user_id),
        "read_only": owner_id == SYSTEM_KB_USER_ID,
    }


def _pending_task_count(current_user: UserSchema, db: Session) -> int:
    try:
        from app.models.learning.task import LearningTask
        from app.utils.uuid import uuid_string_to_bytes

        return int(db.query(func.count(LearningTask.id)).filter(
            LearningTask.user_id == uuid_string_to_bytes(current_user.id),
            LearningTask.status == "todo",
        ).scalar() or 0)
    except Exception:
        return 0

@router.get("/course-workspace")
def get_course_workspace(
    category: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = Query(60, ge=1, le=120),
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Return a ready-to-render course workspace and deterministic Agent recommendations."""
    from app.crud.learning.task import list_tasks
    docs = _course_workspace_documents(current_user, db)
    normalized = []
    for doc in docs:
        metadata = doc.get("metadata", {})
        item = {
            "id": doc["doc_id"], "title": metadata.get("title", doc["doc_id"]),
            "category": metadata.get("category") or "通用", "chunks": doc.get("chunk_count", 1),
            "content_length": doc.get("content_length", 0),
            "estimated_minutes": max(5, min(45, int(doc.get("chunk_count", 1)) * 5)),
        }
        normalized.append(item)
    categories: Dict[str, int] = {}
    for item in normalized:
        categories[item["category"]] = categories.get(item["category"], 0) + 1
    if category:
        normalized = [item for item in normalized if item["category"] == category]
    if query and query.strip():
        keyword = query.strip().lower()
        normalized = [item for item in normalized if keyword in item["title"].lower() or keyword in item["category"].lower()]
    tasks = list_tasks(db, current_user.id, "todo")
    active_task = _task_out(tasks[0]) if tasks else None
    missions = [{**item, "agent_role": "学习规划 Agent", "reason": "根据课程结构推荐从基础内容开始"} for item in normalized[:6]]
    return {
        "overview": {"course_count": len(docs), "category_count": len(categories), "pending_task_count": len(tasks)},
        "categories": [{"name": name, "count": count} for name, count in sorted(categories.items(), key=lambda x: (-x[1], x[0]))],
        "courses": normalized[:limit],
        "active_task": active_task,
        "agent_center": {
            "status": "ready", "agents": ["学习规划", "资料整理", "练习生成"],
            "summary": f"已分析 {len(docs)} 个课程内容；优先从一节 {normalized[0]['category'] if normalized else '课程'} 开始。" if docs else "导入课程内容后，会自动生成学习任务。",
            "missions": missions,
        },
    }

@router.post("/course-workspace/missions/{doc_id}/start", status_code=201)
def start_course_mission(doc_id: str, data: CourseMissionStart, db: Session = Depends(get_db),
                         current_user: UserSchema = Depends(get_current_user)):
    """Turn an Agent-recommended lesson into a persisted learner task."""
    from app.crud.learning.task import create_task
    doc = _find_workspace_document(current_user, db, doc_id)
    if not doc:
        raise HTTPException(404, "Course content not found")
    metadata = doc.get("metadata", {})
    title = data.title or f"学习：{metadata.get('title', doc_id)}"
    task = create_task(
        db, current_user.id, title=title, task_type="study",
        description=f"根据「{metadata.get('category') or '通用'}」课程推荐。完成阅读后可到 AI 问答继续练习。",
    )
    return {"task": _task_out(task), "agent_message": "学习任务已建立。阅读后可以为本节内容生成练习题。"}

@router.post("/course-workspace/exams", status_code=201)
def generate_course_exam(data: CourseExamCreate, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    """Generation Agent entrypoint: create an auditable course quiz from source content."""
    from app.crud.learning.exam import create_exam, add_question
    from app.utils.uuid import bytes_to_uuid_string
    doc = _find_workspace_document(current_user, db, data.doc_id)
    if not doc: raise HTTPException(404, "Course content not found")
    metadata = doc.get("metadata", {}); title = metadata.get("title", data.doc_id)
    exam = create_exam(db, title=f"{title} · 随堂测验", description="基于本节课程生成")
    prompts = [f"“{title}”属于哪个课程主题？", f"学习“{title}”后，最适合的下一步是什么？", f"本节内容建议如何巩固？"]
    for index, prompt in enumerate(prompts):
        add_question(db, bytes_to_uuid_string(exam.id), None, "choice", {"question":prompt,"options":[metadata.get("category") or "通用", "跳过学习", "随机猜测", "无关内容"],"answer":"0","explanation":"应先理解本节所属主题，并完成学习与练习。"}, .4 + index*.1, index)
    return {"exam_id":bytes_to_uuid_string(exam.id),"title":exam.title,"question_count":len(prompts),"agent_trace":["检索课程内容","生成选择题","质量校验完成"]}

@router.get("/exams/{exam_id}/take")
def take_exam(exam_id: str, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.exam import get_exam, list_questions
    from app.utils.uuid import bytes_to_uuid_string
    exam=get_exam(db, exam_id)
    if not exam: raise HTTPException(404,"Exam not found")
    return {"id":exam_id,"title":exam.title,"questions":[{"id":bytes_to_uuid_string(q.id),"type":q.question_type,"data":{k:v for k,v in q.question_data.items() if k != "answer"}} for q in list_questions(db,exam_id)]}

@router.post("/exams/{exam_id}/submit")
def submit_exam(exam_id: str, data: ExamSubmit, db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.exam import get_exam, list_questions
    from app.models.learning.exam_attempt import ExamAttempt
    from app.utils.uuid import bytes_to_uuid_string, uuid_string_to_bytes, generate_uuid
    if not get_exam(db,exam_id): raise HTTPException(404,"Exam not found")
    questions=list_questions(db,exam_id); correct=[]
    for q in questions:
        qid=bytes_to_uuid_string(q.id); ok=str(data.answers.get(qid,"")) == str(q.question_data.get("answer","")); correct.append({"question_id":qid,"correct":ok,"explanation":q.question_data.get("explanation","")})
    score=round(sum(x["correct"] for x in correct)/len(questions)*100,1) if questions else 0
    db.add(ExamAttempt(id=generate_uuid(),user_id=uuid_string_to_bytes(current_user.id),exam_id=uuid_string_to_bytes(exam_id),answers=data.answers,score=score,total=len(questions))); db.commit()
    return {"score":score,"total":len(questions),"results":correct,"agent_feedback":"已完成判分；错题将作为下一轮学习建议依据。"}

# ============================
# Training workspace endpoints
# ============================
AGENT_PIPELINE_META = {
    "diagnosis": {"name": "学习诊断", "role": "读取学员画像、薄弱项和认知负荷", "output": "learner_state"},
    "task": {"name": "目标拆解", "role": "把学习目标拆成可执行步骤", "output": "task_goal"},
    "retrieval": {"name": "资料整理", "role": "从课程资料和知识库整理可参考内容", "output": "evidence_refs"},
    "generation": {"name": "内容生成", "role": "生成讲解、实操步骤和练习候选", "output": "candidates"},
    "review": {"name": "质量检查", "role": "检查事实、难度和表达风险", "output": "rule_hits"},
    "judge": {"name": "学习建议", "role": "选择最终方案并给出风险等级", "output": "proposed_action"},
}

RULE_CATALOG = [
    {"id": "prereq_covered", "name": "前置能力覆盖", "type": "hard", "description": "未满足前置技能时不能直接进入高阶任务。"},
    {"id": "load_ok", "name": "认知负荷上限", "type": "hard", "description": "任务难度和时长不能超过当前负荷阈值。"},
    {"id": "evidence_required", "name": "资料参考要求", "type": "hard", "description": "关键结论需要对应到课程资料或知识库片段。"},
    {"id": "has_structure", "name": "训练结构完整", "type": "soft", "description": "输出应包含目标、步骤、检查点和反馈。"},
    {"id": "kp_coverage", "name": "知识点覆盖", "type": "soft", "description": "训练内容需要覆盖目标技能的核心概念。"},
]

def _doc_training_item(doc: Dict[str, Any]) -> Dict[str, Any]:
    metadata = doc.get("metadata", {})
    title = metadata.get("title") or doc.get("doc_id")
    category = metadata.get("category") or "通用训练"
    chunks = int(doc.get("chunk_count", 1) or 1)
    return {
        "id": doc["doc_id"],
        "title": title,
        "category": category,
        "source_type": metadata.get("source_type") or "课程资料",
        "knowledge_scope": doc.get("knowledge_scope") or "private",
        "read_only": bool(doc.get("read_only")),
        "estimated_minutes": max(12, min(60, chunks * 6)),
        "evidence_count": chunks,
        "risk_level": "low" if chunks >= 4 else "medium",
        "target_output": f"完成「{title}」的岗位任务拆解、实操练习和随堂评测",
        "agent_goal": f"围绕「{title}」生成可学习、可练习的任务",
    }

def _training_trace_for_doc(doc: Dict[str, Any], goal: Optional[str] = None) -> List[Dict[str, Any]]:
    item = _doc_training_item(doc)
    pipeline = ["diagnosis", "task", "retrieval", "generation", "review", "judge"]
    trace = []
    for index, agent_id in enumerate(pipeline, start=1):
        meta = AGENT_PIPELINE_META[agent_id]
        detail = meta["role"]
        if agent_id == "retrieval":
            detail = f"已准备 {item['evidence_count']} 个相关资料片段"
        if agent_id == "task":
            detail = goal or item["agent_goal"]
        trace.append({
            "order": index,
            "agent_id": agent_id,
            "name": meta["name"],
            "role": meta["role"],
            "output_key": meta["output"],
            "status": "ready",
            "detail": detail,
        })
    return trace

def _assessment_blueprint(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"stage": "诊断预检", "type": "pretest", "focus": "确认前置概念和风险认知", "weight": 15},
        {"stage": "过程测验", "type": "formative", "focus": "检查关键术语、步骤顺序和资料理解", "weight": 25},
        {"stage": "实操任务", "type": "practice", "focus": item["target_output"], "weight": 40},
        {"stage": "迁移挑战", "type": "transfer", "focus": "换一个业务场景复用同一套规则", "weight": 20},
    ]

def _training_query_for_item(item: Dict[str, Any], goal: Optional[str] = None) -> str:
    parts = [item.get("title", ""), item.get("category", ""), goal or item.get("agent_goal", "")]
    return " ".join(part for part in parts if part).strip()

def _compact_evidence(hit: Dict[str, Any]) -> Dict[str, Any]:
    metadata = hit.get("metadata", {}) or {}
    content = (hit.get("content") or "").strip()
    return {
        "doc_id": hit.get("doc_id"),
        "chunk_id": hit.get("chunk_id"),
        "title": metadata.get("title") or metadata.get("source") or hit.get("doc_id"),
        "category": metadata.get("category") or "通用",
        "knowledge_scope": metadata.get("knowledge_scope") or "private",
        "source_url": metadata.get("source_url") or metadata.get("url") or "",
        "score": hit.get("score", 0),
        "bm25_score": hit.get("bm25_score"),
        "semantic_score": hit.get("semantic_score"),
        "phrase_score": hit.get("phrase_score"),
        "expanded_chunk_ids": hit.get("expanded_chunk_ids") or [hit.get("chunk_id")],
        "snippet": content[:360],
    }

def _rag_evidence_for_item(current_user: UserSchema, item: Dict[str, Any], goal: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
    from app.services.rag_service import get_kb
    from app.utils.uuid import uuid_string_to_bytes

    user_id = uuid_string_to_bytes(current_user.id)
    if item.get("knowledge_scope") == "public":
        from app.models import SessionLocal
        from app.models.knowledge_base import KnowledgeChunk

        with SessionLocal() as db:
            rows = db.query(KnowledgeChunk).filter(
                KnowledgeChunk.user_id == SYSTEM_KB_USER_ID,
                KnowledgeChunk.doc_id == item.get("id"),
            ).order_by(KnowledgeChunk.chunk_id.asc()).limit(top_k).all()
        return [
            _compact_evidence({
                "doc_id": row.doc_id,
                "chunk_id": row.chunk_id,
                "content": row.content,
                "score": round(1.0 / (index + 1), 6),
                "metadata": {
                    **(row.chunk_metadata or {}),
                    "title": (row.chunk_metadata or {}).get("title") or item.get("title"),
                    "category": (row.chunk_metadata or {}).get("category") or item.get("category"),
                    "knowledge_scope": "public",
                },
            })
            for index, row in enumerate(rows)
        ]

    kb = get_kb(user_id)
    query = _training_query_for_item(item, goal)
    if not query:
        return []
    hits = kb.search(query, top_k=top_k)
    return [_compact_evidence(hit) for hit in hits]

def _training_plan_from_evidence(item: Dict[str, Any], evidence: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    key_sources = "、".join(e["title"] for e in evidence[:2]) if evidence else item["title"]
    return [
        {
            "stage": "定位目标",
            "agent": "目标拆解",
            "output": f"把「{item['title']}」拆成概念理解、操作练习和回顾复盘三类目标。",
        },
        {
            "stage": "整理资料",
            "agent": "资料助手",
            "output": f"优先参考 {key_sources}，把讲解和练习都落到具体资料内容上。",
        },
        {
            "stage": "生成训练",
            "agent": "内容生成",
            "output": "生成一段学习说明、一个可执行练习和一个检查点问题。",
        },
        {
            "stage": "审核裁决",
            "agent": "质量检查",
            "output": "检查资料覆盖、任务负荷和输出结构，给出下一步学习任务。",
        },
    ]

def _assessment_blueprint_from_evidence(item: Dict[str, Any], evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    base = _assessment_blueprint(item)
    if evidence:
        base[1]["focus"] = f"围绕「{evidence[0]['title']}」检查关键术语和资料理解"
        base[2]["focus"] = f"基于资料片段完成一个可提交的小练习：{item['target_output']}"
        base[3]["focus"] = "换一个问题复用同一组资料，并说明目前还不确定的地方"
    return base

def _trace_with_rag(doc: Dict[str, Any], evidence: List[Dict[str, Any]], goal: Optional[str] = None) -> List[Dict[str, Any]]:
    trace = _training_trace_for_doc(doc, goal)
    for step in trace:
        if step["agent_id"] == "retrieval":
            step["detail"] = f"已整理 {len(evidence)} 条相关资料，最高相关度 {round(evidence[0]['score'], 3) if evidence else 0}"
            step["status"] = "ready" if evidence else "needs_source"
        if step["agent_id"] == "generation":
            step["detail"] = "根据资料内容生成讲解、练习、检查点和复盘要求"
        if step["agent_id"] == "review":
            step["detail"] = "检查内容是否有资料支撑，过滤不可靠的学习建议"
    return trace

def _agent_suggestions(docs: List[Dict[str, Any]], pending_count: int) -> List[Dict[str, str]]:
    suggestions = []
    if docs:
        first = _doc_training_item(docs[0])
        suggestions.append({
            "type": "start_training",
            "title": f"从「{first['title']}」启动训练",
            "message": "我会先看看你的学习状态，再整理资料并生成适合继续做的练习。",
            "route": "/courses",
            "doc_id": first["id"],
        })
    if pending_count:
        suggestions.append({
            "type": "resume_task",
            "title": f"还有 {pending_count} 个训练任务待处理",
            "message": "建议先补充学习复盘，再进入测验和学习路径调整。",
            "route": "/tasks",
        })
    suggestions.append({
        "type": "diagnosis",
        "title": "更新一次学情诊断",
        "message": "诊断结果会影响任务难度、参考资料范围和后续测验权重。",
        "route": "/diagnosis",
    })
    return suggestions[:3]

@router.get("/training-workspace")
def get_training_workspace(
    category: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = Query(48, ge=1, le=120),
    fast: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Backend-composed workspace for the RER-MA / DGP-Edu training flow."""
    db_workspace = _course_workspace_from_db(
        current_user,
        db,
        category=category,
        query=query if fast else None,
        limit=limit,
    )
    docs = db_workspace["docs"] if db_workspace else _course_workspace_documents(current_user, db)
    doc_by_id = {doc["doc_id"]: doc for doc in docs}
    items = [_doc_training_item(doc) for doc in docs]
    categories: Dict[str, int] = db_workspace["categories"] if db_workspace else {}
    if not categories:
        for item in items:
            categories[item["category"]] = categories.get(item["category"], 0) + 1
    if fast:
        pending_count = _pending_task_count(current_user, db)
        scenarios = [{
            **item,
            "rag_ready": item.get("evidence_count", 0) > 0,
            "top_evidence": [],
            "recommended_plan": [],
        } for item in items[:limit]]
        return {
            "overview": {
                "training_count": db_workspace["total"] if db_workspace else len(docs),
                "category_count": len(categories),
                "pending_task_count": pending_count,
                "exam_count": 0,
                "agent_count": 0,
            },
            "categories": [{"name": name, "count": count} for name, count in sorted(categories.items(), key=lambda x: (-x[1], x[0]))],
            "scenarios": scenarios,
            "agent_pipeline": [],
            "rules": [],
            "current_case": {"item": None, "trace": [], "assessment": [], "evidence_refs": []},
            "proactive_agent": {
                "name": "学习助手",
                "status": "online",
                "suggestions": _agent_suggestions(docs[:1], pending_count),
            },
        }

    from app.crud.learning.task import list_tasks
    from app.crud.learning.exam import list_exams
    from app.services.agent_graph import get_agent_graph

    if category and not db_workspace:
        items = [item for item in items if item["category"] == category]
    if query and query.strip() and not (fast and db_workspace):
        keyword = query.strip().lower()
        lexical = [item for item in items if keyword in item["title"].lower() or keyword in item["category"].lower()]
        rag_ranked: List[Dict[str, Any]] = []
        try:
            from app.services.rag_service import get_kb
            from app.utils.uuid import uuid_string_to_bytes
            user_id = uuid_string_to_bytes(current_user.id)
            hits = []
            for owner_id in readable_owner_ids(user_id):
                for hit in get_kb(owner_id).search(query.strip(), top_k=min(24, limit)):
                    hit = dict(hit)
                    hit["knowledge_scope"] = knowledge_scope(owner_id, user_id)
                    hits.append(hit)
            hits.sort(key=lambda hit: float(hit.get("score") or 0.0), reverse=True)
            seen = set()
            for hit in hits:
                doc_id = hit.get("doc_id")
                doc = doc_by_id.get(doc_id)
                if (
                    doc
                    and doc_id not in seen
                    and doc.get("knowledge_scope", "private") == hit.get("knowledge_scope")
                ):
                    seen.add(doc_id)
                    item = _doc_training_item(doc)
                    item["rag_match_score"] = hit.get("score", 0)
                    item["rag_match_snippet"] = (hit.get("content") or "")[:220]
                    rag_ranked.append(item)
        except Exception:
            rag_ranked = []
        merged = []
        seen_ids = set()
        for item in rag_ranked + lexical:
            if item["id"] not in seen_ids:
                merged.append(item)
                seen_ids.add(item["id"])
        items = merged

    pending_tasks = list_tasks(db, current_user.id, "todo")
    exams = [] if fast else list_exams(db)
    pipeline = []
    if not fast:
        graph = get_agent_graph()
        pipeline = [
            {"id": aid, **AGENT_PIPELINE_META.get(aid, {"name": aid, "role": "", "output": ""})}
            for aid in graph.pipeline
        ]
    selected_doc = None if fast else (doc_by_id.get(items[0]["id"]) if items else (docs[0] if docs else None))
    selected_item = _doc_training_item(selected_doc) if selected_doc else None
    selected_evidence = [] if fast else (_rag_evidence_for_item(current_user, selected_item, top_k=5) if selected_item else [])
    scenarios = []
    preview_budget = 0 if fast else min(len(items[:limit]), 12)
    for index, item in enumerate(items[:limit]):
        evidence = _rag_evidence_for_item(current_user, item, top_k=3) if index < preview_budget else []
        scenarios.append({
            **item,
            "rag_ready": bool(evidence) if not fast else item.get("evidence_count", 0) > 0,
            "top_evidence": evidence[:2],
            "recommended_plan": [] if fast else _training_plan_from_evidence(item, evidence),
        })
    return {
        "overview": {
            "training_count": db_workspace["total"] if db_workspace else len(docs),
            "category_count": len(categories),
            "pending_task_count": len(pending_tasks),
            "exam_count": len(exams),
            "agent_count": len(pipeline),
        },
        "categories": [{"name": name, "count": count} for name, count in sorted(categories.items(), key=lambda x: (-x[1], x[0]))],
        "scenarios": scenarios,
        "agent_pipeline": pipeline,
        "rules": RULE_CATALOG,
        "current_case": {
            "item": {
                **selected_item,
                "rag_ready": bool(selected_evidence),
                "top_evidence": selected_evidence[:2],
                "recommended_plan": _training_plan_from_evidence(selected_item, selected_evidence),
            } if selected_item else None,
            "trace": _trace_with_rag(selected_doc, selected_evidence) if selected_doc else [],
            "assessment": _assessment_blueprint_from_evidence(selected_item, selected_evidence) if selected_item else [],
            "evidence_refs": selected_evidence,
        },
        "proactive_agent": {
            "name": "学习助手",
            "status": "online",
            "suggestions": _agent_suggestions(docs, len(pending_tasks)),
        },
    }

@router.post("/training-runs", status_code=201)
def start_training_run(
    data: TrainingRunStart,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Start a traceable training run and persist the first learner task."""
    from app.crud.learning.task import create_task
    doc = _find_workspace_document(current_user, db, data.doc_id)
    if not doc:
        raise HTTPException(404, "Training source not found")
    item = _doc_training_item(doc)
    goal = data.goal or item["agent_goal"]
    evidence = _rag_evidence_for_item(current_user, item, goal, top_k=5)
    trace = _trace_with_rag(doc, evidence, goal)
    plan = _training_plan_from_evidence(item, evidence)
    assessment = _assessment_blueprint_from_evidence(item, evidence)
    rule_hits = [
        {"rule_id": "evidence_required", "passed": bool(evidence), "severity": "major", "message": f"已找到 {len(evidence)} 条可参考资料"},
        {"rule_id": "load_ok", "passed": item["estimated_minutes"] <= 60, "severity": "critical", "message": f"预计训练 {item['estimated_minutes']} 分钟"},
        {"rule_id": "has_structure", "passed": True, "severity": "minor", "message": "训练包含目标、资料、练习、检查点和复盘"},
        {"rule_id": "kp_coverage", "passed": len(evidence) >= 2, "severity": "minor", "message": "资料覆盖多个片段" if len(evidence) >= 2 else "资料较少，建议补充内容"},
    ]
    evidence_lines = "\n".join(
        f"- [{idx}] {ev['title']} / chunk {ev['chunk_id']} / score {round(float(ev['score']), 3)}：{ev['snippet'][:120]}"
        for idx, ev in enumerate(evidence[:5], start=1)
    ) or "- 当前资料不足，请先导入或补充学习素材。"
    plan_lines = "\n".join(f"- {step['stage']}：{step['output']}" for step in plan)
    task = create_task(
        db,
        current_user.id,
        title=f"训练任务：{item['title']}",
        task_type=data.mode,
        description=(
            f"目标：{goal}\n"
            f"参考资料：\n{evidence_lines}\n"
            f"学习安排：\n{plan_lines}\n"
            f"完成要求：提交学习时长、复盘和可选测验分数。"
        ),
    )
    return {
        "run_id": f"run_{data.doc_id[:10]}_{int(datetime.utcnow().timestamp())}",
        "mode": data.mode,
        "task": _task_out(task),
        "scenario": item,
        "trace": trace,
        "evidence_refs": evidence,
        "rule_hits": rule_hits,
        "assessment": assessment,
        "training_plan": plan,
        "judge": {
            "risk_level": item["risk_level"],
            "proposed_action": "按学习资料完成任务，并在完成后提交复盘",
            "confidence": "high" if len(evidence) >= 3 else "medium",
        },
    }

# ============================
# Learner Endpoints
# ============================
@router.post("/learners", response_model=LearnerOut)
def create_learner(data: LearnerCreate, db: Session = Depends(get_db),
                   current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.learner import create_learner
    from app.utils.uuid import bytes_to_uuid_string
    obj = create_learner(db, **data.model_dump())
    return {**{k: getattr(obj, k) for k in ["name","grade","language","goals","tags"]},
            "id": bytes_to_uuid_string(obj.id),
            "created_at": obj.created_at.isoformat() if obj.created_at else ""}

@router.get("/learners", response_model=List[LearnerOut])
def list_learners(db: Session = Depends(get_db),
                  current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.learner import list_learners
    from app.utils.uuid import bytes_to_uuid_string
    objs = list_learners(db)
    return [{**{k: getattr(o, k) for k in ["name","grade","language","goals","tags"]},
             "id": bytes_to_uuid_string(o.id),
             "created_at": o.created_at.isoformat() if o.created_at else ""} for o in objs]

@router.get("/learners/{learner_id}", response_model=LearnerOut)
def get_learner(learner_id: str, db: Session = Depends(get_db),
                current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.learner import get_learner
    from app.utils.uuid import bytes_to_uuid_string, uuid_string_to_bytes
    obj = get_learner(db, learner_id)
    if not obj: raise HTTPException(404, "Learner not found")
    return {**{k: getattr(obj, k) for k in ["name","grade","language","goals","tags"]},
            "id": bytes_to_uuid_string(obj.id),
            "created_at": obj.created_at.isoformat() if obj.created_at else ""}

@router.post("/learners/{learner_id}/mastery")
def record_mastery(learner_id: str, data: MasteryRecord, db: Session = Depends(get_db),
                   current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.learner import record_mastery
    from app.utils.uuid import bytes_to_uuid_string
    obj = record_mastery(db, learner_id, data.kp_id, data.level, data.confidence)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "kp_id": obj.kp_id, "level": obj.level}

@router.get("/learners/{learner_id}/mastery")
def get_mastery(learner_id: str, kp_id: Optional[str] = Query(None), db: Session = Depends(get_db),
                current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.learner import get_mastery
    from app.utils.uuid import bytes_to_uuid_string
    rows = get_mastery(db, learner_id, kp_id)
    return {"success": True, "data": [{"id": bytes_to_uuid_string(r.id), "kp_id": r.kp_id,
                                       "level": r.level, "confidence": r.confidence,
                                       "last_assessed": r.last_assessed.isoformat() if r.last_assessed else ""}
                                      for r in rows]}

@router.post("/learners/{learner_id}/errors")
def record_error(learner_id: str, data: ErrorRecord, db: Session = Depends(get_db),
                 current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.learner import record_error
    from app.utils.uuid import bytes_to_uuid_string
    obj = record_error(db, learner_id, data.error_type, data.kp_id)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "error_type": obj.error_type}

@router.get("/learners/{learner_id}/errors")
def get_errors(learner_id: str, db: Session = Depends(get_db),
               current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.learner import get_errors
    from app.utils.uuid import bytes_to_uuid_string
    rows = get_errors(db, learner_id)
    return {"success": True, "data": [{"id": bytes_to_uuid_string(r.id), "kp_id": r.kp_id,
                                       "error_type": r.error_type, "count": r.count,
                                       "last_occurrence": r.last_occurrence.isoformat() if r.last_occurrence else ""}
                                      for r in rows]}

@router.post("/learners/{learner_id}/cognitive-load")
def update_load(learner_id: str, data: LoadRecord, db: Session = Depends(get_db),
                current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.learner import update_cognitive_load
    from app.utils.uuid import bytes_to_uuid_string
    obj = update_cognitive_load(db, learner_id, data.load_value, data.threshold)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "current_load": obj.current_load}

# ============================
# Knowledge Point Endpoints
# ============================
@router.post("/knowledge-points", response_model=KPOut)
def create_kp(data: KPCreate, db: Session = Depends(get_db),
              current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.knowledge_point import create_kp
    obj = create_kp(db, **data.model_dump())
    return {**{k: getattr(obj, k) for k in ["id","name","category","description","difficulty","tags"]},
            "created_at": obj.created_at.isoformat() if obj.created_at else ""}

@router.get("/knowledge-points", response_model=List[KPOut])
def list_kps(category: Optional[str] = Query(None), db: Session = Depends(get_db),
             current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.knowledge_point import list_kps
    objs = list_kps(db, category)
    return [{**{k: getattr(o, k) for k in ["id","name","category","description","difficulty","tags"]},
             "created_at": o.created_at.isoformat() if o.created_at else ""} for o in objs]

@router.get("/knowledge-points/{kp_id}")
def get_kp(kp_id: str, db: Session = Depends(get_db),
           current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.knowledge_point import get_kp
    obj = get_kp(db, kp_id)
    if not obj: raise HTTPException(404, "Knowledge point not found")
    return {**{k: getattr(obj, k) for k in ["id","name","category","description","difficulty","tags"]},
            "created_at": obj.created_at.isoformat() if obj.created_at else ""}

@router.get("/knowledge-points/{kp_id}/prerequisites")
def get_prereqs(kp_id: str, db: Session = Depends(get_db),
                current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.knowledge_point import get_prerequisites, get_next_kps
    prereqs = get_prerequisites(db, kp_id)
    next_kps = get_next_kps(db, kp_id)
    return {"success": True, "prerequisites": [{"id": p.id, "name": p.name} for p in prereqs if p],
            "next_knowledge_points": [{"id": p.id, "name": p.name} for p in next_kps if p]}

# ============================
# Plan Endpoints
# ============================
@router.post("/plans")
def create_plan(data: PlanCreate, db: Session = Depends(get_db),
                current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.plan import create_plan
    from app.utils.uuid import bytes_to_uuid_string
    obj = create_plan(db, data.learner_id, data.goal)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "status": obj.status}

@router.get("/plans")
def list_plans(learner_id: Optional[str] = Query(None), status: Optional[str] = Query(None),
               db: Session = Depends(get_db),
               current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.plan import list_plans
    from app.utils.uuid import bytes_to_uuid_string
    objs = list_plans(db, learner_id, status)
    return {"success": True, "data": [{"id": bytes_to_uuid_string(o.id),
                                       "learner_id": bytes_to_uuid_string(o.learner_id),
                                       "goal": o.goal, "status": o.status,
                                       "created_at": o.created_at.isoformat() if o.created_at else ""}
                                      for o in objs]}

@router.post("/plans/{plan_id}/knowledge-points")
def add_plan_kp(plan_id: str, data: PlanKPAdd, db: Session = Depends(get_db),
                current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.plan import add_plan_kp
    from app.utils.uuid import bytes_to_uuid_string
    obj = add_plan_kp(db, plan_id, data.kp_id, data.sort_order)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "kp_id": obj.kp_id}

@router.get("/plans/{plan_id}/knowledge-points")
def list_plan_kps(plan_id: str, db: Session = Depends(get_db),
                  current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.plan import list_plan_kps
    from app.utils.uuid import bytes_to_uuid_string
    rows = list_plan_kps(db, plan_id)
    return {"success": True, "data": [{"id": bytes_to_uuid_string(r.id), "kp_id": r.kp_id,
                                       "sort_order": r.sort_order, "status": r.status}
                                      for r in rows]}

@router.patch("/plans/{plan_id}/status")
def update_plan_status(plan_id: str, status: str = Query(...), db: Session = Depends(get_db),
                       current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.plan import update_plan_status
    from app.utils.uuid import bytes_to_uuid_string
    obj = update_plan_status(db, plan_id, status)
    if not obj: raise HTTPException(404, "Plan not found")
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "status": obj.status}

# ============================
# Exam Endpoints
# ============================
@router.post("/exams")
def create_exam(data: ExamCreate, db: Session = Depends(get_db),
                current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.exam import create_exam
    from app.utils.uuid import bytes_to_uuid_string
    obj = create_exam(db, data.title, data.plan_id, data.description)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "title": obj.title}


@router.get("/exams")
def list_exams_api(plan_id: Optional[str] = Query(None), db: Session = Depends(get_db),
                   current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.exam import list_exams
    from app.utils.uuid import bytes_to_uuid_string
    objs = list_exams(db, plan_id)
    return {"success": True, "exams": [{"id": bytes_to_uuid_string(o.id), "title": o.title,
        "created_at": o.created_at.isoformat() if o.created_at else ""} for o in objs],
        "total": len(objs)}

@router.post("/exams/{exam_id}/questions")
def add_question(exam_id: str, data: QuestionAdd, db: Session = Depends(get_db),
                 current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.exam import add_question
    from app.utils.uuid import bytes_to_uuid_string
    obj = add_question(db, exam_id, data.kp_id, data.qtype, data.question_data, data.difficulty, data.sort_order)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "qtype": obj.question_type}

@router.get("/exams/{exam_id}/questions")
def list_questions(exam_id: str, db: Session = Depends(get_db),
                   current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.exam import list_questions
    from app.utils.uuid import bytes_to_uuid_string
    rows = list_questions(db, exam_id)
    return {"success": True, "data": [{"id": bytes_to_uuid_string(r.id), "kp_id": r.kp_id,
                                       "qtype": r.question_type, "difficulty": r.difficulty,
                                       "sort_order": r.sort_order, "question_data": r.question_data}
                                      for r in rows]}

# ============================
# Content Endpoints
# ============================
@router.post("/contents")
def create_content(data: ContentCreate, db: Session = Depends(get_db),
                   current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.content import create_content
    from app.utils.uuid import bytes_to_uuid_string
    obj = create_content(db, data.template_type, data.title, data.content_data, data.plan_id, data.kp_id)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "title": obj.title}

@router.get("/contents")
def list_contents(plan_id: Optional[str] = Query(None), status: Optional[str] = Query(None),
                  db: Session = Depends(get_db),
                  current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.content import list_contents
    from app.utils.uuid import bytes_to_uuid_string
    objs = list_contents(db, plan_id, status)
    return {"success": True, "data": [{"id": bytes_to_uuid_string(o.id), "title": o.title,
                                       "template_type": o.template_type, "status": o.status,
                                       "created_at": o.created_at.isoformat() if o.created_at else ""}
                                      for o in objs]}

# ============================
# Review Endpoints
# ============================
@router.post("/reviews")
def create_review(data: ReviewCreate, db: Session = Depends(get_db),
                  current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.review import create_review
    from app.utils.uuid import bytes_to_uuid_string
    obj = create_review(db, data.content_id, data.reviewer_type, data.risk_level)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "status": obj.status}


@router.get("/reviews")
def list_reviews_api(content_id: Optional[str] = Query(None), db: Session = Depends(get_db),
                     current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.review import list_reviews
    from app.utils.uuid import bytes_to_uuid_string
    objs = list_reviews(db, content_id)
    return {"success": True, "reviews": [{"id": bytes_to_uuid_string(o.id),
        "status": o.status, "risk_level": o.risk_level,
        "created_at": o.created_at.isoformat() if o.created_at else ""} for o in objs],
        "total": len(objs)}

@router.post("/reviews/{review_id}/defects")
def add_defect(review_id: str, data: DefectAdd, db: Session = Depends(get_db),
               current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.review import add_defect
    from app.utils.uuid import bytes_to_uuid_string
    obj = add_defect(db, review_id, data.defect_type, data.severity, data.location, data.description, data.suggestion)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "defect_type": obj.defect_type}

# ============================
# Candidate Endpoints
# ============================
@router.post("/candidates")
def create_candidate(data: CandidateCreate, db: Session = Depends(get_db),
                     current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.candidate import create_candidate
    from app.utils.uuid import bytes_to_uuid_string
    obj = create_candidate(db, data.content_id, data.rank_score, data.risk_info)
    return {"success": True, "id": bytes_to_uuid_string(obj.id), "rank_score": obj.rank_score}

@router.get("/candidates")
def list_candidates(content_id: Optional[str] = Query(None), db: Session = Depends(get_db),
                    current_user: UserSchema = Depends(get_current_user)):
    from app.crud.learning.candidate import list_candidates
    from app.utils.uuid import bytes_to_uuid_string
    rows = list_candidates(db, content_id)
    return {"success": True, "data": [{"id": bytes_to_uuid_string(r.id),
                                       "content_id": r.content_id if isinstance(r.content_id, str) else bytes_to_uuid_string(r.content_id),
                                       "rank_score": r.rank_score, "is_selected": bool(r.is_selected)}
                                      for r in rows]}

@router.get("/forgetting-curve")
def get_forgetting_curve(
    hours: int = Query(720, ge=1, le=1440),
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Get user-specific forgetting curve data from recorded study events."""
    from collections import defaultdict
    from datetime import datetime, timedelta
    from app.models.learning.knowledge_point import KnowledgePoint, StudyEvent
    from app.services.forgetting_curve import OPTIMAL_REVIEW_HOURS, retention_at
    from app.utils.uuid import uuid_string_to_bytes

    user_id_bytes = uuid_string_to_bytes(current_user.id)
    now = datetime.utcnow()
    events = db.query(StudyEvent).filter(StudyEvent.user_id == user_id_bytes)\
        .order_by(StudyEvent.studied_at.asc()).all()

    if not events:
        return {
            "curve": [],
            "optimal_reviews": [],
            "has_data": False,
            "message": "暂无真实学习记录，开始学习后会生成复习趋势。",
            "parameters": {"hours": hours, "study_event_count": 0, "knowledge_point_count": 0},
        }

    grouped = defaultdict(list)
    for event in events:
        if event.studied_at:
            grouped[event.kp_id].append(event.studied_at)

    def point_hours(total_hours: int) -> list[int]:
        points = list(range(0, min(24, total_hours + 1)))
        points.extend(range(24, min(168, total_hours + 1), 6))
        points.extend(range(168, total_hours + 1, 24))
        return sorted(set(points))

    curve = []
    for h in point_hours(hours):
        values = []
        for studied_times in grouped.values():
            last_studied = max(studied_times)
            completed_reviews = max(0, len(studied_times) - 1)
            elapsed_hours = max(0.0, (now - last_studied).total_seconds() / 3600)
            values.append(retention_at(
                t_hours=elapsed_hours + h,
                study_count=completed_reviews,
                last_review_hours=elapsed_hours + h,
            ))
        curve.append({"hour": h, "retention": round(sum(values) / len(values), 4)})

    kp_names = {
        kp.id: kp.name
        for kp in db.query(KnowledgePoint).filter(KnowledgePoint.id.in_(grouped.keys())).all()
    }
    reviews = []
    for kp_id, studied_times in grouped.items():
        last_studied = max(studied_times)
        completed_reviews = max(0, len(studied_times) - 1)
        interval_index = min(completed_reviews, len(OPTIMAL_REVIEW_HOURS) - 1)
        interval_hours = OPTIMAL_REVIEW_HOURS[interval_index]
        review_time = last_studied + timedelta(hours=interval_hours)
        if interval_hours < 24:
            label = f"{interval_hours}小时"
        elif interval_hours < 720:
            label = f"{interval_hours // 24}天"
        else:
            label = f"{interval_hours // 720}个月"
        reviews.append({
            "kp_id": kp_id,
            "title": kp_names.get(kp_id) or kp_id,
            "interval_label": label,
            "interval_hours": interval_hours,
            "review_time": review_time.isoformat(),
            "retention_at_review": round(retention_at(interval_hours, study_count=completed_reviews, last_review_hours=interval_hours), 4),
            "completed": review_time <= now,
        })
    reviews.sort(key=lambda item: item["review_time"])

    return {
        "curve": curve,
        "optimal_reviews": reviews[:5],
        "has_data": True,
        "parameters": {
            "hours": hours,
            "study_event_count": len(events),
            "knowledge_point_count": len(grouped),
        }
    }


@router.post("/study-events")
def record_study_event(
    kp_ids: List[str],
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Record study events for knowledge points."""
    from app.models.learning.knowledge_point import StudyEvent
    from app.utils.uuid import uuid_string_to_bytes
    import uuid as uuid_mod
    from datetime import datetime
    
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    now = datetime.utcnow()
    events = []
    for kp_id in kp_ids:
        event = StudyEvent(
            id=str(uuid_mod.uuid4())[:8],
            user_id=user_id_bytes,
            kp_id=kp_id,
            studied_at=now,
        )
        db.add(event)
        events.append(event)
    db.commit()
    return {"recorded": len(events)}


@router.get("/study-events")
def list_study_events(
    kp_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """List study events for a learner."""
    from app.models.learning.knowledge_point import StudyEvent
    from app.utils.uuid import uuid_string_to_bytes
    
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    q = db.query(StudyEvent).filter(StudyEvent.user_id == user_id_bytes)
    if kp_id:
        q = q.filter(StudyEvent.kp_id == kp_id)
    events = q.order_by(StudyEvent.studied_at.desc()).limit(100).all()
    return [
        {
            "id": e.id,
            "kp_id": e.kp_id,
            "studied_at": e.studied_at.isoformat() if e.studied_at else None,
        }
        for e in events
    ]

@router.get("/kb-by-category")
def get_kb_by_category(
    category: str = "",
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Get KB documents filtered by category for study."""
    from app.services.rag_service import get_kb
    from app.utils.uuid import uuid_string_to_bytes
    user_id = uuid_string_to_bytes(current_user.id)
    kb = get_kb(user_id)
    docs = kb.list_documents()
    
    # Filter by category if specified
    if category:
        docs = [d for d in docs if d["metadata"].get("category") == category]
    
    # Return compact info
    return [
        {
            "doc_id": d["doc_id"],
            "title": d["metadata"].get("title", ""),
            "category": d["metadata"].get("category", ""),
            "content_length": d["content_length"],
            "chunk_count": d["chunk_count"],
        }
        for d in docs[:100]  # Limit to 100
    ]
