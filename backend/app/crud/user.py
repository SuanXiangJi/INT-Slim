from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
from app.utils.password import get_password_hash
from app.utils.uuid import generate_uuid


def get_user_by_email(db: Session, email: str) -> User:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: bytes) -> User:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user: UserCreate) -> User:
    """Create a new user"""
    db_user = User(
        id=generate_uuid(),
        email=user.email,
        password_hash=get_password_hash(user.password),
        nickname=user.nickname,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user