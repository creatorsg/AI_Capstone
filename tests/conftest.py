"""pytest 공용 픽스처 (TestClient, 인증 헤더, 샘플 데이터)"""

import os
import sys

# 환경변수 (import 전에 설정)
os.environ.setdefault("JWT_SECRET_KEY",  "test-secret-key-for-pytest-only")
os.environ.setdefault("AI_PROVIDER",     "mock")
os.environ.setdefault("ALLOWED_ORIGINS", "*")
os.environ["MY_APP_DATABASE_URL"] = "sqlite://"   # database.py 가 읽는 키

# 프로젝트 루트를 경로에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 프로젝트 모듈 import
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database          # engine 레퍼런스 교체용
import main as app_main  # main.py 의 engine 레퍼런스 교체용
from database import Base, get_db
from main import app

# SQLite in-memory 엔진
engine_test = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,   # 단일 커넥션 재사용 (in-memory DB 유지)
)

@event.listens_for(engine_test, "connect")
def _enable_fk(dbapi_conn, _):
    # SQLite ForeignKey 제약 활성화
    dbapi_conn.execute("PRAGMA foreign_keys=ON")

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

# database.py / main.py 의 engine을 테스트 엔진으로 교체
database.engine = engine_test
app_main.engine = engine_test

# 세션 전체에서 테이블 한 번만 생성
Base.metadata.create_all(bind=engine_test)


# 픽스처

@pytest.fixture(autouse=True)
def reset_tables():
    # 각 테스트 전후 테이블 초기화 (데이터 격리)
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)
    yield
    # teardown: 다음 테스트를 위한 정리 (선택적)


@pytest.fixture(scope="function")
def client():
    """PostgreSQL 없이 동작하는 FastAPI TestClient"""
    def override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers(client):
    """
    테스트용 유저 생성 + 로그인 → Authorization 헤더 반환

    사용 예:
        def test_something(client, auth_headers):
            resp = client.get("/children/", headers=auth_headers)
    """
    client.post("/auth/register", json={
        "email":    "testuser@example.com",
        "password": "TestPassword123!",
        "nickname": "테스트유저",
    })
    login_resp = client.post("/auth/login", json={
        "email":    "testuser@example.com",
        "password": "TestPassword123!",
    })
    assert login_resp.status_code == 200, f"로그인 실패: {login_resp.text}"
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def sample_child(client, auth_headers) -> dict:
    # 테스트용 아이 생성
    resp = client.post("/children/", json={
        "name":       "김테스트",
        "birth_date": "2023-01-15",
        "gender":     "male",        # ← "male" | "female" 만 허용
        "allergies":  [],
        "conditions": [],
    }, headers=auth_headers)
    assert resp.status_code == 201, f"아이 생성 실패: {resp.text}"
    return resp.json()
