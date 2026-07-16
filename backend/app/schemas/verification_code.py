from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Literal


class VerificationCodeBase(BaseModel):
    email: EmailStr
    purpose: Literal['register', 'login', 'reset_password']


class VerificationCodeCreate(VerificationCodeBase):
    pass


class VerificationCodeVerify(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    purpose: Literal['register', 'login', 'reset_password']


class VerificationCode(VerificationCodeBase):
    id: str
    user_id: Optional[str] = None
    code: str
    is_used: bool
    created_at: datetime
    expires_at: datetime
    
    class Config:
        from_attributes = True


class SendCodeResponse(BaseModel):
    message: str
    email: str
    expires_in: int  # 验证码有效期（秒）