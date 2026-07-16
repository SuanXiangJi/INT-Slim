import random
import string
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.verification_code import VerificationCode
from app.schemas.verification_code import VerificationCodeCreate
from app.utils.uuid import generate_uuid
from app.config import settings


def generate_verification_code(length: int = 6) -> str:
    """Generate a random verification code"""
    return ''.join(random.choices(string.digits, k=length))


def get_verification_code_by_email_and_purpose(
    db: Session, email: str, purpose: str
) -> VerificationCode:
    """Get the latest verification code for a specific email and purpose"""
    return (
        db.query(VerificationCode)
        .filter(
            and_(
                VerificationCode.email == email,
                VerificationCode.purpose == purpose,
                VerificationCode.is_used == 0,
                VerificationCode.expires_at > datetime.utcnow()
            )
        )
        .order_by(VerificationCode.created_at.desc())
        .first()
    )


def get_verification_code_by_code(
    db: Session, email: str, code: str, purpose: str
) -> VerificationCode:
    """Get a verification code by its value, email, and purpose"""
    return (
        db.query(VerificationCode)
        .filter(
            and_(
                VerificationCode.email == email,
                VerificationCode.code == code,
                VerificationCode.purpose == purpose,
                VerificationCode.is_used == 0,
                VerificationCode.expires_at > datetime.utcnow()
            )
        )
        .first()
    )


def create_verification_code(
    db: Session, verification_code: VerificationCodeCreate
) -> VerificationCode:
    """Create a new verification code"""
    # Generate code
    code = generate_verification_code(settings.verification_code_length)
    
    # Calculate expiration time
    expires_at = datetime.utcnow() + timedelta(
        minutes=settings.verification_code_expire_minutes
    )
    
    # Create verification code
    db_verification_code = VerificationCode(
        id=generate_uuid(),
        email=verification_code.email,
        code=code,
        purpose=verification_code.purpose,
        expires_at=expires_at,
    )
    
    db.add(db_verification_code)
    db.commit()
    db.refresh(db_verification_code)
    
    return db_verification_code


def mark_verification_code_as_used(
    db: Session, verification_code: VerificationCode
) -> VerificationCode:
    """Mark a verification code as used"""
    verification_code.is_used = 1
    db.commit()
    db.refresh(verification_code)
    return verification_code


def delete_expired_verification_codes(db: Session) -> int:
    """Delete all expired verification codes"""
    result = db.query(VerificationCode).filter(
        VerificationCode.expires_at < datetime.utcnow()
    ).delete()
    db.commit()
    return result


def check_code_rate_limit(db: Session, email: str, purpose: str) -> bool:
    """Check if the user has requested too many codes recently (rate limit)"""
    # Check if there are any codes sent in the last 1 minute
    one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
    
    recent_codes = (
        db.query(VerificationCode)
        .filter(
            and_(
                VerificationCode.email == email,
                VerificationCode.purpose == purpose,
                VerificationCode.created_at >= one_minute_ago
            )
        )
        .count()
    )
    
    return recent_codes < 3  # Allow up to 3 codes per minute
