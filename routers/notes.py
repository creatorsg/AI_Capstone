"""아이 노트 API - 날짜별 일기/발달/증상/간식 기록 및 빈도 분석"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.health import ChildNote
from models.user import User
from schemas.health import (
    ChildNoteCreate,
    ChildNoteUpdate,
    ChildNoteResponse,
    ChildNoteAnalysis,
    SymptomFrequency,
)
from services.auth_service import get_current_user, verify_child_ownership

router = APIRouter(prefix="/notes", tags=["아이 노트"])

VALID_DAYS = {7, 30, 90}


# ─────────────────────────────────────────────────────────────────────────────
# 노트 CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/{child_id}",
    response_model=ChildNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="아이 노트 작성",
)
def create_note(
    child_id: int,
    body: ChildNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """일기·간식·행동발달·증상 노트를 작성합니다."""
    verify_child_ownership(child_id, db, current_user)

    note = ChildNote(
        child_id=child_id,
        category=body.category,
        note_date=body.note_date,
        title=body.title,
        content=body.content,
        value=body.value,
        unit=body.unit,
        severity=body.severity,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get(
    "/{child_id}",
    response_model=list[ChildNoteResponse],
    summary="아이 노트 목록 조회",
)
def list_notes(
    child_id: int,
    category: Optional[str] = Query(default=None, description="diary|snack|behavior|symptom"),
    date_from: Optional[date] = Query(default=None),
    date_to:   Optional[date] = Query(default=None),
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """날짜·카테고리 필터로 노트 목록을 조회합니다. (최신순)"""
    verify_child_ownership(child_id, db, current_user)

    q = db.query(ChildNote).filter(ChildNote.child_id == child_id)
    if category:
        q = q.filter(ChildNote.category == category)
    if date_from:
        q = q.filter(ChildNote.note_date >= date_from)
    if date_to:
        q = q.filter(ChildNote.note_date <= date_to)

    return (
        q.order_by(ChildNote.note_date.desc(), ChildNote.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get(
    "/{child_id}/{note_id}",
    response_model=ChildNoteResponse,
    summary="아이 노트 단건 조회",
)
def get_note(
    child_id: int,
    note_id:  int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_child_ownership(child_id, db, current_user)
    note = db.query(ChildNote).filter(
        ChildNote.id == note_id,
        ChildNote.child_id == child_id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    return note


@router.patch(
    "/{child_id}/{note_id}",
    response_model=ChildNoteResponse,
    summary="아이 노트 수정",
)
def update_note(
    child_id: int,
    note_id:  int,
    body: ChildNoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_child_ownership(child_id, db, current_user)
    note = db.query(ChildNote).filter(
        ChildNote.id == note_id,
        ChildNote.child_id == child_id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")

    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(note, field, val)
    db.commit()
    db.refresh(note)
    return note


@router.delete(
    "/{child_id}/{note_id}",
    status_code=status.HTTP_200_OK,
    summary="아이 노트 삭제",
)
def delete_note(
    child_id: int,
    note_id:  int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_child_ownership(child_id, db, current_user)
    note = db.query(ChildNote).filter(
        ChildNote.id == note_id,
        ChildNote.child_id == child_id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    db.delete(note)
    db.commit()
    return {"message": f"노트({note_id}) 삭제 완료"}


# ─────────────────────────────────────────────────────────────────────────────
# 빈도 분석
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{child_id}/analysis/{category}",
    response_model=ChildNoteAnalysis,
    summary="카테고리별 빈도 분석 (7·30·90일)",
)
def analyze_notes(
    child_id: int,
    category: str,
    days: int = Query(default=30, description="7 / 30 / 90"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    지정 카테고리의 노트를 기간별로 집계합니다.
    - total_count : 전체 건수
    - daily_breakdown : 날짜별 건수 + 평균 수치
    - peak_date : 가장 많이 기록된 날
    - avg_value : 전체 평균 수치 (value 있는 경우)
    """
    if days not in VALID_DAYS:
        raise HTTPException(status_code=400, detail="days 는 7, 30, 90 중 하나여야 합니다.")
    verify_child_ownership(child_id, db, current_user)

    since = date.today() - timedelta(days=days)

    rows = (
        db.query(ChildNote)
        .filter(
            ChildNote.child_id == child_id,
            ChildNote.category == category,
            ChildNote.note_date >= since,
        )
        .order_by(ChildNote.note_date.asc())
        .all()
    )

    # 날짜별 집계
    daily: dict[date, list] = {}
    for r in rows:
        daily.setdefault(r.note_date, []).append(r)

    breakdown = []
    for d, items in sorted(daily.items()):
        values = [i.value for i in items if i.value is not None]
        breakdown.append(SymptomFrequency(
            date=d,
            count=len(items),
            avg_value=round(sum(values) / len(values), 2) if values else None,
        ))

    peak_date = max(daily, key=lambda d: len(daily[d])) if daily else None
    all_values = [r.value for r in rows if r.value is not None]
    avg_value  = round(sum(all_values) / len(all_values), 2) if all_values else None

    return ChildNoteAnalysis(
        child_id=child_id,
        days=days,
        category=category,
        total_count=len(rows),
        daily_breakdown=breakdown,
        peak_date=peak_date,
        avg_value=avg_value,
    )
