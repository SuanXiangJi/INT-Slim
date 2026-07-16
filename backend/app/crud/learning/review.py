import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.learning.review import QualityReview, ReviewDefect

def _b16(s=""):
    if isinstance(s, bytes): return s
    return uuid.UUID(s).bytes if s else uuid.uuid4().bytes

def create_review(db: Session, content_id: str, reviewer_type: str = "auto",
                  risk_level: str = "medium") -> QualityReview:
    obj = QualityReview(id=_b16(), content_id=content_id,
                        reviewer_type=reviewer_type, risk_level=risk_level)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def get_review(db: Session, review_id: str) -> Optional[QualityReview]:
    return db.query(QualityReview).filter(QualityReview.id == _b16(review_id)).first()

def list_reviews(db: Session, content_id: str = None) -> list:
    q = db.query(QualityReview)
    if content_id: q = q.filter(QualityReview.content_id == content_id)
    return q.order_by(QualityReview.created_at.desc()).all()

def update_review_status(db: Session, review_id: str, status: str, summary: str = None) -> Optional[QualityReview]:
    obj = get_review(db, review_id)
    if not obj: return None
    obj.status = status
    if summary: obj.review_summary = summary
    db.commit(); db.refresh(obj); return obj

def add_defect(db: Session, review_id: str, defect_type: str, severity: str = "minor",
               location: str = None, description: str = None, suggestion: str = None) -> ReviewDefect:
    obj = ReviewDefect(id=_b16(), review_id=review_id, defect_type=defect_type,
                       severity=severity, location=location, description=description, suggestion=suggestion)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def list_defects(db: Session, review_id: str) -> list:
    return db.query(ReviewDefect).filter(ReviewDefect.review_id == review_id).all()
