from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
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


class VaccinationRecord(Base):
    """예방접종 기록"""
    __tablename__ = "vaccination_records"

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    vaccine_name = Column(String, nullable=False)   # 예: "BCG", "DTaP 1차"
    vaccinated_at = Column(Date, nullable=True)     # 접종일
    next_due = Column(Date, nullable=True)          # 다음 접종 예정일
    note = Column(String, nullable=True)
