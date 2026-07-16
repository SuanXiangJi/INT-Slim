from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from app.models.auth_token import AuthToken


def create_auth_token(
    db: Session,
    token_hash: str,
    user_id: bytes,
    expires_at: datetime,
    token_type: str = "access_token",
    ip_address: str = None,
    user_agent: str = None,
    device_name: str = None
) -> AuthToken:
    """Create a new auth token record"""
    db_token = AuthToken(
        token_hash=token_hash,
        user_id=user_id,
        token_type=token_type,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
        device_name=device_name
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_auth_token_by_hash(db: Session, token_hash: str) -> AuthToken:
    """Get auth token by token hash"""
    return db.query(AuthToken).filter(AuthToken.token_hash == token_hash).first()


def revoke_auth_token(db: Session, token_id: int) -> bool:
    """Revoke an auth token"""
    db_token = db.query(AuthToken).filter(AuthToken.id == token_id).first()
    if db_token:
        db_token.is_revoked = 1
        db.commit()
        db.refresh(db_token)
        return True
    return False


def revoke_auth_token_by_hash(db: Session, token_hash: str) -> bool:
    """Revoke an auth token by its hash"""
    db_token = get_auth_token_by_hash(db, token_hash)
    if db_token:
        db_token.is_revoked = 1
        db.commit()
        db.refresh(db_token)
        return True
    return False


def is_auth_token_valid(db: Session, token_hash: str) -> bool:
    """Check if an auth token is valid"""
    db_token = get_auth_token_by_hash(db, token_hash)
    if not db_token:
        return False
    
    if db_token.is_revoked:
        return False
    
    if db_token.expires_at < datetime.utcnow():
        return False
    
    return True


def get_user_auth_tokens(db: Session, user_id: bytes) -> list[AuthToken]:
    """Get all auth tokens for a user"""
    return db.query(AuthToken).filter(AuthToken.user_id == user_id).all()


def delete_expired_auth_tokens(db: Session) -> int:
    """Delete all expired auth tokens"""
    result = db.query(AuthToken).filter(AuthToken.expires_at < datetime.utcnow()).delete()
    db.commit()
    return result


def delete_revoked_auth_tokens(db: Session) -> int:
    """Delete all revoked auth tokens"""
    result = db.query(AuthToken).filter(AuthToken.is_revoked == 1).delete()
    db.commit()
    return result