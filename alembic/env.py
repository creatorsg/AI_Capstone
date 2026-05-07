"""Alembic 마이그레이션 환경 설정 (.env 연동, 자동 감지)"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# .env 파일 로드
load_dotenv(PROJECT_ROOT / ".env")

# Alembic Config 객체
config = context.config

# 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DB URL 주입 (.env → alembic config)
db_url = os.getenv("MY_APP_DATABASE_URL")
if not db_url:
    raise ValueError(
        "MY_APP_DATABASE_URL 환경변수가 설정되지 않았습니다.\n"
        ".env 파일을 확인하세요."
    )
config.set_main_option("sqlalchemy.url", db_url)

# 모델 메타데이터 (자동 감지)
from database import Base          # noqa: E402
import models                      # noqa: E402, F401  ← 모든 모델 로드 트리거

target_metadata = Base.metadata


# Offline 마이그레이션 (DB 연결 없이 SQL 스크립트 생성)
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,          # 컬럼 타입 변경도 감지
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# Online 마이그레이션 (실제 DB에 직접 적용)
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
