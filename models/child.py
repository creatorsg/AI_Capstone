"""아이 정보 모델 (Child: 기본정보, ChildProfile: 민감정보 분리)"""

from sqlalchemy import Column, Integer, String, Date, DateTime, Text, JSON, ForeignKey
from sqlalchemy.sql import func
from database import Base


class Child(Base):
    """아이의 기본 정보 (비민감 데이터)"""
    __tablename__ = "children"

    id         = Column(Integer, primary_key=True, index=True)
    # JWT 인증 추가: 각 아이는 특정 부모(User)에게 귀속됨
    # → 로그인한 사용자는 자신의 아이 데이터만 조회/수정/삭제 가능
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name       = Column(String(50), nullable=False)
    birth_date = Column(Date, nullable=True)
    gender     = Column(String(10), nullable=True)   # "male" | "female"

    # RAG/AI 컨텍스트용 필드 (맞춤 답변에 필요)
    allergies  = Column(JSON, default=list, nullable=False)   # ["달걀", "우유"]
    conditions = Column(JSON, default=list, nullable=False)   # ["아토피", "천식"]
    notes      = Column(Text, default="", nullable=True)      # 보호자 자유 메모

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ChildProfile(Base):
    """아이의 민감 개인정보 (PII) - Child와 분리 보관"""
    __tablename__ = "child_profiles"

    id                = Column(Integer, primary_key=True, index=True)
    child_id          = Column(Integer, ForeignKey("children.id"), nullable=True)
    playfab_id        = Column(String, unique=True, index=True, nullable=True)
    real_name         = Column(String(50), nullable=False)
    emergency_address = Column(String, nullable=True)
    blood_type        = Column(String(5), nullable=True)     # "A+", "O-" 등
    medical_notes     = Column(Text, nullable=True)          # 특이사항, 알레르기 상세
