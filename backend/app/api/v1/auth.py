from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
import hashlib

from app.models import get_db
from app.schemas.user import User, UserCreate, Token, UserLogin
from app.schemas.verification_code import (
    VerificationCodeCreate, 
    VerificationCodeVerify, 
    SendCodeResponse
)
from app.crud.user import get_user_by_email, create_user
from app.crud.verification_code import (
    create_verification_code,
    get_verification_code_by_code,
    mark_verification_code_as_used,
    check_code_rate_limit,
    get_verification_code_by_email_and_purpose
)
from app.crud.auth_token import create_auth_token, get_user_auth_tokens, revoke_auth_token, is_auth_token_valid, revoke_auth_token_by_hash
from app.utils.password import verify_password
from app.utils.jwt import create_access_token
from app.utils.uuid import bytes_to_uuid_string
from app.config import settings
from app.dependencies.auth import get_current_user
from app.utils.email import send_verification_code_email

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@router.post("/send-code", response_model=SendCodeResponse, status_code=status.HTTP_200_OK)
async def send_verification_code(
    code_data: VerificationCodeCreate,
    db: Session = Depends(get_db)
):
    """Send verification code to email"""
    # Check rate limit
    if not check_code_rate_limit(db, code_data.email, code_data.purpose):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later."
        )
    
    # Create verification code
    verification_code = create_verification_code(db, code_data)
    
    # Send email asynchronously
    is_sent = await send_verification_code_email(
        email=code_data.email,
        code=verification_code.code,
        purpose=code_data.purpose
    )
    
    if not is_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification code. Please try again later."
        )
    
    return SendCodeResponse(
        message="Verification code sent successfully",
        email=code_data.email,
        expires_in=settings.verification_code_expire_minutes * 60
    )


@router.post("/verify-code", status_code=status.HTTP_200_OK)
def verify_verification_code(
    verify_data: VerificationCodeVerify,
    db: Session = Depends(get_db)
):
    """Verify verification code"""
    # Check if email is already registered first
    if verify_data.purpose == 'register':
        existing_user = get_user_by_email(db, email=verify_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已注册，请直接登录"
            )

    # Get verification code
    verification_code = get_verification_code_by_code(
        db,
        verify_data.email,
        verify_data.code,
        verify_data.purpose
    )

    if not verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )

    # Mark code as used
    mark_verification_code_as_used(db, verification_code)

    return {"message": "Verification code verified successfully"}


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    db_user = get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    db_user = create_user(db=db, user=user)
    
    # Convert to Pydantic model with proper UUID conversion
    return User(
        id=bytes_to_uuid_string(db_user.id),
        email=db_user.email,
        nickname=db_user.nickname,
        is_active=bool(db_user.is_active),
        created_at=db_user.created_at
    )


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db), request: Request = Request):
    """Login a user"""
    user = get_user_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(days=settings.access_token_expire_days)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    # Calculate expires_at time
    expires_at = datetime.utcnow() + access_token_expires
    
    # Hash the token for storage (SHA-256 produces 64 hex characters)
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()
    
    # Get client IP and user agent
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent")
    
    # Store token in database
    create_auth_token(
        db=db,
        token_hash=token_hash,
        user_id=user.id,
        expires_at=expires_at,
        token_type="access_token",
        ip_address=client_ip,
        user_agent=user_agent
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login/json", response_model=Token)
def login_json(user_login: UserLogin, db: Session = Depends(get_db), request: Request = Request):
    """Login a user with JSON body"""
    user = get_user_by_email(db, email=user_login.email)
    if not user or not verify_password(user_login.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(days=settings.access_token_expire_days)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    # Calculate expires_at time
    expires_at = datetime.utcnow() + access_token_expires
    
    # Hash the token for storage (SHA-256 produces 64 hex characters)
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()
    
    # Get client IP and user agent
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent")
    
    # Store token in database
    create_auth_token(
        db=db,
        token_hash=token_hash,
        user_id=user.id,
        expires_at=expires_at,
        token_type="access_token",
        ip_address=client_ip,
        user_agent=user_agent
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=User)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@router.post("/refresh-token", response_model=Token)
def refresh_token(db: Session = Depends(get_db), request: Request = Request, current_user: User = Depends(get_current_user)):
    """Refresh access token using current valid token"""
    # Get current token from request headers
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token (remove "Bearer " prefix)
    current_token = auth_header.split(" ")[1]
    
    # Hash the current token for database lookup
    current_token_hash = hashlib.sha256(current_token.encode()).hexdigest()
    
    # Generate new access token
    access_token_expires = timedelta(days=settings.access_token_expire_days)
    new_access_token = create_access_token(
        data={"sub": current_user.email}, expires_delta=access_token_expires
    )
    
    # Calculate expires_at time
    expires_at = datetime.utcnow() + access_token_expires
    
    # Hash the new token for storage
    new_token_hash = hashlib.sha256(new_access_token.encode()).hexdigest()
    
    # Get client IP and user agent
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent")
    
    # Store new token in database
    # First, we need to get the user's binary ID from the database
    user = get_user_by_email(db, email=current_user.email)
    create_auth_token(
        db=db,
        token_hash=new_token_hash,
        user_id=user.id,
        expires_at=expires_at,
        token_type="access_token",
        ip_address=client_ip,
        user_agent=user_agent
    )
    
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.get("/tokens", response_model=list[dict])
def get_user_tokens(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all tokens for current user"""
    # Get user's binary ID from database
    user = get_user_by_email(db, email=current_user.email)
    
    # Get all tokens for the user
    tokens = get_user_auth_tokens(db, user.id)
    
    # Convert tokens to response format
    token_list = []
    for token in tokens:
        token_list.append({
            "id": token.id,
            "token_type": token.token_type,
            "created_at": token.created_at,
            "expires_at": token.expires_at,
            "is_revoked": token.is_revoked,
            "ip_address": token.ip_address,
            "user_agent": token.user_agent,
            "device_name": token.device_name
        })
    
    return token_list


@router.post("/tokens/{token_id}/revoke", response_model=dict)
def revoke_token(token_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Revoke a specific token"""
    # Check if token exists and belongs to the current user
    user = get_user_by_email(db, email=current_user.email)
    tokens = get_user_auth_tokens(db, user.id)
    
    token_exists = any(token.id == token_id for token in tokens)
    if not token_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found"
        )
    
    # Revoke the token
    success = revoke_auth_token(db, token_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke token"
        )
    
    return {"message": "Token revoked successfully"}


@router.post("/tokens/revoke-all", response_model=dict)
def revoke_all_tokens(db: Session = Depends(get_db), request: Request = Request, current_user: User = Depends(get_current_user)):
    """Revoke all tokens for current user except the current one"""
    # Get current token from request headers
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token (remove "Bearer " prefix)
    current_token = auth_header.split(" ")[1]
    current_token_hash = hashlib.sha256(current_token.encode()).hexdigest()
    
    # Get user's binary ID from database
    user = get_user_by_email(db, email=current_user.email)
    
    # Get all tokens for the user
    tokens = get_user_auth_tokens(db, user.id)
    
    # Revoke all tokens except the current one
    revoked_count = 0
    for token in tokens:
        # Skip the current token
        if token.token_hash != current_token_hash:
            success = revoke_auth_token(db, token.id)
            if success:
                revoked_count += 1
    
    return {"message": f"Revoked {revoked_count} tokens successfully"}


@router.post("/logout", response_model=dict)
def logout(db: Session = Depends(get_db), request: Request = Request, current_user: User = Depends(get_current_user)):
    """Logout current user by revoking their token"""
    # Get current token from request headers
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token (remove "Bearer " prefix)
    current_token = auth_header.split(" ")[1]
    
    # Hash the token for database lookup
    token_hash = hashlib.sha256(current_token.encode()).hexdigest()
    
    # Revoke the token
    success = revoke_auth_token_by_hash(db, token_hash)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout"
        )
    
    return {"message": "Logout successful"}