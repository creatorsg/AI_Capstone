"""JWT 기반 회원가입 / 로그인 / 토큰 갱신 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.user import UserCreate, UserLogin, UserResponse, Token, RefreshRequest
from services.auth_service import (
    hash_password,
    verify_password,
    create_token_pair,
    decode_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["인증"])


# 회원가입
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
def register(body: UserCreate, db: Session = Depends(get_db)):
    """
    부모 계정을 생성합니다.

    - 이메일 중복 시 409 반환
    - 비밀번호는 bcrypt 해시 후 저장 (평문 저장 없음)
    """
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 이메일입니다.",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        nickname=body.nickname,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# 로그인
@router.post("/login", response_model=Token, summary="로그인")
def login(body: UserLogin, db: Session = Depends(get_db)):
    """
    이메일 + 비밀번호로 로그인합니다.

    성공 시 응답:
    ```json
    {
      "access_token":  "eyJ...",   // 30분 유효 (API 요청 시 사용)
      "refresh_token": "eyJ...",   // 7일 유효 (재발급 시 사용)
      "token_type":    "bearer"
    }
    ```

    프론트엔드에서 access_token 은 메모리(변수)에,
    refresh_token 은 HttpOnly 쿠키에 저장하는 것을 권장합니다.
    """
    user = db.query(User).filter(User.email == body.email).first()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다. 관리자에게 문의하세요.",
        )

    return create_token_pair(user.id, user.email)


# 토큰 갱신
@router.post("/refresh", response_model=Token, summary="Access Token 갱신")
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    """
    Refresh Token 으로 새 Access Token + Refresh Token 을 발급합니다.

    - Access Token 이 만료됐을 때 재로그인 없이 갱신할 수 있습니다.
    - Refresh Token 도 함께 갱신됩니다 (보안 강화).
    """
    payload = decode_token(body.refresh_token, expected_type="refresh")
    user_id = int(payload["sub"])

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )

    return create_token_pair(user.id, user.email)


# 내 정보 조회
@router.get("/me", response_model=UserResponse, summary="현재 로그인 사용자 정보")
def get_me(current_user: User = Depends(get_current_user)):
    """
    현재 로그인한 사용자의 정보를 반환합니다.

    헤더: `Authorization: Bearer <access_token>`
    """
    return current_user


# 로그아웃
@router.post("/logout", summary="로그아웃")
def logout(current_user: User = Depends(get_current_user)):
    """
    로그아웃 처리입니다.

    JWT 는 서버에 상태를 저장하지 않으므로,
    클라이언트 측에서 토큰을 삭제하면 됩니다.
    (추후 Redis 블랙리스트를 구현하면 서버 측 무효화도 가능)
    """
    return {"message": "로그아웃 되었습니다. 클라이언트 토큰을 삭제하세요."}
