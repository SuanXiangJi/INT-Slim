from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.conversation import Conversation
from app.models.user import User
from app.utils.uuid import generate_uuid


def get_conversation_by_id(db: Session, conversation_id: bytes) -> Conversation:
    """Get a conversation by its ID"""
    return db.query(Conversation).filter(Conversation.id == conversation_id).first()


def get_conversations_by_user_id(db: Session, user_id: bytes) -> list[Conversation]:
    """Get all conversations for a user, excluding deleted ones"""
    return db.query(Conversation).filter(
        and_(Conversation.user_id == user_id, Conversation.is_deleted == 0)
    ).order_by(Conversation.updated_at.desc()).all()


def create_conversation(db: Session, user_id: bytes, title: str = None) -> Conversation:
    """Create a new conversation. Title defaults to timestamp if not provided."""
    if title is None:
        title = datetime.now().strftime("%m-%d %H:%M")
    conversation = Conversation(
        id=generate_uuid(),
        user_id=user_id,
        title=title
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def update_conversation_title(db: Session, conversation_id: bytes, title: str) -> Conversation:
    """Update a conversation's title"""
    conversation = get_conversation_by_id(db, conversation_id)
    if conversation:
        conversation.title = title
        db.commit()
        db.refresh(conversation)
    return conversation


def delete_conversation(db: Session, conversation_id: bytes) -> bool:
    """Soft delete a conversation"""
    conversation = get_conversation_by_id(db, conversation_id)
    if conversation:
        conversation.is_deleted = 1
        db.commit()
        db.refresh(conversation)
        return True
    return False


def hard_delete_conversation(db: Session, conversation_id: bytes) -> bool:
    """Hard delete a conversation"""
    conversation = get_conversation_by_id(db, conversation_id)
    if conversation:
        db.delete(conversation)
        db.commit()
        return True
    return False