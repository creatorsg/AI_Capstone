import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# .env 파일을 읽어옵니다.
load_dotenv()

# 시스템 환경변수와 섞이지 않도록 고유한 이름을 사용합니다.
# 만약 .env를 못 읽을 경우를 대비해 직접 주소를 fallback으로 넣었습니다.
SQLALCHEMY_DATABASE_URL = os.getenv(
    "MY_APP_DATABASE_URL", 
    "postgresql://myuser:yourpassword_here@localhost:5432/kids_app"
)

# DB 엔진 생성
# SQLite(테스트/개발)는 pool_size/max_overflow를 지원하지 않으므로 분기합니다.
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )

# 세션 및 베이스 클래스 설정
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# DB 세션 의존성 주입 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()