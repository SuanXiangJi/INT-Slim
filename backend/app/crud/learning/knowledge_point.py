import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.learning.knowledge_point import KnowledgePoint, KpPrerequisite

def create_kp(db: Session, name: str, category: str = None, description: str = None,
              difficulty: float = 0.5, tags: list = None) -> KnowledgePoint:
    kid = str(uuid.uuid4())[:8]
    obj = KnowledgePoint(id=kid, name=name, category=category, description=description,
                         difficulty=difficulty, tags=tags or [])
    db.add(obj); db.commit(); db.refresh(obj); return obj

def get_kp(db: Session, kp_id: str) -> Optional[KnowledgePoint]:
    return db.query(KnowledgePoint).filter(KnowledgePoint.id == kp_id).first()

def list_kps(db: Session, category: str = None, skip: int = 0, limit: int = 100) -> List[KnowledgePoint]:
    q = db.query(KnowledgePoint)
    if category: q = q.filter(KnowledgePoint.category == category)
    return q.offset(skip).limit(limit).all()

def search_kps(db: Session, query: str, limit: int = 10) -> list:
    return db.query(KnowledgePoint).filter(
        KnowledgePoint.name.like(f"%{query}%") | KnowledgePoint.description.like(f"%{query}%")
    ).limit(limit).all()

def add_prerequisite(db: Session, kp_id: str, prereq_kp_id: str) -> KpPrerequisite:
    obj = KpPrerequisite(kp_id=kp_id, prerequisite_kp_id=prereq_kp_id)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def get_prerequisites(db: Session, kp_id: str) -> list:
    rows = db.query(KpPrerequisite).filter(KpPrerequisite.kp_id == kp_id).all()
    return [db.query(KnowledgePoint).filter(KnowledgePoint.id == r.prerequisite_kp_id).first() for r in rows]

def get_next_kps(db: Session, kp_id: str) -> list:
    rows = db.query(KpPrerequisite).filter(KpPrerequisite.prerequisite_kp_id == kp_id).all()
    return [db.query(KnowledgePoint).filter(KnowledgePoint.id == r.kp_id).first() for r in rows]

def find_learning_path(db: Session, target_kp_id: str) -> list:
    """BFS to find prerequisite chain."""
    from collections import deque
    kp = get_kp(db, target_kp_id)
    if not kp: return []
    visited = set(); path = []
    q = deque([(target_kp_id, [target_kp_id])])
    while q:
        current, p = q.popleft()
        if current in visited: continue
        visited.add(current)
        prereqs = db.query(KpPrerequisite).filter(KpPrerequisite.kp_id == current).all()
        if not prereqs:
            path = p; break
        for pr in prereqs:
            if pr.prerequisite_kp_id not in visited:
                q.append((pr.prerequisite_kp_id, [pr.prerequisite_kp_id] + p))
    return [db.query(KnowledgePoint).filter(KnowledgePoint.id == pid).first() for pid in path if pid]

def update_kp(db: Session, kp_id: str, **kwargs) -> Optional[KnowledgePoint]:
    obj = get_kp(db, kp_id)
    if not obj: return None
    for k, v in kwargs.items():
        if v is not None and hasattr(obj, k): setattr(obj, k, v)
    db.commit(); db.refresh(obj); return obj
