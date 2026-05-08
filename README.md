# AI_Capstone — 초보 부모를 위한 육아 RAG 챗봇

한성대학교 AI 캡스톤 프로젝트 — 0\~5세 자녀를 둔 초보 부모가 아이의 증상·발달·예방접종·복지정책·병원·약국 정보를 손쉽게 확인할 수 있는 **RAG(Retrieval-Augmented Generation) 기반 챗봇**입니다.

---

## 시스템 개요

```
사용자 질문
    │
    ▼
[의도 분석 (LLM)]  ─────────────────────────────────────────────────────
    │  intent / topic / risk_level / needs_clarification               │
    ▼                                                                  │
[쿼리 재작성 (LLM)]                                                       │
    │  아이 프로필 + 채팅 히스토리 반영, 벡터 검색 최적화 문장               │
    ▼                                                                  │
[벡터 검색 (ChromaDB)]                                                   │
    │  knowledge 컬렉션 또는 facility 컬렉션 인텐트 기반 라우팅            │
    ▼                                                                  │
[Reranking]  ── category / topic / age_group / curated 가중치            │
    ▼                                                                  │
[답변 생성 (LLM)]  ◄──────────────────────────────────────────────────── ┘
    │  인텐트별 프롬프트 템플릿 + 안전 경고 prefix
    ▼
최종 답변 (Streamlit 채팅 UI)
```

**주요 특징**
- 아이 프로필(이름·생년월일·성별·알레르기·기저질환) 및 최근 기록(수면·식사·발열)을 컨텍스트로 주입
- 채팅 히스토리(최근 3턴)를 프롬프트에 반영해 맥락 있는 대화 지원
- `medical_basic` / `development` / `vaccination` / `policy` / `hospital_locator` / `daily_parenting` 6가지 인텐트별 전용 답변 템플릿
- 경련·호흡 곤란 등 위험 키워드 감지 시 즉시 응급 안내 prefix 추가
- 임베딩 모델과 인제스트 하이퍼파라미터를 `ingest_manifest.json`으로 추적, 기동 시 불일치 자동 감지

---

## 기술 스택

| 구분 | 사용 기술 |
|------|-----------|
| LLM | OpenAI GPT-5.4-mini (`ChatOpenAI`) |
| 임베딩 | OpenAI `text-embedding-3-large` (3072차원) |
| 벡터 DB | ChromaDB |
| RAG 프레임워크 | LangChain |
| UI | Streamlit |
| 데이터 수집 | 공공데이터포털 API, BeautifulSoup 웹 크롤링 |
| 지오코딩 | Kakao Developers API |

---

## 실행 환경 및 실행법

### Windows

```powershell
# Python 3.10 가상환경 생성
py -3.10 -m venv .venv

# 가상환경 활성화
.venv\Scripts\Activate.ps1
# 실행 오류 시: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 필요 라이브러리 설치
pip install -r requirements.txt

# 환경 변수 설정 (.env 파일 생성)
# OPENAI_API_KEY=sk-...

# 벡터 DB 생성 (최초 1회 또는 데이터 변경 시)
cd app
py ingest.py

# 챗봇 실행 (app/ 디렉토리에서)
streamlit run main.py
```

### macOS / Linux

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd app
python ingest.py
streamlit run main.py
```

### 환경 변수 (`.env`)

프로젝트 루트에 `.env` 파일을 생성합니다.

```
OPENAI_API_KEY=sk-...
```

---

## 폴더 구조

```
AI_Capstone/
├── app/                        # 서비스 소스코드
│   ├── main.py                 # Streamlit 채팅 UI 진입점
│   ├── rag.py                  # RAG 파이프라인 핵심 로직
│   ├── ingest.py               # 데이터 → ChromaDB 적재 파이프라인
│   ├── prompts.py              # 인텐트별 LLM 프롬프트 템플릿
│   ├── vector_config.py        # 벡터 DB 경로·컬렉션명·임베딩 모델 설정
│   └── curated_docs.py         # 직접 작성한 curated knowledge 샘플
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
│   ├── tune.py                 # 하이퍼파라미터 그리드 탐색
│   ├── test_questions.json     # 테스트 질문 셋 (58개, 8개 인텐트)
│   └── results/                # 평가·튜닝 결과 JSON 및 뷰어
│
├── chroma_db/                  # 벡터화된 데이터 (ingest.py 실행 후 생성)
│   └── ingest_manifest.json    # 인제스트 시 사용한 모델·파라미터 기록
├── requirements.txt
├── .env                        # API 키 (git 제외)
└── README.md
```

---

## 코드 설명

### `app/main.py` — Streamlit 채팅 UI

- 사이드바에서 아이 프로필(이름·생년월일·성별·알레르기·기저질환)과 최근 기록(수면·식사·발열) 입력
- `st.chat_input` + `st.session_state.messages`로 다중 턴 채팅 히스토리 관리
- 답변·참고 문서·디버그 정보를 각 메시지 아래 expander로 확인 가능
- 사이드바의 **대화 초기화** 버튼으로 세션 리셋

### `app/rag.py` — RAG 파이프라인

| 함수 | 역할 |
|------|------|
| `analyze_query()` | 질문의 intent·topic·risk_level·needs_clarification 분류 |
| `rewrite_query()` | 아이 프로필과 분석 결과를 반영해 벡터 검색용 쿼리 재작성 |
| `get_retriever()` | `hospital_locator`는 facility 컬렉션, 나머지는 knowledge 컬렉션으로 라우팅 |
| `simple_rerank()` | category·topic·age_group·curated 가중치 기반 문서 재순위화 |
| `apply_safety_prefix()` | high risk 판정 시 응급 안내 문구 prefix 추가 |
| `answer_question()` | 전 단계를 통합한 최종 답변 생성. `chat_history`, `k`, `top_k`, `temperature` 파라미터화 |

기동 시 `_check_embedding_model()`이 `ingest_manifest.json`과 현재 코드의 임베딩 모델을 비교해 불일치 시 즉시 오류를 발생시킵니다.

### `app/ingest.py` — 데이터 적재 파이프라인

실행하면 5단계 진행 상황이 터미널에 출력됩니다.

```
[1/5] JSON 파일 로딩...      ← 파일별 로드 결과 출력
[2/5] 큐레이션 문서 로딩...
[3/5] knowledge 문서 청킹...
[4/5] 메타데이터 처리 및 중복 제거...
[5/5] ChromaDB 업로드...     ← tqdm 진행 바
```

완료 후 `chroma_db/ingest_manifest.json`에 아래 정보가 저장됩니다.

```json
{
  "embedding_model": "text-embedding-3-large",
  "ingested_at": "2026-05-06T15:30:00",
  "hyperparameters": {
    "chunk_size": 800,
    "chunk_overlap": 120,
    "batch_size": 500
  },
  "collections": {
    "parenting_knowledge": { "doc_count": 1200 },
    "parenting_facility":  { "doc_count": 3100 }
  }
}
```

> **임베딩 모델 변경 시**: `app/vector_config.py`의 `EMBEDDING_MODEL` 상수를 수정하고 `chroma_db/`를 삭제한 후 `ingest.py`를 재실행하세요.

> **청킹 파라미터 변경 시**: `ingest.py`의 `CHUNK_SIZE` / `CHUNK_OVERLAP` 상수를 수정하고 동일하게 재실행하세요.

### `app/prompts.py` — LLM 프롬프트 템플릿

| 프롬프트 | 역할 |
|----------|------|
| `QUERY_ANALYZER_PROMPT` | 질문 → intent·topic·risk_level·needs_clarification JSON |
| `QUERY_REWRITE_PROMPT` | 벡터 검색에 최적화된 단일 검색 문장 생성 |
| `ANSWER_PROMPT_MEDICAL` | 증상 해석 / 집에서 할 수 있는 것 / 즉시 병원 가야 할 신호 |
| `ANSWER_PROMPT_DEVELOPMENT` | 정상 발달 범위 / 관찰 포인트 / 놀이 활동 제안 |
| `ANSWER_PROMPT_VACCINATION` | 접종 정보 / 전후 주의사항 |
| `ANSWER_PROMPT_POLICY` | 지원 대상·금액·신청 방법·문의처 |
| `ANSWER_PROMPT_HOSPITAL` | 시설 목록·운영시간·방문 전 확인 권고 |
| `ANSWER_PROMPT_DAILY` | 상황 이해 / 실용적 팁 / 전문가 상담 기준 |
| `ANSWER_PROMPT_DEFAULT` | 위 인텐트에 해당하지 않는 경우의 범용 템플릿 |

`get_answer_prompt(intent)` 함수가 인텐트를 받아 해당 템플릿을 반환합니다.

### `app/vector_config.py` — 중앙 설정

임베딩 모델명·컬렉션명·경로·manifest 경로를 한 곳에서 관리합니다. **모델 변경은 반드시 이 파일의 `EMBEDDING_MODEL`만 수정하세요.**

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

# LLM Judge 없이 빠르게 (rule-based 메트릭만)
python evaluate.py --no-judge

# 특정 인텐트만 평가
python evaluate.py --intent hospital_locator --no-judge

# 특정 질문 ID만 평가
python evaluate.py --ids pha_001 pha_002 pha_003 --no-judge

# 앞에서 N개만 평가
python evaluate.py --subset 20 --no-judge
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
| unknown | 5 | 짧고 맥락 없는 질문 (needs_clarification) |

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
| `k` | 4 / 6 / 8 | 벡터DB에서 가져오는 문서 수 |
| `top_k` | 3 / 4 / 5 | reranking 후 LLM에 전달하는 문서 수 |
| `temperature` | 0.0 / 0.2 | LLM 생성 온도 |

결과 JSON에는 조합별 집계 메트릭과 **질문별 전체 답변**이 모두 저장되어 직접 품질을 확인할 수 있습니다.

최적 파라미터는 `app/rag.py`의 `DEFAULT_K` / `DEFAULT_TOP_K` 상수에 반영하거나 `answer_question()` 호출 시 직접 전달합니다.

---

## 주의 사항

- 이 챗봇은 **일반 정보 제공 목적**이며 의학적 진단을 대체하지 않습니다.
- 경련, 호흡 곤란, 의식 저하 등 위험 증상이 있을 경우 즉시 119 또는 응급실을 이용하세요.
- OpenAI API 사용에 따른 비용이 발생할 수 있습니다.
- `.env` 파일과 `chroma_db/` 폴더는 `.gitignore`에 포함되어 있습니다.
