"""아이 정보 Pydantic 스키마"""

from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Optional, List


# Child (기본 정보) 스키마

class ChildCreate(BaseModel):
    """아이 등록 시 요청 바디"""
    name: str
    gender: str                              # "male" | "female"
    birth_date: date
    allergies: List[str] = []               # RAG 맞춤 답변용 (예: ["달걀", "우유"])
    conditions: List[str] = []             # RAG 맞춤 답변용 (예: ["아토피"])
    notes: str = ""                          # 보호자 메모

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        allowed = ("male", "female")
        if v not in allowed:
            raise ValueError(f"gender 는 {allowed} 중 하나여야 합니다.")
        return v


class ChildUpdate(BaseModel):
    """아이 정보 수정 (PATCH: 일부 필드만 전송 가능)"""
    name: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    allergies: Optional[List[str]] = None
    conditions: Optional[List[str]] = None
    notes: Optional[str] = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("male", "female"):
            raise ValueError("gender 는 'male' 또는 'female' 이어야 합니다.")
        return v


class ChildResponse(BaseModel):
    """아이 정보 응답"""
    id: int
    name: str
    gender: str
    birth_date: date
    allergies: List[str] = []
    conditions: List[str] = []
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ChildProfile (민감 정보) 스키마

class ChildProfileCreate(BaseModel):
    """아이 민감정보 등록 시 요청 바디"""
    child_id: Optional[int] = None
    playfab_id: Optional[str] = None
    real_name: str
    emergency_address: Optional[str] = None
    blood_type: Optional[str] = None      # "A+", "B-", "O+" 등
    medical_notes: Optional[str] = None   # 알레르기 상세, 특이사항


class ChildProfileResponse(BaseModel):
    """아이 민감정보 응답"""
    id: int
    child_id: Optional[int] = None
    playfab_id: Optional[str] = None
    real_name: str
    emergency_address: Optional[str] = None
    blood_type: Optional[str] = None
    medical_notes: Optional[str] = None

    model_config = {"from_attributes": True}
