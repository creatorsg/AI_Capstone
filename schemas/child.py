"""아이 정보 Pydantic 스키마"""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date, datetime
from typing import Optional, List


# Child (기본 정보) 스키마

class ChildCreate(BaseModel):
    """아이 등록 시 요청 바디"""
    name: str = Field(..., min_length=1, max_length=50)
    gender: str                              # "male" | "female"
    birth_date: date
    height_cm: Optional[float] = None       # 키 (cm)
    weight_kg: Optional[float] = None       # 체중 (kg)
    allergies: List[str] = []               # RAG 맞춤 답변용 (예: ["달걀", "우유"])
    conditions: List[str] = []             # RAG 맞춤 답변용 (예: ["아토피"])
    notes: str = ""                          # 보호자 메모

    @field_validator("name")
    @classmethod
    def strip_and_validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("이름은 빈 문자열일 수 없습니다.")
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        allowed = ("male", "female")
        if v not in allowed:
            raise ValueError(f"gender 는 {allowed} 중 하나여야 합니다.")
        return v

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("생년월일은 오늘 이후일 수 없습니다.")
        return v


class ChildUpdate(BaseModel):
    """아이 정보 수정 (PATCH: 일부 필드만 전송 가능)"""
    name: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    allergies: Optional[List[str]] = None
    conditions: Optional[List[str]] = None
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("이름은 빈 문자열일 수 없습니다.")
        if len(v) > 50:
            raise ValueError("이름은 50자 이하여야 합니다.")
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("male", "female"):
            raise ValueError("gender 는 'male' 또는 'female' 이어야 합니다.")
        return v

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v > date.today():
            raise ValueError("생년월일은 오늘 이후일 수 없습니다.")
        return v


class ChildResponse(BaseModel):
    """아이 정보 응답

    모델의 birth_date / gender 가 nullable 이므로 응답에서도 Optional 처리.
    """
    id: int
    name: str
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    allergies: List[str] = []
    conditions: List[str] = []
    notes: Optional[str] = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ChildProfile (민감 정보) 스키마

class ChildProfileCreate(BaseModel):
    """아이 민감정보 등록 시 요청 바디

    child_id 는 필수 - 1:1 관계라서 어떤 아이의 프로필인지 명시되어야 함.
    """
    child_id: int                                # 필수 (마이그레이션 0003)
    playfab_id: Optional[str] = None
    real_name: str = Field(..., min_length=1, max_length=50)
    emergency_address: Optional[str] = None
    blood_type: Optional[str] = None      # "A+", "B-", "O+" 등
    medical_notes: Optional[str] = None   # 알레르기 상세, 특이사항


class ChildProfileUpdate(BaseModel):
    """아이 민감정보 부분 수정"""
    playfab_id: Optional[str] = None
    real_name: Optional[str] = None
    emergency_address: Optional[str] = None
    blood_type: Optional[str] = None
    medical_notes: Optional[str] = None


class ChildProfileResponse(BaseModel):
    """아이 민감 개인정보 응답 스키마"""
    id:               int
    child_id:         int
    playfab_id:       Optional[str] = None
    real_name:        Optional[str] = None
    emergency_address:Optional[str] = None
    blood_type:       Optional[str] = None
    medical_notes:    Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
