import uuid, datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.learning.learner import Learner, LearnerMastery, LearnerError, LearnerCognitiveLoad

def _b16(s=""):
    if isinstance(s, bytes): return s
    return uuid.UUID(s).bytes if s else uuid.uuid4().bytes

def create_learner(db: Session, name: str, grade: str = None, language: str = "zh-CN",
                   goals: list = None, tags: list = None) -> Learner:
    obj = Learner(id=_b16(), name=name, grade=grade, language=language,
                  goals=goals or [], tags=tags or [])
    db.add(obj); db.commit(); db.refresh(obj); return obj

def get_learner(db: Session, learner_id: str) -> Optional[Learner]:
    return db.query(Learner).filter(Learner.id == _b16(learner_id)).first()

def get_learner_by_name(db: Session, name: str) -> Optional[Learner]:
    return db.query(Learner).filter(Learner.name == name).first()

def list_learners(db: Session, skip: int = 0, limit: int = 100) -> List[Learner]:
    return db.query(Learner).offset(skip).limit(limit).all()

def update_learner(db: Session, learner_id: str, **kwargs) -> Optional[Learner]:
    obj = get_learner(db, learner_id)
    if not obj: return None
    for k, v in kwargs.items():
        if v is not None and hasattr(obj, k): setattr(obj, k, v)
    db.commit(); db.refresh(obj); return obj

def record_mastery(db: Session, learner_id: str, kp_id: str, level: float = 0.0,
                   confidence: float = 0.5) -> LearnerMastery:
    lid = _b16(learner_id)
    existing = db.query(LearnerMastery).filter(
        LearnerMastery.learner_id == lid,
        LearnerMastery.kp_id == kp_id
    ).first()
    now = datetime.datetime.now()
    if existing:
        existing.level = level
        existing.confidence = confidence
        existing.last_assessed = now
        obj = existing
    else:
        obj = LearnerMastery(id=_b16(), learner_id=lid, kp_id=kp_id,
                             level=level, confidence=confidence, last_assessed=now)
        db.add(obj)
    db.commit(); db.refresh(obj); return obj

def get_mastery(db: Session, learner_id: str, kp_id: str = None) -> list:
    q = db.query(LearnerMastery).filter(LearnerMastery.learner_id == _b16(learner_id))
    if kp_id: q = q.filter(LearnerMastery.kp_id == kp_id)
    return q.all()

def record_error(db: Session, learner_id: str, error_type: str, kp_id: str = None) -> LearnerError:
    lid = _b16(learner_id)
    now = datetime.datetime.now()
    # merge similar recent errors
    recent = db.query(LearnerError).filter(
        LearnerError.learner_id == lid,
        LearnerError.error_type == error_type,
        LearnerError.kp_id == kp_id,
        LearnerError.last_occurrence >= now - datetime.timedelta(hours=1)
    ).first()
    if recent:
        recent.count = (recent.count or 0) + 1
        recent.last_occurrence = now
        obj = recent
    else:
        obj = LearnerError(id=_b16(), learner_id=lid, kp_id=kp_id,
                          error_type=error_type, count=1, last_occurrence=now)
        db.add(obj)
    db.commit(); db.refresh(obj); return obj

def get_errors(db: Session, learner_id: str, limit: int = 50) -> list:
    return db.query(LearnerError).filter(
        LearnerError.learner_id == _b16(learner_id)
    ).order_by(LearnerError.last_occurrence.desc()).limit(limit).all()

def update_cognitive_load(db: Session, learner_id: str, load_value: float, threshold: float = 0.8) -> LearnerCognitiveLoad:
    lid = _b16(learner_id)
    existing = db.query(LearnerCognitiveLoad).filter(LearnerCognitiveLoad.learner_id == lid).first()
    if existing:
        existing.current_load = load_value
        existing.threshold = threshold
        obj = existing
    else:
        obj = LearnerCognitiveLoad(id=_b16(), learner_id=lid, current_load=load_value, threshold=threshold)
        db.add(obj)
    db.commit(); db.refresh(obj); return obj

def get_cognitive_load(db: Session, learner_id: str) -> Optional[LearnerCognitiveLoad]:
    return db.query(LearnerCognitiveLoad).filter(LearnerCognitiveLoad.learner_id == _b16(learner_id)).first()
