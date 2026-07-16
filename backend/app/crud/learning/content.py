import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.learning.content import ContentAssembly

def _b16(s=""):
    if isinstance(s, bytes): return s
    return uuid.UUID(s).bytes if s else uuid.uuid4().bytes

def create_content(db: Session, template_type: str, title: str, content_data: dict,
                   plan_id: str = None, kp_id: str = None) -> ContentAssembly:
    obj = ContentAssembly(id=_b16(), plan_id=_b16(plan_id) if plan_id else None,
                          kp_id=kp_id, template_type=template_type, title=title,
                          content_data=content_data)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def get_content(db: Session, content_id: str) -> Optional[ContentAssembly]:
    return db.query(ContentAssembly).filter(ContentAssembly.id == _b16(content_id)).first()

def list_contents(db: Session, plan_id: str = None, status: str = None) -> list:
    q = db.query(ContentAssembly)
    if plan_id: q = q.filter(ContentAssembly.plan_id == _b16(plan_id))
    if status: q = q.filter(ContentAssembly.status == status)
    return q.order_by(ContentAssembly.created_at.desc()).all()

def update_content_status(db: Session, content_id: str, status: str) -> Optional[ContentAssembly]:
    obj = get_content(db, content_id)
    if not obj: return None
    obj.status = status; db.commit(); db.refresh(obj); return obj
