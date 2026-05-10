"""FastAPI 애플리케이션 진입점"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from database import engine, Base

# 모델 임포트 (Base.metadata.create_all이 모든 테이블을 인식하기 위해 필수)
from models.user import User                                   # 인증 테이블
from models.child import Child, ChildProfile
from models.health import HealthLog, VaccinationRecord
from models.chat import ChatHistory, ConversationSession


# lifespan: 앱 시작/종료 시 실행되는 이벤트 핸들러
# 기존 방식(Base.metadata.create_all 을 최상단에 호출)은
# 앱 임포트 시점에 DB 연결을 시도해 테스트가 어렵습니다.
# lifespan 이벤트로 이동하면 앱 실행 시에만 동작합니다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시: 없는 테이블만 자동 생성 (기존 데이터 유지)
    Base.metadata.create_all(bind=engine)
    yield
    # 종료 시: 필요한 정리 작업 (커넥션 풀 해제 등)
    engine.dispose()


# FastAPI 앱 생성
app = FastAPI(
    title="육아 AI 챗봇 API",
    description="""
초보 부모(0~5세 자녀)를 위한 AI 기반 육아 도우미 서비스

## 주요 기능
- **아이 프로필** 등록 및 관리
- **건강 기록** (발열, 수면, 수유, 예방접종)
- **AI 채팅** (역질문 시스템 + RAG 기반 답변)
- **주변 병원 검색** (GPS 기반 Kakao Maps)
- **정부 복지 정책** 안내
- **JWT 인증** (회원가입 / 로그인 / 토큰 갱신)
""",
    version="0.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# CORS 미들웨어
# 프론트엔드(React 등)에서 API 호출 시 반드시 필요합니다.
# 프로덕션 환경에서는 ALLOWED_ORIGINS를 실제 도메인으로 제한하세요.
# ⚠️ allow_origins=["*"] + allow_credentials=True 는 브라우저 스펙상 금지 조합입니다.
#    ALLOWED_ORIGINS="*" 일 때는 allow_credentials=False 로 자동 처리합니다.
import os
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
_is_wildcard = ALLOWED_ORIGINS == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=not _is_wildcard,   # "*" 일 땐 False, 명시적 도메인일 땐 True
    allow_methods=["*"],
    allow_headers=["*"],
)


# 라우터 등록
from routers.auth import router as auth_router               # JWT 인증
from routers.children import router as children_router
from routers.health import router as health_router
from routers.chat import router as chat_router
from routers.hospitals import router as hospitals_router
from routers.welfare import router as welfare_router

app.include_router(auth_router)       # /auth/register, /auth/login, ...
app.include_router(children_router)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(hospitals_router)
app.include_router(welfare_router)


# 헬스체크 엔드포인트
@app.get("/", tags=["서버 상태"], summary="서버 상태 확인")
def read_root():
    return {
        "status": "FastAPI is Running!",
        "service": "육아 AI 챗봇",
        "version": "0.2.0",
        "docs": "/docs",
    }


@app.get("/db-check", tags=["서버 상태"], summary="DB 연결 확인")
def check_db():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            return {"db_status": "Connected!", "version": result.fetchone()[0]}
    except Exception as e:
        return {"db_status": "Error", "message": str(e)}
