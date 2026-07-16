from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.learning.course import Course

def create_course(db: Session, course_id: str, name: str, summary: str = None,
                  page_count: int = 0, category: str = None, tags: list = None,
                  source: str = None) -> Course:
    obj = Course(id=course_id, name=name, summary=summary, page_count=page_count,
                 category=category, tags=tags or [], source=source)
    db.add(obj); db.commit(); db.refresh(obj); return obj

def get_course(db: Session, course_id: str) -> Optional[Course]:
    return db.query(Course).filter(Course.id == course_id).first()

def list_courses(db: Session, category: str = None) -> list:
    q = db.query(Course)
    if category: q = q.filter(Course.category == category)
    return q.order_by(Course.name).all()

def search_courses(db: Session, query: str, limit: int = 10) -> list:
    return db.query(Course).filter(Course.name.like(f"%{query}%")).limit(limit).all()
