# ──────────────────────────────────────────────────────────────────────────────
# Dockerfile - FastAPI 백엔드 컨테이너 (개발용)
#
# 빌드: docker build -t kids-chatbot-api .
# 개발: docker-compose up
# 프로덕션: docker-compose -f docker-compose.prod.yml up
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# 시스템 패키지 (psycopg2 native 드라이버 필요 시 libpq-dev 추가)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 먼저 복사 (캐시 최적화: 코드 변경 시 pip install 재실행 방지)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 개발: --reload 로 코드 변경 실시간 반영
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
