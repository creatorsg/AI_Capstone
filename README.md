# AI_Capstone — 초보 부모를 위한 육아 RAG 챗봇

한성대학교 AI 캡스톤 프로젝트 — 0\~5세 자녀를 둔 초보 부모가 아이의 증상·발달·예방접종·복지정책·병원 정보를 손쉽게 확인할 수 있는 **RAG(Retrieval-Augmented Generation) 기반 챗봇**입니다.

---

## 시스템 개요

```
사용자 질문
    │
    ▼
[의도 분석 (LLM)]  ──────────────────────────────────────────────
    │  intent / topic / risk_level / needs_clarification      │
    ▼                                                         │
[쿼리 재작성 (LLM)]                                              │
    │  아이 프로필 반영, 벡터 검색에 최적화된 문장                      │
    ▼                                                         │
[벡터 검색 (ChromaDB)]                                          │
    │  knowledge 컬렉션 또는 facility 컬렉션 라우팅                 │
    ▼                                                         │
[Reranking]  ── category / topic / age_group / curated 가중치   │
    ▼                                                         │
[답변 생성 (LLM)]  ◄────────────────────────────────────────────┘
    │  인텐트별 프롬프트 템플릿 + 안전 경고 prefix
    ▼
최종 답변 (Streamlit UI)
```

**주요 특징**
- 아이 프로필(이름·생년월일·성별·알레르기·기저질환) 및 최근 기록(수면·식사·발열)을 컨텍스트로 주입
- `medical_basic`, `development`, `vaccination`, `policy`, `hospital_locator`, `daily_parenting` 6가지 인텐트 기반 라우팅
- 경련·호흡 곤란 등 위험 키워드 감지 시 즉시 응급 안내 prefix 추가
- 질문·답변·참고 문서·디버그 정보 모두 UI에서 확인 가능

---

## 기술 스택

| 구분 | 사용 기술 |
|------|-----------|
| LLM | OpenAI GPT (ChatOpenAI) |
| 임베딩 | OpenAI Embeddings |
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
python app/ingest.py

# 챗봇 실행
streamlit run app/main.py
```

### macOS / Linux

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python app/ingest.py
streamlit run app/main.py
```

### 환경 변수 (.env)

프로젝트 루트에 `.env` 파일을 생성하고 아래 키를 입력합니다.

```
OPENAI_API_KEY=sk-...
```

---

## 폴더 구조

```
AI_Capstone/
├── app/                        # 서비스 소스코드
│   ├── main.py                 # Streamlit UI 진입점
│   ├── rag.py                  # RAG 파이프라인 핵심 로직
│   ├── ingest.py               # 데이터 → ChromaDB 적재 파이프라인
│   ├── prompts.py              # 인텐트별 LLM 프롬프트 템플릿
│   ├── vector_config.py        # 벡터 DB 경로·컬렉션명 설정
│   └── curated_docs.py         # 최소한의 curated knowledge 샘플
│
├── data/                       # 원본 데이터 및 전처리 스크립트
│   ├── README_DATA.md          # 데이터 상세 설명
│   ├── data1_cleaned_pediatrics_hospitals.json
│   ├── data2_geocoded_night_hospitals.json
│   ├── data3_vaccine_final_knowledge_base.json
│   ├── data4_geocoded_national_vaccine_hospitals_final.json
│   ├── data5_welfare_childcare_kb.json
│   ├── data6_geocoded_childcare_facilities_final.json
│   ├── data7_childcare_auto_kb.json
│   └── data1~7.py              # 각 데이터 수집·전처리 스크립트
│
├── eval/                       # RAG 평가 및 하이퍼파라미터 튜닝
│   ├── README.md               # 평가 시스템 상세 설명
│   ├── evaluate.py             # 배치 평가 (LLM-as-Judge 포함)
│   ├── tune.py                 # 하이퍼파라미터 그리드 탐색
│   ├── test_questions.json     # 테스트 질문 셋
│   └── results/                # 평가·튜닝 결과 JSON 및 뷰어
│
├── chroma_db/                  # 벡터화된 데이터 (ingest.py 실행 후 생성)
├── requirements.txt
├── .env                        # API 키 (git 제외)
└── README.md
```

---

## 코드 설명

### `app/main.py` — Streamlit UI

- 사이드바에서 아이 프로필(이름·생년월일·성별·알레르기·기저질환)과 최근 기록(수면·식사·발열) 입력
- 채팅 인터페이스로 질문 전송, 답변·참고 문서·디버그 정보 표시
- 대화 초기화 버튼으로 세션 히스토리 리셋

### `app/rag.py` — RAG 파이프라인

| 함수 | 역할 |
|------|------|
| `analyze_query()` | 질문의 intent·topic·risk_level·needs_clarification 분류 |
| `rewrite_query()` | 아이 프로필과 분석 결과를 반영해 벡터 검색용 쿼리 재작성 |
| `get_retriever()` | intent에 따라 knowledge 또는 facility 컬렉션으로 라우팅 |
| `simple_rerank()` | category·topic·age_group·curated 가중치 기반 문서 재순위화 |
| `apply_safety_prefix()` | high risk 판정 시 응급 안내 문구 prefix 추가 |
| `answer_question()` | 위 단계를 조합한 최종 답변 생성 함수 |

### `app/ingest.py` — 데이터 적재 파이프라인

1. `data/` 폴더의 JSON 파일 7종 로딩
2. 큐레이션 문서 로딩 (`curated_docs.py`)
3. knowledge 문서 청킹 (chunk_size=800, overlap=120)
4. 메타데이터 정규화 (카테고리·토픽·연령대·위도·경도 등)
5. MD5 해시 기반 중복 제거
6. ChromaDB `knowledge` / `facility` 두 컬렉션에 upsert
7. 임베딩 모델·청킹 파라미터를 기록한 `manifest.json` 저장

### `app/prompts.py` — LLM 프롬프트 템플릿

- **QUERY_ANALYZER_PROMPT**: 질문을 intent·topic·risk_level·needs_clarification JSON으로 분류
- **QUERY_REWRITE_PROMPT**: 벡터 검색에 최적화된 단일 검색 문장으로 변환
- **인텐트별 답변 프롬프트 6종**: `medical_basic` / `development` / `vaccination` / `policy` / `hospital_locator` / `daily_parenting`

### `app/vector_config.py` — 벡터 DB 설정

- ChromaDB 저장 경로(`chroma_db/`), 컬렉션명(`knowledge`, `facility`), 임베딩 모델명, manifest 경로 등 중앙 관리

### `app/curated_docs.py` — Curated Knowledge

- 자동 수집 데이터를 보완하는 최소한의 직접 작성 지식 샘플

---

## 데이터 설명

7종의 JSON 파일이 두 가지 용도로 분류됩니다.

| 분류 | 파일 | 출처 |
|------|------|------|
| **지식 (RAG 답변용)** | data3 — 예방접종 상세 지식 | 질병관리청 |
| | data5 — 복지서비스 요약 | 한국사회보장정보원 |
| | data7 — 육아상식 월령별 성장 | 아이사랑포털 (크롤링) |
| **시설 (병원 찾기용)** | data1 — 소아청소년과 병원 | 건강보험심사평가원 |
| | data2 — 야간·휴일 소아과 | 건강보험심사평가원 |
| | data4 — 예방접종 지정 의료기관 | 질병관리청 |
| | data6 — 아이돌봄 제공기관 | 성평등가족부 |

> 데이터 수집·전처리 상세 내용은 [data/README_DATA.md](data/README_DATA.md) 참고

---

## 평가 및 튜닝

```bash
cd eval

# 배치 평가 (LLM-as-Judge 포함)
python evaluate.py

# LLM Judge 없이 빠르게
python evaluate.py --no-judge

# 하이퍼파라미터 그리드 탐색
python tune.py

# 결과 시각화
# results/viewer.html 을 브라우저에서 열기
```

**측정 메트릭**

| 메트릭 | 방식 |
|--------|------|
| `intent_accuracy` / `risk_level_accuracy` | rule-based |
| `keyword_coverage` / `safety_compliance` | rule-based |
| `context_relevance` / `answer_faithfulness` / `answer_relevance` / `completeness` | LLM Judge (1~5점) |

> 평가 시스템 상세 내용은 [eval/README.md](eval/README.md) 참고

---

## 주의 사항

- 이 챗봇은 **일반 정보 제공 목적**이며 의학적 진단을 대체하지 않습니다.
- 경련, 호흡 곤란, 의식 저하 등 위험 증상이 있을 경우 즉시 119 또는 응급실을 이용하세요.
- OpenAI API 사용에 따른 비용이 발생할 수 있습니다.
- `.env` 파일과 `chroma_db/` 폴더는 `.gitignore`에 포함되어 있습니다.
