from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


# HealthLog 스키마

class HealthLogCreate(BaseModel):
    """건강 기록 추가 요청"""
    child_id: int
    log_type: str       # "fever" | "meal" | "sleep" | "breastfeed" | "formula"
    value: Optional[str] = None   # "38.5°C", "150ml", "2시간" 등
    note: Optional[str] = None


class HealthLogResponse(BaseModel):
    """건강 기록 응답"""
    id: int
    child_id: int
    log_type: str
    value: Optional[str] = None
    note: Optional[str] = None
    recorded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# VaccinationRecord 스키마

class VaccinationCreate(BaseModel):
    """예방접종 기록 추가 요청"""
    child_id: int
    vaccine_name: str           # "BCG", "DTaP 1차" 등
    vaccinated_at: Optional[date] = None
    next_due: Optional[date] = None
    note: Optional[str] = None


class VaccinationResponse(BaseModel):
    """예방접종 기록 응답"""
    id: int
    child_id: int
    vaccine_name: str
    vaccinated_at: Optional[date] = None
    next_due: Optional[date] = None
    note: Optional[str] = None

    model_config = {"from_attributes": True}
