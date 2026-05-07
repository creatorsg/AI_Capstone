"""사용자(부모) 계정 모델 (JWT 인증 기반)"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id             = Column(Integer, primary_key=True, index=True)
    email          = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)   # bcrypt 해시
    nickname       = Column(String(50), nullable=True)       # 보호자 닉네임
    is_active      = Column(Boolean, default=True)           # 탈퇴/정지 처리용
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())
