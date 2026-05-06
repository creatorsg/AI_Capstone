"""아이 정보 모델 (Child: 기본정보, ChildProfile: 민감정보 분리)"""

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Child(Base):
    """아이의 기본 정보 (비민감 데이터)"""
    __tablename__ = "children"

    id         = Column(Integer, primary_key=True, index=True)
    # JWT 인증: 각 아이는 반드시 특정 부모(User)에게 귀속됨 (마이그레이션 0003 기준)
    # 회원 탈퇴 시 자식 데이터 일괄 정리되도록 ondelete=CASCADE
    user_id    = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name       = Column(String(50), nullable=False)
    birth_date = Column(Date, nullable=True)
    gender     = Column(String(10), nullable=True)   # "male" | "female"

    # 신체 정보
    height_cm  = Column(Float, nullable=True)                 # 키 (cm)
    weight_kg  = Column(Float, nullable=True)                 # 체중 (kg)

    # RAG/AI 컨텍스트용 필드 (맞춤 답변에 필요)
    allergies  = Column(JSON, default=list, nullable=False)   # ["달걀", "우유"]
    conditions = Column(JSON, default=list, nullable=False)   # ["아토피", "천식"]
    notes      = Column(Text, default="", nullable=True)      # 보호자 자유 메모

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 관계 정의 (ORM 레벨 cascade 보강 - DB FK 의 ON DELETE 와 같이 동작)
    profile          = relationship(
        "ChildProfile",
        back_populates="child",
        uselist=False,                          # 1:1 관계
        cascade="all, delete-orphan",
    )
    health_logs      = relationship(
        "HealthLog",
        back_populates="child",
        cascade="all, delete-orphan",
    )
    vaccinations     = relationship(
        "VaccinationRecord",
        back_populates="child",
        cascade="all, delete-orphan",
    )
    # chat_histories / conversation_sessions 는 SET NULL 정책이라 cascade 미설정
    # → DB 레벨에서 child_id 만 NULL 로 바뀌고 레코드는 보존됨


class ChildProfile(Base):
    """아이의 민감 개인정보 (PII) - Child와 분리 보관 (1:1)"""
    __tablename__ = "child_profiles"

    id                = Column(Integer, primary_key=True, index=True)
    # 1:1 관계 강제 (UNIQUE) + child 삭제 시 함께 삭제 (CASCADE)
    child_id          = Column(
        Integer,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    playfab_id        = Column(String, unique=True, index=True, nullable=True)
    real_name         = Column(String(50), nullable=False)
    emergency_address = Column(String, nullable=True)
    blood_type        = Column(String(5), nullable=True)   