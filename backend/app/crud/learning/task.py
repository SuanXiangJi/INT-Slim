# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.learning.task import LearningTask
from app.utils.uuid import generate_uuid, uuid_string_to_bytes


def create_task(db: Session, user_id: str, title: str, description: str | None = None,
                task_type: str = "study", kp_id: str | None = None, due_date=None) -> LearningTask:
    task = LearningTask(
        id=generate_uuid(), user_id=uuid_string_to_bytes(user_id), title=title,
        description=description, task_type=task_type, kp_id=kp_id, due_date=due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, user_id: str, status: str | None = None) -> list[LearningTask]:
    query = db.query(LearningTask).filter(LearningTask.user_id == uuid_string_to_bytes(user_id))
    if status:
        query = query.filter(LearningTask.status == status)
    return query.order_by(LearningTask.status.asc(), LearningTask.due_date.asc(), LearningTask.created_at.desc()).all()


def get_task(db: Session, user_id: str, task_id: str) -> LearningTask | None:
    return db.query(LearningTask).filter(
        LearningTask.id == uuid_string_to_bytes(task_id),
        LearningTask.user_id == uuid_string_to_bytes(user_id),
    ).first()


def set_task_status(db: Session, task: LearningTask, status: str) -> LearningTask:
    task.status = status
    task.completed_at = datetime.utcnow() if status == "done" else None
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: LearningTask) -> None:
    db.delete(task)
    db.commit()
