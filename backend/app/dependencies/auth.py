from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import hashlib
from datetime import datetime

from app.models import get_db
from app.schemas.user import TokenData, User
from app.crud.user import get_user_by_email
from app.crud.auth_token import is_auth_token_valid
from app.config import settings
from app.utils.uuid import bytes_to_uuid_string


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    # Hash the token for database lookup
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    # Check if token is valid in database
    if not is_auth_token_valid(db, token_hash):
        raise credentials_exception
    
    user = get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    
    # Convert binary ID to string for response
    user_dict = {
        "id": bytes_to_uuid_string(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "is_active": bool(user.is_active),
        "created_at": user.created_at
    }
    
    return User(**user_dict)