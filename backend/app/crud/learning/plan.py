import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.learning.plan import LearningPlan, PlanKnowledgePoint

def _b16(s=""):
    if isinstance(s, bytes): return s
    return uuid.UUID(s).bytes if s else uuid.uuid4().bytes

def create_plan(db: Session, learner_id: str, goal: str = None) -> LearningPlan:
    obj = LearningPlan(id=_b16(), learner_id=_b16(learner_id), goal=goal)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def get_plan(db: Session, plan_id: str) -> Optional[LearningPlan]:
    return db.query(LearningPlan).filter(LearningPlan.id == _b16(plan_id)).first()

def list_plans(db: Session, learner_id: str = None, status: str = None) -> list:
    q = db.query(LearningPlan)
    if learner_id: q = q.filter(LearningPlan.learner_id == _b16(learner_id))
    if status: q = q.filter(LearningPlan.status == status)
    return q.order_by(LearningPlan.created_at.desc()).all()

def update_plan_status(db: Session, plan_id: str, status: str) -> Optional[LearningPlan]:
    obj = get_plan(db, plan_id)
    if not obj: return None
    obj.status = status; db.commit(); db.refresh(obj); return obj

def add_plan_kp(db: Session, plan_id: str, kp_id: str, sort_order: int = 0) -> PlanKnowledgePoint:
    obj = PlanKnowledgePoint(id=_b16(), plan_id=_b16(plan_id), kp_id=kp_id, sort_order=sort_order)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def list_plan_kps(db: Session, plan_id: str) -> list:
    return db.query(PlanKnowledgePoint).filter(
        PlanKnowledgePoint.plan_id == _b16(plan_id)
    ).order_by(PlanKnowledgePoint.sort_order).all()

def update_plan_kp_status(db: Session, pkp_id: str, status: str) -> Optional[PlanKnowledgePoint]:
    obj = db.query(PlanKnowledgePoint).filter(PlanKnowledgePoint.id == _b16(pkp_id)).first()
    if not obj: return None
    obj.status = status; db.commit(); db.refresh(obj); return obj
