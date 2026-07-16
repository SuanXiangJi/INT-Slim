from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.message import Message
from app.models.conversation import Conversation
from app.utils.uuid import generate_uuid


def get_message_by_id(db: Session, message_id: bytes) -> Message:
    """Get a message by its ID"""
    return db.query(Message).filter(Message.id == message_id).first()


def get_messages_by_conversation_id(db: Session, conversation_id: bytes) -> list[Message]:
    """Get all messages for a conversation, ordered by creation time"""
    return db.query(Message).filter(Message.conversation_id == conversation_id)\
        .order_by(Message.created_at.asc())\
        .all()


def create_message(
    db: Session,
    conversation_id: bytes,
    role: str,
    content: str,
    metadata: dict = None
) -> Message:
    """Create a new message"""
    message = Message(
        id=generate_uuid(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        msg_metadata=metadata
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def delete_message(db: Session, message_id: bytes) -> bool:
    """Delete a message"""
    message = get_message_by_id(db, message_id)
    if message:
        db.delete(message)
        db.commit()
        return True
    return False


def create_conversation_with_initial_message(
    db: Session,
    user_id: bytes,
    user_content: str,
    assistant_content: str = None,
    title: str = "New Chat"
) -> tuple[Conversation, Message]:
    """Create a new conversation with an initial message"""
    # Create conversation
    from app.crud.conversation import create_conversation
    conversation = create_conversation(db, user_id, title)
    
    # Create user message
    user_message = create_message(
        db=db,
        conversation_id=conversation.id,
        role="user",
        content=user_content
    )
    
    # Create assistant message if provided
    if assistant_content:
        create_message(
            db=db,
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content
        )
    
    return conversation, user_message


def update_message_favor(db: Session, message_id: bytes, is_favored: bool) -> Message:
    """Update message favor status"""
    import logging
    message = get_message_by_id(db, message_id)
    if message:
        logging.info(f"Updating message favor status: message_id={message_id}, is_favored={is_favored}, current_status={message.is_favored}")
        message.is_favored = is_favored
        db.commit()
        db.refresh(message)
        logging.info(f"Message favor status updated successfully: new_status={message.is_favored}")
    else:
        logging.warning(f"Message not found for update: message_id={message_id}")
    return message