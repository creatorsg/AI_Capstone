"""FastAPI 애플리케이션 진입점"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from database import engine, Base

from models.user import User
from models.child import Child, ChildProfile
from models.health import HealthLog, VaccinationRecord, ChildNote
from models.chat import ChatHistory, ConversationSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


app = FastAPI(
    title="육아 AI 챗봇 API",
    description="초보 부모(0~5세 자녀)를 위한 AI 기반 육아 도우미 서비스",
    version="0.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

import os
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
_is_wildcard = ALLOWED_ORIGINS == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=not _is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.auth import router as auth_router
from routers.children import router as children_router
from routers.health import router as health_router
from routers.chat import router as chat_router
from routers.hospitals import router as hospitals_router
from routers.welfare import router as welfare_router
from routers.notes import router as notes_router

app.include_router(auth_router)
app.include_router(children_router)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(hospitals_router)
app.include_router(welfare_router)
app.include_router(notes_router)


@app.get("/", tags=["서버 상태"], summary="서버 상태 확인")
def read_root():
    return {"status": "FastAPI is Running!", "service": "육아 AI 챗봇", "version": "0.4.0", "docs": "/docs"}


@app.get("/db-check", tags=["서버 상태"], summary="DB 연결 확인")
def check_db():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            return {"db_status": "Connected!", "version": result.fetchone()[0]}
    except Exception as e:
        return {"db_status": "Error", "message": str(e)}
