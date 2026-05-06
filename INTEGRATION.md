# 팀원 브랜치 통합 가이드

> 담당: 인선 (Backend & Infrastructure)  
> 최종 수정: 2026-05-06

---

## 팀 브랜치 현황

| 팀원 | 브랜치 | 담당 영역 | 통합 상태 |
|------|--------|-----------|-----------|
| 인선 | `inseon` | Backend API + 인프라 | 완료 - 기준 브랜치 |
| juhyeong | `juhyeong` | RAG (ChromaDB 기반 문서 검색) | 완료 - services/rag/ 에 통합 완료 |
| jaehwi | `jaehwi` | 정적 데이터 8종 JSON 생성 | 완료 - data1~data8 모두 data/ 에 배치 완료 |
| byeongchan | `byeongchan` | React Native 프론트엔드 | 진행중 - Config.ts IP 하드코딩 -> 환경변수화 필요 |

---

## 1. jaehwi 브랜치 통합 (정적 데이터)

### 필요한 파일 목록

jaehwi 브랜치의 `data/` 디렉터리에서 아래 파일들을 `fount-project/data/` 에 복사합니다.

```
data/
├── data1_cleaned_pediatrics_hospitals.json     # 소아청소년과 병원 목록
├── data2_geocoded_night_hospitals.json         # 야간 소아과 병원
├── data3_disease_symptoms_kb.json              # 질병-증상 지식베이스 (챗봇용)
├── data4_geocoded_national_vaccine_hospitals_final.json  # 예방접종 병원
├── data5_welfare_childcare_kb.json             # 복지서비스 지식베이스
├── data6_geocoded_childcare_facilities_final.json       # 아이돌봄센터
└── data7_vaccine_schedule_kb.json              # 예방접종 스케줄 지식베이스
```

### 통합 절차

```bash
# 1. jaehwi 브랜치에서 data 파일 확인
git checkout jaehwi
ls data/

# 2. inseon 브랜치로 돌아와 파일 복사
git checkout inseon
cp ../jaehwi-checkout/data/*.json data/

# 3. 서버 재시작 없이 자동 인식 확인
curl http://localhost:8000/welfare/status
curl http://localhost:8000/hospitals/static/status
```

### 자동 인식 원리
`welfare.py`와 `hospitals.py`는 `@lru_cache`로 lazy-loading합니다.  
→ 파일만 배치하면 **다음 요청 시 자동으로 로드**, 서버 재시작 불필요.

### 확인 체크리스트
- [ ] `GET /welfare/status` → `"source": "file"`, count > 0
- [ ] `GET /hospitals/static/status` → 4개 카테고리 모두 `"loaded": true`
- [ ] `GET /hospitals/static/nearby?lat=37.5665&lon=126.9780` → 결과 반환

---

## 2. juhyeong 브랜치 통합 (RAG 서비스)

### 현재 stub 구조

`services/rag_service.py` 가 인터페이스를 정의해 두었습니다.  
juhyeong이 완성한 코드를 이 파일에 채우면 됩니다.

```python
# services/rag_service.py 현재 stub
async def search_rag(query: str, child_context: dict | None) -> str:
    """
    TODO: juhyeong ChromaDB 연동 후 구현
    현재는 빈 문자열 반환 (AI가 자체 지식으로 답변)
    """
    return ""
```

### juhyeong이 구현해야 하는 인터페이스

```python
# services/rag_service.py 최종 형태
async def search_rag(query: str, child_context: dict | None = None) -> str:
    """
    Parameters
    ----------
    query : str
        사용자 질문 (예: "38.5도 열이 나요, 어떻게 해야 하나요?")
    child_context : dict | None
        {
          "name": "김민준",
          "birth_date": "2023-01-15",
          "gender": "남",
          "allergies": ["땅콩"],
          "conditions": [],
          "blood_type": "A",
          "medical_notes": "..."
        }

    Returns
    -------
    str
        ChromaDB에서 검색한 관련 문서 내용 (AI 프롬프트에 삽입됨)
        검색 결과 없으면 빈 문자열 "" 반환
    """
    # juhyeong 구현 영역
    ...
```

### RAG 통합 절차

```bash
# 1. juhyeong 브랜치의 RAG 관련 파일 확인
git checkout juhyeong
ls services/

# 2. rag_service.py 구현체 가져오기
git checkout inseon
git checkout juhyeong -- services/rag_service.py

# 3. ChromaDB 의존성 추가 (juhyeong 확인 후)
# requirements.txt 에 추가:
# chromadb>=0.4.0

# 4. 챗봇 테스트
curl -X POST http://localhost:8000/chat/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"child_id": 1, "message": "열이 38.5도예요"}'
```

### 확인 체크리스트
- [ ] `services/rag_service.py` 구현 완료
- [ ] `requirements.txt` chromadb 추가
- [ ] 챗봇 응답에 RAG 문서 내용이 반영되는지 확인
- [ ] RAG 검색 실패 시 graceful fallback 동작 확인 (빈 문자열 → AI 자체 답변)

---

## 3. 최종 통합 시 merge 순서 권장

```
main (또는 develop)
  └── inseon (기준)
        ├── jaehwi 데이터 파일 복사 (git checkout jaehwi -- data/)
        └── juhyeong RAG 구현 병합 (git checkout juhyeong -- services/rag_service.py)
```

> **주의**: 충돌이 날 수 있는 파일
> - `requirements.txt` — 각 브랜치에서 패키지를 추가했을 수 있음 → 수동 병합
> - `services/rag_service.py` — 현재 stub이므로 juhyeong 버전으로 덮어쓰기

---

## 4. 환경변수 최종 체크리스트

서버 배포 전 반드시 설정:

```bash
# 필수
MY_APP_DATABASE_URL=postgresql://...
JWT_SECRET_KEY=$(openssl rand -hex 32)   # 절대 기본값 사용 금지!
AI_PROVIDER=claude                        # 또는 gemini
ANTHROPIC_API_KEY=sk-ant-...

# 병원 검색 (Kakao API)
KAKAO_REST_API_KEY=...

# CORS (프론트엔드 도메인)
ALLOWED_ORIGINS=https://your-frontend.com
```

---

## 5. Alembic 마이그레이션 실행 (DB 처음 세팅 시)

```bash
pip install alembic
alembic upgrade head

# 이후 모델 변경 시
alembic revision --autogenerate -m "변경 내용 설명"
alembic upgrade head
```

---

## 6. AWS 배포 가이드 (EC2 + ECR + GitHub Actions)

### 아키텍처 구성

```
GitHub inseon 브랜치 push
    └── GitHub Actions CI/CD (.github/workflows/deploy.yml)
          ├── pytest 자동 실행
          ├── Docker 이미지 빌드 → ECR 푸시
          └── EC2 SSH 접속 → docker-compose.prod.yml 재시작
                └── EC2 인스턴스
                      ├── nginx (80/443) ← SSL: Let's Encrypt
                      ├── FastAPI (8000, 내부)
                      └── RDS PostgreSQL (외부 연결)
```

### 6-1. AWS 사전 세팅

```bash
# 1. ECR 레포지토리 생성
aws ecr create-repository --repository-name kids-chatbot-api --region ap-northeast-2

# 2. EC2 인스턴스 생성 (권장: t3.medium, Ubuntu 22.04)
#    - 보안그룹: 80, 443, 22(SSH) 인바운드 허용
#    - IAM Role: AmazonEC2ContainerRegistryReadOnly 정책 부여

# 3. EC2에 Docker 설치
sudo apt update && sudo apt install -y docker.io docker-compose
sudo usermod -aG docker ubuntu

# 4. RDS PostgreSQL 생성 (또는 EC2 내 로컬 PostgreSQL 사용)
#    - 엔진: PostgreSQL 15
#    - 보안그룹: EC2 보안그룹에서만 5432 접근 허용
```

### 6-2. GitHub Secrets 설정

GitHub 레포 → Settings → Secrets and variables → Actions → **New repository secret**

| Secret 이름 | 값 | 설명 |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | AKIA... | IAM 사용자 Access Key |
| `AWS_SECRET_ACCESS_KEY` | ... | IAM 사용자 Secret Key |
| `AWS_REGION` | `ap-northeast-2` | 서울 리전 |
| `ECR_REPOSITORY` | `kids-chatbot-api` | ECR 레포 이름 |
| `EC2_HOST` | `13.xxx.xxx.xxx` | EC2 퍼블릭 IP |
| `EC2_USERNAME` | `ubuntu` | EC2 SSH 사용자명 |
| `EC2_SSH_KEY` | (PEM 파일 전체 내용) | EC2 접속 키 |
| `ENV_PROD_FILE` | (.env.prod 파일 전체 내용) | 운영 환경변수 |

### 6-3. nginx 도메인 설정

`nginx/nginx.conf` 의 `your-domain.com` 을 실제 도메인으로 변경:

```bash
# 예시: sed 로 일괄 치환
sed -i 's/your-domain.com/api.yourdomain.com/g' nginx/nginx.conf
```

### 6-4. SSL 인증서 최초 발급 (EC2에서 직접 실행)

```bash
cd ~/app
# HTTP만 열어서 도전 수신 가능하도록 nginx 먼저 실행
docker-compose -f docker-compose.prod.yml up -d nginx

# Certbot 인증서 발급
docker-compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d api.yourdomain.com \
  --email your-email@example.com \
  --agree-tos --no-eff-email

# 전체 서비스 재시작
docker-compose -f docker-compose.prod.yml up -d
```

### 6-5. 배포 확인 체크리스트

- [ ] `https://api.yourdomain.com/` → `{"status": "FastAPI is Running!"}`
- [ ] `https://api.yourdomain.com/db-check` → `{"db_status": "Connected!"}`
- [ ] `https://api.yourdomain.com/docs` → Swagger UI 접근
- [ ] `https://api.yourdomain.com/hospitals/static/status` → data1~data8 모두 `exists: true`
- [ ] GitHub Actions → 최신 워크플로우 성공 확인
- [ ] inseon 브랜치 push 시 자동 배포 트리거 확인

### 6-6. byeongchan 프론트엔드 연동 시

`src/constants/Config.ts` 의 `API_BASE_URL` 을 배포된 URL로 변경 필요:

```typescript
// 변경 전 (로컬 개발용)
export const API_BASE_URL = 'http://192.168.123.109:8000';

// 변경 후 (운영)
export const API_BASE_URL = 'https://api.yourdomain.com';
```
