"""건강 기록 CRUD API (JWT 인증, 소유권 검증)"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.child import Child
from models.health import HealthLog, VaccinationRecord
from models.user import User
from schemas.health import (
    HealthLogCreate, HealthLogResponse,
    VaccinationCreate, VaccinationResponse
)
from services.auth_service import get_current_user

router = APIRouter(
    prefix="/health",
    tags=["건강 기록"]
)


# 소유권 검증 헬퍼
def _verify_child_owner(child_id: int, db: Session, current_user: User) -> None:
    """child_id 의 아이가 current_user 소유인지 검증합니다."""
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="아이 정보를 찾을 수 없습니다.")
    if child.user_id is not None and child.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다.",
        )


# HealthLog (건강 기록)

@router.post(
    "/logs/",
    response_model=HealthLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="건강 기록 추가 (열, 수유, 수면 등)",
)
def create_health_log(
    log: HealthLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_child_owner(log.child_id, db, current_user)
    new_log = HealthLog(**log.model_dump())
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log


@router.get(
    "/logs/{child_id}",
    response_model=list[HealthLogResponse],
    summary="아이 건강 기록 조회",
)
def get_health_logs(
    child_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_child_owner(child_id, db, current_user)
    return db.query(HealthLog).filter(HealthLog.child_id == child_id).all()


@router.get(
    "/logs/{child_id}/type/{log_type}",
    response_model=list[HealthLogResponse],
    summary="타입별 건강 기록 조회",
)
def get_health_logs_by_type(
    child_id: int,
    log_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_child_owner(child_id, db, current_user)
    return db.query(HealthLog).filter(
        HealthLog.child_id == child_id,
        HealthLog.log_type == log_type,
    ).all()


# VaccinationRecord (예방접종)

@router.post(
    "/vaccinations/",
    response_model=VaccinationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="예방접종 기록 추가",
)
def create_vaccination(
    vaccination: VaccinationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_child_owner(vaccination.child_id, db, current_user)
    new_vaccination = VaccinationRecord(**vaccination.model_dump())
    db.add(new_vaccination)
    db.commit()
    db.refresh(new_vaccination)
    return new_vaccination


@router.get(
    "/vaccinations/{child_id}",
    response_model=list[VaccinationResponse],
    summary="예방접종 기록 조회",
)
def get_vaccinations(
    child_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_child_owner(child_id, db, current_user)
    return db.query(VaccinationRecord).filter(
        VaccinationRecord.child_id == child_id
    ).all()
