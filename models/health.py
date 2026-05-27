from sqlalchemy import Column, Integer, String, Date, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class HealthLog(Base):
    """아이의 건강 기록 (열, 수유, 수면, 식사 등)"""
    __tablename__ = "health_logs"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)

    # log_type 예시: "fever" | "meal" | "sleep" | "breastfeed" | "formula"
    log_type = Column(String, nullable=False)

    # value: 열이면 "38.5", 수유면 "150ml" 등 유연하게 문자열로 저장
    value = Column(String, nullable=True)
    note = Column(String, nullable=True)
    recorded_at = Column(DateTime, server_default=func.now(), nullable=False)

    child = relationship("Child", back_populates="health_logs")


class VaccinationRecord(Base):
    """예방접종 기록"""
    __tablename__ = "vaccination_records"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    vaccine_name = Column(String, nullable=False)   # 예: "BCG", "DTaP 1차"
    vaccinated_at = Column(Date, nullable=True)     # 접종일
    next_due = Column(Date, nullable=True)          # 다음 접종 예정일
    note = Column(String, nullable=True)

    child = relationship("Child", back_populates="vaccinations")


class ChildNote(Base):
    """아이 노트 - 날짜별 일기/간식/행동발달/증상 기록"""
    __tablename__ = "child_notes"

    id        = Column(Integer, primary_key=True, index=True)
    child_id  = Column(
        Integer,
        ForeignKey("children.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category  = Column(String(20), nullable=False, index=True)  # diary|snack|behavior|symptom
    note_date = Column(Date, nullable=False, index=True)
    title     = Column(String(100), nullable=True)
    content   = Column(Text, nullable=False)
    value     = Column(Float, nullable=True)         # 발열: 38.5 / 행동 점수 등
    unit      = Column(String(20), nullable=True)    # "°C", "회" 등
    severity  = Column(String(10), nullable=True)    # mild|moderate|severe (symptom 전용)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    child = relationship("Child", back_populates="notes_list")
