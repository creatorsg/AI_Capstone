"""사용자 계정 Pydantic 스키마 (회원가입/로그인/토큰)"""

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


# 회원가입 요청
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nickname: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        return v


# 로그인 요청
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# 사용자 정보 응답
class UserResponse(BaseModel):
    id: int
    email: str
    nickname: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# JWT 토큰 응답
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# 토큰 갱신 요청
class RefreshRequest(BaseModel):
    refresh_token: str


# 토큰 내부 페이로드 (내부 사용)
class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
