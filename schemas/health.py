from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Optional, Literal


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


# ChildNote 스키마

NoteCategory = Literal["diary", "snack", "behavior", "symptom"]
NoteSeverity  = Literal["mild", "moderate", "severe"]


class ChildNoteCreate(BaseModel):
    """아이 노트 생성 요청"""
    category:  NoteCategory
    note_date: date
    title:     Optional[str]   = None
    content:   str
    value:     Optional[float] = None   # 발열: 38.5 / 행동 점수 등
    unit:      Optional[str]   = None   # "°C", "회" 등
    severity:  Optional[NoteSeverity] = None  # symptom 전용


class ChildNoteUpdate(BaseModel):
    """아이 노트 수정 요청 (부분 수정 가능)"""
    title:    Optional[str]           = None
    content:  Optional[str]           = None
    value:    Optional[float]         = None
    unit:     Optional[str]           = None
    severity: Optional[NoteSeverity]  = None


class ChildNoteResponse(BaseModel):
    """아이 노트 응답"""
    id:         int
    child_id:   int
    category:   str
    note_date:  date
    title:      Optional[str]   = None
    content:    str
    value:      Optional[float] = None
    unit:       Optional[str]   = None
    severity:   Optional[str]   = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# 분석 응답 스키마

class SymptomFrequency(BaseModel):
    """날짜별 빈도 항목"""
    date:      date
    count:     int
    avg_value: Optional[float] = None


class ChildNoteAnalysis(BaseModel):
    """아이 노트 분석 응답"""
    child_id:        int
    days:            int
    category:        str
    total_count:     int
    daily_breakdown: list[SymptomFrequency]
    peak_date:       Optional[date]  = None
    avg_value:       Optional[float] = None
