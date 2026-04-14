# 팀원 브랜치 통합 가이드

> 담당: 인선 (Backend & Infrastructure)  
> 최종 수정: 2026-04-11

---

## 팀 브랜치 현황

| 팀원 | 브랜치 | 담당 영역 | 통합 상태 |
|------|--------|-----------|-----------|
| 인선 | `inseon` | Backend API + 인프라 | ✅ 기준 브랜치 |
| juhyeong | `juhyeong` | RAG (ChromaDB 기반 문서 검색) | ⏳ stub 연결 완료, 코드 완성 대기 |
| jaehwi | `jaehwi` | 정적 데이터 7종 JSON 생성 | ⏳ JSON 파일 수동 배치 필요 |

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
