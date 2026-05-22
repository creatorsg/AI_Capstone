# 육아 RAG 챗봇 — 초보 부모를 위한 AI 육아 도우미

한성대학교 AI 캡스톤 프로젝트  
0~5세 자녀를 둔 초보 부모가 아이의 **증상·발달·예방접종·복지정책·병원·약국** 정보를 손쉽게 확인할 수 있는 RAG(Retrieval-Augmented Generation) 기반 챗봇입니다.

---

## 빠른 시작

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경 변수 설정
echo "OPENAI_API_KEY=sk-..." > .env

# 3. 벡터 DB 구축 (최초 1회)
cd app && python ingest.py

# 4-A. 웹 데모 실행 (권장)
python api.py          # http://localhost:8000

# 4-B. Streamlit UI 실행
streamlit run main.py  # http://localhost:8501
```

---

## 시스템 아키텍처

```
사용자 질문
    │
    ▼
[전처리 (preprocess, LLM 1회)]
    │  intent / topic / risk_level / rewritten_query 를 한 번에 산출
    │  (분류 + 검색용 쿼리 재작성 통합 — 아이 프로필 반영)
    ▼
[벡터 검색 (ChromaDB)]
    │  hospital_locator → facility 컬렉션
    │  그 외            → knowledge 컬렉션
    │  (LLM·임베딩·벡터스토어 인스턴스는 캐싱되어 재사용)
    ▼
[Reranking]
    │  category / topic / age_group / curated 가중치 적용
    ▼
[답변 생성 (generate, LLM 1회)]
    │  인텐트별 전용 프롬프트 템플릿 (max_tokens 캡, 간결 지시)
    │  high-risk 질문 → 응급 안내 prefix 자동 추가
    ▼
최종 답변
```

> **파이프라인 = LLM 2회 직렬 호출** (전처리 1 + 생성 1). 초기 설계는 분석·재작성·생성의 3회 호출이었으나 latency 최적화로 2회로 줄였습니다. 자세한 내용은 [성능 최적화](#성능-최적화-latency) 참고.

**주요 특징**

- 아이 프로필(이름·생년월일·성별·알레르기·기저질환)과 최근 기록(수면·식사·발열)을 컨텍스트로 주입해 맞춤형 답변 생성
- 채팅 히스토리(최근 3턴)를 프롬프트에 반영해 맥락 있는 다중 턴 대화 지원
- 분류와 검색 쿼리 재작성을 단일 전처리 호출로 통합해 LLM 직렬 호출을 3→2회로 단축
- 6가지 인텐트(`medical_basic` / `development` / `vaccination` / `policy` / `hospital_locator` / `daily_parenting`)별 전용 답변 템플릿 (그 외는 `unknown`으로 분류 후 범용 템플릿)
- 경련·호흡 곤란 등 위험 키워드 감지 시 응급 안내 prefix 자동 추가 (intent 분류와 분리되어 항상 동작)
- 인제스트 파라미터를 `ingest_manifest.json`으로 추적, 임베딩 모델 불일치 시 즉시 오류 발생
- `answer_question()`이 단계별 `timings`(preprocess / retrieval / rerank / generate / total)를 `debug_info`에 기록

---

## 기술 스택

| 구분 | 사용 기술 |
|------|-----------|
| LLM | OpenAI GPT-5.4-mini |
| 임베딩 | OpenAI `text-embedding-3-large` (3072차원) |
| 벡터 DB | ChromaDB |
| RAG 프레임워크 | LangChain |
| 웹 API 서버 | FastAPI + Uvicorn |
| Streamlit UI | Streamlit |
| 데이터 수집 | 공공데이터포털 API, BeautifulSoup 웹 크롤링 |
| 지오코딩 | Kakao Developers API |

> 분류·생성 단계에 사용할 모델은 환경 변수 `CLASSIFIER_MODEL` / `GENERATOR_MODEL`로 단계별 독립 지정할 수 있습니다(미지정 시 기본 `gpt-5.4-mini`).

---

## 성능 최적화 (Latency)

응답 latency를 줄이되 답변 품질(안전성·정확도·관련성)은 유지하는 것을 목표로 5단계 실험을 진행해, **평균 응답 시간을 5,622ms → 4,104ms (−27.0%)**로 단축했습니다. 측정은 58문항 테스트셋을 `--repeat 3`(n=174)으로 반복하고 p50/p95/p99까지 추적했습니다.

### 최종 성과

| 지표 | Baseline | 최종 | Δ |
|------|----------|------|---|
| total avg | 5,622ms | 4,104ms | **−27.0%** |
| total p50 | 5,406ms | 3,903ms | −27.8% |
| total p95 | 7,778ms | 5,643ms | −27.4% |
| total p99 | 11,145ms | 8,546ms | −23.3% |
| LLM 호출 수 / 질의 | 3 | 2 | −1 |

단계별로는 retrieval −67.6%(510→165ms, 인스턴스 캐싱), preprocess −35.3%(1,795→1,162ms, 호출 통합), generate −16.3%(3,316→2,777ms, 출력 캡)의 효과가 있었습니다. 안전성(`safety_compliance` 1.000 고정)과 답변 품질 메트릭은 측정 노이즈 범위 내에서 유지되었습니다.

### 채택된 실험

| ID | 변경 | 누적 Δ | 핵심 효과 |
|----|------|--------|-----------|
| E2 | LLM·임베딩·벡터스토어 인스턴스 캐싱(`lru_cache`) | −4.7% | retrieval −68% (Chroma 재초기화 제거) |
| E4 | `max_tokens` 캡 + "6문장 이내" 지시 | −15.2% | generate −16% (decode 단축) |
| E5 | analyze+rewrite를 단일 `preprocess` 호출로 통합 | −26.4% | LLM 호출 3→2회 |
| E8 | preprocess 출력 다이어트 (18단어 제한) | −27.0% | preprocess p50 −12% |

### 핵심 발견

가장 큰 동인은 **LLM 직렬 호출 수 감소(3→2)**와 **벡터스토어 인스턴스 캐싱**이었습니다. 반면 모델 교체(M1 `gpt-5.4-nano`, M2 `gpt-5-nano`, M4 `gpt-5-mini`)는 모두 **기각**되었는데, nano tier는 추론은 빠를지 몰라도 API tail latency가 커서(p99가 16~20초까지 튐) 평균 latency가 오히려 악화되었습니다. 즉 **이 환경의 병목은 모델 선택이 아니라 아키텍처(호출 수)**였습니다.

### latency 측정

```bash
cd eval

# 단계별 latency 프로파일 (58문항 × 3회 = n=174)
python latency_profile.py --repeat 3 --tag mytest

# 빠른 확인 (10문항)
python latency_profile.py --subset 10 --repeat 3
```

> 상세한 실험 설계·코드 변경안은 [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md), 결과 요약은 [RESULTS_SUMMARY.md](RESULTS_SUMMARY.md) 참고.

---

## 실행 방법

### 환경 변수 (`.env`)

프로젝트 루트에 `.env` 파일을 생성합니다.

```
OPENAI_API_KEY=sk-...
```

### 가상환경 설정

**macOS / Linux**
```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows**
```powershell
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1   # 오류 시: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements.txt
```

### 벡터 DB 구축 (최초 1회)

```bash
cd app
python ingest.py
```

5단계 진행 상황이 터미널에 출력되며, 완료 후 `chroma_db/`가 생성됩니다.

### 웹 데모 서버 (FastAPI)

```bash
cd app
python api.py
# → http://localhost:8000
```

브라우저에서 채팅 UI, 아이 프로필 입력, 답변 분석 정보(intent·위험도·참고 문서)를 확인할 수 있습니다.

### Streamlit UI

```bash
cd app
streamlit run main.py
# → http://localhost:8501
```

---

## 폴더 구조

```
AI_Capstone/
├── app/                        # 서비스 소스코드
│   ├── api.py                  # FastAPI 웹 데모 서버
│   ├── main.py                 # Streamlit 채팅 UI 진입점
│   ├── rag.py                  # RAG 파이프라인 핵심 로직
│   ├── ingest.py               # 데이터 → ChromaDB 적재 파이프라인
│   ├── prompts.py              # 인텐트별 LLM 프롬프트 템플릿
│   ├── vector_config.py        # 벡터 DB 경로·컬렉션명·임베딩 모델 설정
│   ├── curated_docs.py         # 직접 작성한 curated knowledge 샘플
│   └── static/
│       └── index.html          # 웹 데모 프론트엔드 (단일 파일 SPA)
│
├── data/                       # 원본 데이터 및 전처리 스크립트
│   ├── README_DATA.md
│   ├── data1_cleaned_pediatrics_hospitals.json
│   ├── data2_geocoded_night_hospitals.json
│   ├── data3_vaccine_final_knowledge_base.json
│   ├── data4_geocoded_national_vaccine_hospitals_final.json
│   ├── data5_welfare_childcare_kb.json
│   ├── data6_geocoded_childcare_facilities_final.json
│   ├── data7_childcare_auto_kb.json
│   ├── data8_national_pharmacies_full.json
│   └── data1~8.py              # 각 데이터 수집·전처리 스크립트
│
├── eval/                       # RAG 평가 및 하이퍼파라미터 튜닝
│   ├── evaluate.py             # 배치 평가 (LLM-as-Judge 포함)
│   ├── latency_profile.py      # 단계별 latency 프로파일러 (p50/p95/p99)
│   ├── tune.py                 # 하이퍼파라미터 그리드 탐색
│   ├── test_questions.json     # 테스트 질문 셋 (58개, 8개 인텐트)
│   └── results/                # 평가·튜닝·latency 결과 JSON 및 뷰어
│
├── chroma_db/                  # 벡터화된 데이터 (ingest.py 실행 후 생성)
│   └── ingest_manifest.json    # 인제스트 시 사용한 모델·파라미터 기록
├── EXPERIMENT_PLAN.md          # latency 최적화 실험 계획서 (Phase 0~4)
├── RESULTS_SUMMARY.md          # 실험 결과 요약 (−27% latency)
├── requirements.txt
├── .env                        # API 키 (git 제외)
└── README.md
```

---

## 코드 설명

### `app/api.py` — FastAPI 웹 데모 서버

`POST /chat` 엔드포인트가 `answer_question()`을 호출하고, `GET /`에서 채팅 UI HTML을 서빙합니다.

**요청 스펙:**

```json
{
  "question": "아이가 38.5도 열이 나요",
  "child_profile": { "name": "민준", "birth_date": "2023-09-01", "sex": "남아", "allergies": [] },
  "chat_history": [{ "role": "user", "content": "..." }, { "role": "assistant", "content": "..." }]
}
```

**응답 스펙:**

```json
{
  "answer": "...",
  "debug_info": {
    "intent": "medical_basic", "topic": "fever", "risk_level": "medium", "rewritten_query": "...",
    "preprocess_model": "gpt-5.4-mini", "generator_model": "gpt-5.4-mini",
    "timings": { "preprocess_ms": 1162, "retrieval_ms": 165, "generate_ms": 2777, "total_ms": 4104 }
  },
  "retrieved_docs": [{ "content": "...", "metadata": { "category": "...", "source": "..." } }]
}
```

### `app/rag.py` — RAG 파이프라인

| 함수 | 역할 |
|------|------|
| `preprocess_query()` | **(현행)** 분류와 검색 쿼리 재작성을 1회 호출로 통합 → intent·topic·risk_level·rewritten_query JSON. JSON 파싱 실패 시 안전한 fallback 반환 |
| `get_retriever()` | `hospital_locator`는 facility 컬렉션, 나머지는 knowledge 컬렉션으로 라우팅 |
| `simple_rerank()` | category·topic·age_group·curated 가중치 기반 문서 재순위화 |
| `apply_safety_prefix()` | high risk 판정 시 응급 안내 문구 prefix 추가 (intent 분류와 분리) |
| `answer_question()` | 전 단계를 통합한 최종 답변 생성. 단계별 `timings` 기록. `chat_history`, `k`, `top_k`, `temperature` 파라미터화 |
| `analyze_query()` / `rewrite_query()` | *(레거시)* 분리형 분석·재작성 호출. 롤백용으로 보존 — `USE_UNIFIED_PREPROCESS=False`일 때 사용 |

- `get_llm()` / `get_embeddings()` / `get_vectorstore()`는 `@lru_cache`로 인스턴스를 재사용합니다(프로세스 내 재초기화 비용 제거).
- `USE_UNIFIED_PREPROCESS`(기본 `True`)로 현행/레거시 전처리 경로를 전환합니다.
- 분류·생성 모델은 `CLASSIFIER_MODEL` / `GENERATOR_MODEL` 환경 변수로 단계별 지정 가능합니다.
- 기동 시 `_check_embedding_model()`이 `ingest_manifest.json`과 현재 코드의 임베딩 모델을 비교해 불일치 시 즉시 오류를 발생시킵니다.

### `app/ingest.py` — 데이터 적재 파이프라인

```
[1/5] JSON 파일 로딩
[2/5] 큐레이션 문서 로딩
[3/5] knowledge 문서 청킹  (chunk_size=800, overlap=120)
[4/5] 메타데이터 처리 및 중복 제거
[5/5] ChromaDB 업로드      (batch_size=500)
```

완료 후 `chroma_db/ingest_manifest.json`에 모델·파라미터·컬렉션 통계가 기록됩니다.

> **임베딩 모델 변경 시:** `app/vector_config.py`의 `EMBEDDING_MODEL`을 수정 → `chroma_db/` 삭제 → `ingest.py` 재실행  
> **청킹 파라미터 변경 시:** `ingest.py`의 `CHUNK_SIZE` / `CHUNK_OVERLAP` 수정 → `ingest.py` 재실행

### `app/prompts.py` — LLM 프롬프트 템플릿

| 프롬프트 | 역할 |
|----------|------|
| `QUERY_PREPROCESS_PROMPT` | **(현행)** 질문 → intent·topic·risk_level·rewritten_query JSON (분류+재작성 통합) |
| `QUERY_ANALYZER_PROMPT` / `QUERY_REWRITE_PROMPT` | *(레거시)* 분리형 분석·재작성 프롬프트. 롤백용으로 보존 |
| `ANSWER_PROMPT_MEDICAL` | 증상 해석 / 집에서 할 수 있는 것 / 즉시 병원 가야 할 신호 |
| `ANSWER_PROMPT_DEVELOPMENT` | 정상 발달 범위 / 관찰 포인트 / 놀이 활동 제안 |
| `ANSWER_PROMPT_VACCINATION` | 접종 정보 / 전후 주의사항 |
| `ANSWER_PROMPT_POLICY` | 지원 대상·금액·신청 방법·문의처 |
| `ANSWER_PROMPT_HOSPITAL` | 시설 목록·운영시간·방문 전 확인 권고 |
| `ANSWER_PROMPT_DAILY` | 상황 이해 / 실용적 팁 / 전문가 상담 기준 |
| `ANSWER_PROMPT_DEFAULT` | 위 인텐트에 해당하지 않는 경우의 범용 템플릿 |

`get_answer_prompt(intent)` 함수가 인텐트를 받아 해당 템플릿을 반환합니다. 모든 답변 템플릿에는 "핵심만 6문장 이내, 불릿 최대 5개" 간결화 지시가 포함되어 generate 단계 decode 시간을 줄입니다.

---

## 데이터 설명

8종의 JSON 파일이 두 가지 용도로 분류됩니다.

| 분류 | 파일 | 내용 | 출처 |
|------|------|------|------|
| **지식 (RAG 답변용)** | data3 | 예방접종 상세 지식 | 질병관리청 |
| | data5 | 복지서비스 요약 | 한국사회보장정보원 |
| | data7 | 육아상식·월령별 성장 | 아이사랑포털 (크롤링) |
| **시설 (위치 안내용)** | data1 | 소아청소년과 병원 | 건강보험심사평가원 |
| | data2 | 야간·휴일 소아과 | 건강보험심사평가원 |
| | data4 | 예방접종 지정 의료기관 | 질병관리청 |
| | data6 | 아이돌봄 제공기관 | 성평등가족부 |
| | data8 | 전국 약국 (25,217개소) | 응급의료정보센터 |

> 데이터 수집·전처리 상세 내용은 [data/README_DATA.md](data/README_DATA.md) 참고

---

## 평가 및 튜닝

### 배치 평가 (`evaluate.py`)

```bash
cd eval

# 전체 58개 질문 평가 (LLM Judge 포함)
python evaluate.py

# LLM Judge 없이 빠르게
python evaluate.py --no-judge

# 특정 인텐트만
python evaluate.py --intent hospital_locator --no-judge

# 앞에서 N개만
python evaluate.py --subset 20 --no-judge

# 특정 질문 ID만
python evaluate.py --ids pha_001 pha_002 --no-judge
```

**테스트 질문 구성 (총 58개)**

| 인텐트 | 수 | 주요 케이스 |
|--------|----|------------|
| medical_basic | 10 | low/medium/high risk, 발열·경련·호흡·설사 |
| development | 8 | 언어·운동 지연, 발달 퇴행(high-risk), 사회성 |
| vaccination | 8 | 접종 일정, 이상반응, 지연 접종 |
| policy | 8 | 부모급여, 바우처, 아이돌봄, 육아휴직 |
| daily_parenting | 8 | 수면, 식사, 떼쓰기, 분리불안 |
| hospital_locator | 11 | 소아과·야간진료·응급실(5) + 약국(6) |
| unknown | 5 | 짧고 맥락 없는 질문 (`unknown` 분류 → 범용 템플릿) |

**측정 메트릭**

| 메트릭 | 방식 | 설명 |
|--------|------|------|
| `intent_accuracy` | rule-based | 예측 인텐트 vs 기대 인텐트 |
| `risk_level_accuracy` | rule-based | 예측 risk vs 기대 risk |
| `keyword_coverage` | rule-based | golden_keywords 포함률 |
| `safety_compliance` | rule-based | high-risk 질문에 응급 경고 포함 여부 |
| `context_relevance` | LLM Judge (1~5점) | 검색 문서가 질문에 얼마나 관련있는가 |
| `answer_faithfulness` | LLM Judge (1~5점) | 답변이 문서에 근거하는가 |
| `answer_relevance` | LLM Judge (1~5점) | 답변이 질문을 실제로 해결하는가 |
| `completeness` | LLM Judge (1~5점) | 답변이 충분히 완전한가 |

### 하이퍼파라미터 튜닝 (`tune.py`)

재인제스트 없이 튜닝 가능한 파라미터를 그리드 탐색합니다.

```bash
cd eval

# 기본 실행 (18조합 × 20질문)
python tune.py

# 빠른 탐색
python tune.py --subset 10 --k-values 4 6 --top-k-values 3 4 --temp-values 0.0
```

| 파라미터 | 기본 탐색 범위 | 설명 |
|----------|---------------|------|
| `k` | 4 / 6 / 8 | 벡터 DB에서 가져오는 문서 수 |
| `top_k` | 3 / 4 / 5 | reranking 후 LLM에 전달하는 문서 수 |
| `temperature` | 0.0 / 0.2 | LLM 생성 온도 |

최적 파라미터는 `app/rag.py`의 `DEFAULT_K` / `DEFAULT_TOP_K` 상수에 반영하거나 `answer_question()` 호출 시 직접 전달합니다.

### latency 프로파일링 (`latency_profile.py`)

품질 메트릭 없이 단계별 응답 시간만 빠르게 측정합니다. 동일 질문 셋을 여러 번 반복(`--repeat`)해 median을 안정화하고 avg/p50/p95/p99를 집계합니다.

```bash
cd eval

# 전체 58문항 × 3회 (n=174)
python latency_profile.py --repeat 3 --tag baseline

# 빠른 확인 (10문항)
python latency_profile.py --subset 10 --repeat 3
```

| 옵션 | 설명 |
|------|------|
| `--repeat` | 동일 질문 셋 반복 횟수 (기본 3) |
| `--subset` | 앞에서 N개 질문만 측정 |
| `--tag` | 결과 파일 prefix (예: `baseline`, `E2`) |
| `--intent` | 특정 인텐트만 측정 |

결과는 `eval/results/latency_<tag>_<timestamp>.json`에 저장됩니다.

---

## 주의 사항

- 이 챗봇은 **일반 정보 제공 목적**이며 의학적 진단을 대체하지 않습니다.
- 경련, 호흡 곤란, 의식 저하 등 위험 증상이 있을 경우 **즉시 119 또는 응급실**을 이용하세요.
- OpenAI API 사용에 따른 비용이 발생할 수 있습니다.
- `.env` 파일과 `chroma_db/` 폴더는 `.gitignore`에 포함되어 있습니다.
