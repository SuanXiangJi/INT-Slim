import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.learning.exam import Exam, ExamQuestion

def _b16(s=""):
    if isinstance(s, bytes): return s
    return uuid.UUID(s).bytes if s else uuid.uuid4().bytes

def create_exam(db: Session, title: str, plan_id: str = None, description: str = None) -> Exam:
    obj = Exam(id=_b16(), plan_id=_b16(plan_id) if plan_id else None, title=title, description=description)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def get_exam(db: Session, exam_id: str) -> Optional[Exam]:
    return db.query(Exam).filter(Exam.id == _b16(exam_id)).first()

def list_exams(db: Session, plan_id: str = None) -> list:
    q = db.query(Exam)
    if plan_id: q = q.filter(Exam.plan_id == _b16(plan_id))
    return q.order_by(Exam.created_at.desc()).all()

def add_question(db: Session, exam_id: str, kp_id: str, qtype: str,
                 question_data: dict, difficulty: float = 0.5, sort_order: int = 0) -> ExamQuestion:
    obj = ExamQuestion(id=_b16(), exam_id=_b16(exam_id), kp_id=kp_id, question_type=qtype,
                       question_data=question_data, difficulty=difficulty, sort_order=sort_order)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def list_questions(db: Session, exam_id: str) -> list:
    return db.query(ExamQuestion).filter(ExamQuestion.exam_id == _b16(exam_id)).order_by(ExamQuestion.sort_order).all()
