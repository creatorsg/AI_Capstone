"""JWT 인증 서비스
- 비밀번호 bcrypt 해시/검증
- Access/Refresh 토큰 발급 및 검증
- FastAPI Depends 주입용 get_current_user()
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models.user import User

# 설정값
SECRET_KEY        = os.getenv("JWT_SECRET_KEY", "CHANGE-THIS-TO-A-SECURE-RANDOM-KEY-IN-PRODUCTION")
ALGORITHM         = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXP  = int(os.getenv("ACCESS_TOKEN_EXP", "30"))    # 분
REFRESH_TOKEN_EXP = int(os.getenv("REFRESH_TOKEN_EXP", "7"))    # 일

# bcrypt 컨텍스트
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer 토큰 추출기
bearer_scheme = HTTPBearer()


# 비밀번호 유틸리티

def hash_password(plain_password: str) -> str:
    """평문 비밀번호 → bcrypt 해시"""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """입력 비밀번호와 저장된 해시 비교"""
    return pwd_context.verify(plain_password, hashed_password)


# JWT 토큰 생성

def create_access_token(user_id: int, email: str) -> str:
    """
    Access Token 생성 (짧은 유효기간)

    페이로드:
      sub  : user_id (string)
      email: 이메일
      type : "access"
      exp  : 만료 시각
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXP)
    payload = {
        "sub":   str(user_id),
        "email": email,
        "type":  "access",
        "exp":   expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int, email: str) -> str:
    """
    Refresh Token 생성 (긴 유효기간)

    Access Token 만료 시 이 토큰으로 새 Access Token 발급
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXP)
    payload = {
        "sub":   str(user_id),
        "email": email,
        "type":  "refresh",
        "exp":   expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_token_pair(user_id: int, email: str) -> dict:
    """Access + Refresh 토큰 동시 발급"""
    return {
        "access_token":  create_access_token(user_id, email),
        "refresh_token": create_refresh_token(user_id, email),
        "token_type":    "bearer",
    }


# JWT 토큰 검증

def decode_token(token: str, expected_type: str = "access") -> dict:
    """
    JWT 토큰 디코딩 및 검증

    raises:
      401 - 토큰 만료 / 잘못된 형식 / 타입 불일치
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 토큰이 유효하지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 토큰 타입 검증 (access / refresh 혼용 방지)
        if payload.get("type") != expected_type:
            raise credentials_exception

        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        return payload

    except JWTError:
        raise credentials_exception


# FastAPI 의존성: 현재 로그인 사용자 반환

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI Depends() 에 주입해 로그인한 사용자를 반환합니다.

    사용법:
        @router.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            return {"user_id": current_user.id}

    Authorization 헤더:
        Authorization: Bearer <access_token>
    """
    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = int(payload["sub"])

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없거나 비활성화된 계정입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    토큰이 있으면 사용자 반환, 없어도 에러 없이 None 반환.
    공개/로그인 모두 허용하는 엔드포인트에서 사용.
    """
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = int(payload["sub"])
        return db.query(User).filter(User.id == user_id, User.is_active == True).first()
    except HTTPException:
        return None
