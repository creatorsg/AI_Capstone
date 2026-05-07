"""아이 정보 CRUD API (JWT 인증, 소유권 검증)"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.child import Child, ChildProfile
from models.user import User
from schemas.child import (
    ChildCreate, ChildUpdate, ChildResponse,
    ChildProfileCreate, ChildProfileResponse
)
from services.auth_service import get_current_user

router = APIRouter(
    prefix="/children",
    tags=["아이 정보"]
)


# 소유권 검증 헬퍼
def _get_owned_child(child_id: int, db: Session, current_user: User) -> Child:
    """
    주어진 child_id 의 아이 정보를 반환합니다.
    - 아이가 없으면 404
    - 아이의 user_id 가 현재 사용자와 다르면 403
    """
    child = db.query(Child).filter(Child.id == child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="아이 정보를 찾을 수 없습니다.")
    if child.user_id is not None and child.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다.",
        )
    return child


# Child (기본 정보) CRUD

@router.post(
    "/",
    response_model=ChildResponse,
    status_code=status.HTTP_201_CREATED,
    summary="아이 기본 정보 등록",
)
def create_child(
    child: ChildCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    아이 기본 정보를 등록합니다.

    - **allergies**: RAG 맞춤 답변에 활용됩니다. (예: ["달걀", "우유"])
    - **conditions**: RAG 맞춤 답변에 활용됩니다. (예: ["아토피"])
    - 등록 시 자동으로 현재 로그인된 사용자의 아이로 저장됩니다.
    """
    new_child = Child(**child.model_dump())
    new_child.user_id = current_user.id   # ← 소유권 자동 설정
    db.add(new_child)
    db.commit()
    db.refresh(new_child)
    return new_child


@router.get("/", response_model=list[ChildResponse], summary="내 아이 목록 조회")
def get_children(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """현재 로그인된 사용자의 아이 목록만 반환합니다."""
    return (
        db.query(Child)
        .filter(Child.user_id == current_user.id)
        .order_by(Child.id.desc())
        .all()
    )


@router.get("/{child_id}", response_model=ChildResponse, summary="특정 아이 정보 조회")
def get_child(
    child_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_owned_child(child_id, db, current_user)


@router.patch(
    "/{child_id}",
    response_model=ChildResponse,
    summary="아이 기본 정보 수정 (변경 필드만 전송)",
)
def update_child(
    child_id: int,
    child: ChildUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    바뀐 필드만 포함해서 전송하면 됩니다 (PATCH 방식).

    예시: `{ "notes": "이유식 시작" }` → notes 만 업데이트
    """
    db_child = _get_owned_child(child_id, db, current_user)

    update_data = child.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_child, key, value)

    db.commit()
    db.refresh(db_child)
    return db_child


@router.delete(
    "/{child_id}",
    status_code=status.HTTP_200_OK,
    summary="아이 정보 삭제",
)
def delete_child(
    child_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    아이 정보를 삭제합니다.
    연관된 건강 기록 및 채팅 기록도 함께 삭제됩니다.
    """
    db_child = _get_owned_child(child_id, db, current_user)
    db.delete(db_child)
    db.commit()
    return {"message": f"아이 정보(id={child_id})가 삭제되었습니다."}


# ChildProfile (민감 정보) CRUD

def _get_owned_profile(profile_id: int, db: Session, current_user: User) -> ChildProfile:
    """프로필의 소유권(child.user_id)을 검증하고 반환합니다."""
    profile = db.query(ChildProfile).filter(ChildProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다.")

    child = db.query(Child).filter(Child.id == profile.child_id).first()
    if child and child.user_id is not None and child.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="접근 권한이 없습니다.",
        )
    return profile


@router.post(
    "/profiles/",
    response_model=ChildProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="아이 민감 정보 등록",
)
def create_profile(
    profile: ChildProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # child_id 가 요청자의 아이인지 검증
    child = db.query(Child).filter(Child.id == profile.child_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="아이 정보를 찾을 수 없습니다.")
    if child.user_id is not None and child.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

    db_profile = ChildProfile(**profile.model_dump())
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile


@router.get(
    "/profiles/{profile_id}",
    response_model=ChildProfileResponse,
    summary="민감 정보 조회",
)
def get_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_owned_profile(profile_id, db, current_user)


@router.delete(
    "/profiles/{profile_id}",
    status_code=status.HTTP_200_OK,
    summary="민감 정보 삭제",
)
def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = _get_owned_profile(profile_id, db, current_user)
    db.delete(profile)
    db.commit()
    return {"message": f"민감 정보(id={profile_id})가 삭제되었습니다."}
