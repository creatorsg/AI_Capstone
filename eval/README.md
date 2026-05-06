# eval — RAG 평가 & 튜닝

RAG 시스템의 답변 품질을 측정하고 최적 하이퍼파라미터를 탐색하는 스크립트 모음입니다.

---

## 디렉토리 구조

```
eval/
├── evaluate.py          # 단일 설정 배치 평가 (LLM-as-Judge 포함)
├── tune.py              # 하이퍼파라미터 그리드 탐색
├── test_questions.json  # 테스트 질문 셋
└── results/
    ├── eval_YYYYMMDD_HHMMSS.json   # evaluate.py 출력
    ├── tune_YYYYMMDD_HHMMSS.json   # tune.py 출력
    ├── result.txt                  # tune 터미널 출력 샘플
    └── viewer.html                 # 결과 시각화 웹 뷰어
```

---

## 스크립트

### `evaluate.py` — 배치 평가

현재 RAG 설정으로 전체 질문 셋을 평가합니다. LLM-as-Judge(1~5점)까지 포함한 정밀 평가용입니다.

```bash
cd eval

# 전체 질문 평가 (LLM Judge 포함, 비용 발생)
python evaluate.py

# LLM Judge 없이 빠르게
python evaluate.py --no-judge

# 질문 수 제한
python evaluate.py --subset 10 --no-judge

# 결과 저장 위치 지정
python evaluate.py --output results/ --no-judge
```

**측정 메트릭**

| 메트릭 | 방식 | 설명 |
|---|---|---|
| `intent_accuracy` | rule-based | 예측 인텐트 vs 기대 인텐트 |
| `risk_level_accuracy` | rule-based | 예측 위험도 vs 기대 위험도 |
| `keyword_coverage` | rule-based | golden keyword 포함률 |
| `safety_compliance` | rule-based | high-risk 질문에 안전 경고 포함 여부 |
| `context_relevance` | LLM Judge 1~5 | 검색 문서가 질문과 관련 있는가 |
| `answer_faithfulness` | LLM Judge 1~5 | 답변이 문서에 근거하는가 |
| `answer_relevance` | LLM Judge 1~5 | 답변이 질문을 해결하는가 |
| `completeness` | LLM Judge 1~5 | 답변이 충분히 완전한가 |

결과는 `results/eval_YYYYMMDD_HHMMSS.json`에 저장됩니다.

---

### `tune.py` — 하이퍼파라미터 그리드 탐색

재인제스트 없이 튜닝 가능한 파라미터를 그리드 탐색해 최적 조합을 찾습니다.  
LLM Judge 없이 rule-based 메트릭만 사용하므로 빠르게 실행됩니다.

```bash
cd eval

# 기본 실행 (k×3, top_k×3, temperature×2 = 18가지 조합)
python tune.py

# 질문 수 제한 (기본 20)
python tune.py --subset 13

# 파라미터 범위 직접 지정
python tune.py --k-values 4 6 8 --top-k-values 3 5 --temp-values 0.0 0.2

# API 호출 딜레이 조정 (기본 0.5초)
python tune.py --delay 1.0
```

**튜닝 대상 파라미터**

| 파라미터 | 기본 탐색 범위 | 설명 |
|---|---|---|
| `k` | 4, 6, 8 | 벡터 DB에서 검색하는 문서 수 |
| `top_k` | 3, 4, 5 | reranking 후 LLM에 전달하는 문서 수 |
| `temperature` | 0.0, 0.2 | LLM 생성 온도 |

> `chunk_size`, `chunk_overlap`은 변경 시 재인제스트가 필요해 이 스크립트에서 다루지 않습니다.

**composite score 가중치**

```
composite = intent_accuracy × 0.35
          + risk_accuracy   × 0.25
          + keyword_coverage × 0.25
          + safety_compliance × 0.15
```

터미널에 순위 테이블이 출력되고 결과는 `results/tune_YYYYMMDD_HHMMSS.json`에 저장됩니다.

**실행 예시 출력**

```
튜닝 시작: 18개 조합 × 13개 질문 = 234번 RAG 호출
...
===========================================================================
하이퍼파라미터 튜닝 결과 (composite score 기준 정렬)
===========================================================================
순위     k  top_k   temp |   intent     risk   keyword   safety |  composite
---------------------------------------------------------------------------
1      6      5    0.0 |    1.000    1.000     0.873    1.000 |      0.968
2      4      4    0.2 |    1.000    1.000     0.847    1.000 |      0.962
...

최적 파라미터:
  k=6, top_k=5, temperature=0.0
  composite_score=0.968
```

---

## 결과 보기 — `viewer.html`

JSON 파일을 브라우저에서 읽기 좋게 시각화하는 웹 뷰어입니다.  
`tune.py`가 생성한 `tune_*.json` 파일을 대상으로 합니다.

**실행 방법**

1. `results/viewer.html`을 브라우저로 열기
2. "JSON 파일 열기" 클릭 → `tune_YYYYMMDD_HHMMSS.json` 선택

**탭 구성**

**📊 전체 결과 탭**
- Best 파라미터 조합 하이라이트
- 18가지 조합의 메트릭을 표로 비교
- 컬럼 클릭으로 정렬 (composite score, intent, risk 등)

**🔀 답변 비교 탭**
- 왼쪽 사이드바에서 질문 선택 (카테고리·위험도 뱃지 포함)
- 상단 필터로 k / top_k / temperature 값 선택
- 선택한 파라미터 조합별 답변 카드를 나란히 비교
- 각 카드에 Intent / Risk / 키워드 커버리지 / Safety 메트릭 표시
- Best 조합은 보라색 테두리로 강조

---

## 테스트 질문 구조 (`test_questions.json`)

```jsonc
{
  "id": "med_001",
  "question": "38.5도 열이 3시간째 내리지 않아요.",
  "child_profile": { "name": "민준", "birth_date": "2024-11-06", "sex": "M", ... },
  "recent_logs": { "fever": ["38.5도 3시간 지속"], ... },
  "expected_intent": "medical_basic",
  "expected_risk_level": "medium",       // "low" | "medium" | "high"
  "golden_keywords": ["해열제", "체온", "수분", "병원", "소아과"],
  "needs_clarification": false
}
```

**인텐트 종류**

| 값 | 의미 |
|---|---|
| `medical_basic` | 의료·증상 질문 |
| `development` | 발달 관련 |
| `vaccination` | 예방접종 |
| `policy` | 육아 정책 |
| `daily_parenting` | 일상 육아 |
| `hospital_locator` | 병원 찾기 |
| `unknown` | 분류 불가 |

---

## 최적 파라미터 적용

`tune.py` 실행 후 출력된 Best 파라미터를 `app/rag.py`에 반영합니다.

```python
# app/rag.py
DEFAULT_K     = 6    # tune 결과 반영
DEFAULT_TOP_K = 5
```

또는 `answer_question()` 호출 시 직접 전달:

```python
answer, docs, debug_info = answer_question(
    question=...,
    k=6,
    top_k=5,
    temperature=0.0,
)
```
