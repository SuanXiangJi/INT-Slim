import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.learning.candidate import CandidateRanking

def _b16(s=""):
    if isinstance(s, bytes): return s
    return uuid.UUID(s).bytes if s else uuid.uuid4().bytes

def create_candidate(db: Session, content_id: str, rank_score: float = 0.0,
                     risk_info: dict = None) -> CandidateRanking:
    obj = CandidateRanking(id=_b16(), content_id=content_id,
                          rank_score=rank_score, risk_info=risk_info or {})
    db.add(obj); db.commit(); db.refresh(obj); return obj

def list_candidates(db: Session, content_id: str = None) -> list:
    q = db.query(CandidateRanking)
    if content_id: q = q.filter(CandidateRanking.content_id == content_id)
    return q.order_by(CandidateRanking.rank_score.desc()).all()

def select_candidate(db: Session, candidate_id: str) -> Optional[CandidateRanking]:
    obj = db.query(CandidateRanking).filter(CandidateRanking.id == _b16(candidate_id)).first()
    if not obj: return None
    obj.is_selected = 1; db.commit(); db.refresh(obj); return obj
