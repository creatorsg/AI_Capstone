# 챗봇 Latency 최적화 실험 계획서

> 이 문서는 Claude Code(또는 다른 코딩 에이전트)가 자동 리팩터링·실험에 사용하도록 작성되었습니다.
> 각 실험은 **가설 / 변경 대상 파일 / 구체 변경안 / 실행 명령 / 수용 기준(Acceptance Criteria) / 롤백 방법**을 모두 포함합니다.
> 한 번에 하나의 실험만 적용하고, 매 실험마다 `eval/results/`에 결과 JSON을 남기세요.

---

## 0. 현재 시스템 요약 (Baseline)

### 0.1 워크플로우 (per query)

`app/rag.py :: answer_question()` 기준 — **LLM 호출 3회, 모두 직렬**:

```
[1] analyze_query        (LLM #1, gpt-5.4-mini, JSON 분류: intent/topic/risk/clarification)
       │
[2] normalize_risk_level (rule-based, 무시 가능)
       │
[3] rewrite_query        (LLM #2, gpt-5.4-mini, 벡터 검색용 질의 재작성)
       │
[4] retriever.invoke()   (OpenAI Embedding 1회 + Chroma local search)
       │
[5] simple_rerank        (rule-based, 무시 가능)
       │
[6] answer prompt LLM    (LLM #3, gpt-5.4-mini, 최종 답변)
```

### 0.2 현재 측정 인프라

| 항목 | 위치 | 상태 |
|------|------|------|
| 전체 latency | `eval/evaluate.py :: evaluate_one` (`t0`/`time.perf_counter`) | end-to-end만 측정 |
| 단계별 latency | 없음 | **추가 필요** |
| TTFT (Time To First Token) | 없음 | 비스트리밍이라 불가 |
| 품질 메트릭 | intent_accuracy / risk_level_accuracy / keyword_coverage / safety_compliance / LLM-judge(1~5) | OK |

### 0.3 사용 모델

- 메인 LLM: `gpt-5.4-mini` (분류·재작성·생성 모두 동일)
- Judge LLM: `gpt-5.4-mini`
- Embedding: `text-embedding-3-large` (3072 dim)

---

## 1. 목표 및 성공 기준

### 1.1 정량 목표

| 지표 | Baseline | Target |
|------|----------|--------|
| 평균 end-to-end latency | (측정 후 기재) | **−40% 이상** |
| p95 latency | (측정 후 기재) | **−40% 이상** |
| TTFT (스트리밍 후) | N/A | **< 1.0s** |

### 1.2 품질 가드레일 (반드시 유지)

기본 가드레일:
- `intent_accuracy` baseline 대비 **−2%p 이내**
- `safety_compliance_rate` baseline 대비 **유지 (1.0)** — high-risk 안전 경고 누락 금지
- `answer_relevance_avg` (LLM-judge) **−0.2점 이내**
- `keyword_coverage_avg` **−5%p 이내**

Phase 2.5(개인화) 추가 가드레일:
- `appropriate_specificity_score` baseline 대비 **저하 없음** — 단정·진단 표현 증가 금지
- `personalization_score` 개인화 변경 시 baseline 대비 **+0.5점 이상** (개선 목표 겸 가드)
- LLM 호출 횟수가 E5(2회) 대비 늘어나면 즉시 롤백

위 가드레일을 깨는 변경은 즉시 롤백합니다.

> **`intent_accuracy` 노이즈 플로어**: 4회 측정 결과 자연 변동폭은 ±3.4%p (범위 0.966~1.000).
> 단일 run에서 **0.95 이상이면 통과**로 간주하고, 미만이면 3회 추가 측정 후 median으로 재판정.
> `med_010` ("반응이 없어요. 불러도 눈을 안 떠요.")은 `medical_basic`→`unknown` 오분류가 반복되는
> **known-unstable 케이스**이며 가드레일 위반 판정에서 제외 가능.

### 1.3 측정 환경 표준화

- 동일 네트워크, 동일 OPENAI_API_KEY, 동일 시간대(가능한 한)
- evaluate.py `--delay 1.0` 유지(rate limit 영향 통제)
- 비교 실험 시 동일 질문 셋(`eval/test_questions.json`) 사용
- 각 실험은 **최소 3회 반복** 후 median 사용 (cold start, 네트워크 변동 흡수)

---

## 2. Phase 0 — 평가 인프라 강화 (반드시 먼저)

이 단계가 끝나기 전까지 어떤 최적화도 적용하지 않습니다. 측정 도구 없이 비교 불가능합니다.

### Step 0.1 — 단계별 latency 측정 hook 추가

**가설**: 어디서 latency가 발생하는지 분해하지 않으면 잘못된 곳을 최적화할 수 있다.

**변경 대상**: `app/rag.py`

**구체 변경안**:

1. `answer_question` 함수에서 각 단계 시간을 측정해 `debug_info`에 추가:

```python
import time
# ... 기존 import 유지

def answer_question(...):
    timings = {}
    t0 = time.perf_counter()

    analysis = analyze_query(question, model=model)
    timings["analyze_query_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    t = time.perf_counter()
    risk_level = normalize_risk_level(question, analysis)
    intent = analysis.get("intent", "unknown")
    rewritten_query = rewrite_query(question, child_profile, analysis, model=model)
    timings["rewrite_query_ms"] = round((time.perf_counter() - t) * 1000, 1)

    t = time.perf_counter()
    retriever = get_retriever(intent, k=k)
    docs = retriever.invoke(rewritten_query)
    timings["retrieval_ms"] = round((time.perf_counter() - t) * 1000, 1)

    t = time.perf_counter()
    # ... rerank + context build (생략)
    docs = simple_rerank(docs, intent=intent, topic=analysis.get("topic"),
                        age_group=age_group, weights=rerank_weights)
    top_docs = docs[:top_k]
    context = build_context(top_docs)
    timings["rerank_build_ms"] = round((time.perf_counter() - t) * 1000, 1)

    t = time.perf_counter()
    # ... LLM 호출
    response = llm.invoke(prompt)
    timings["generate_ms"] = round((time.perf_counter() - t) * 1000, 1)

    timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    debug_info["timings"] = timings
    # ...
    return answer, top_docs, debug_info
```

2. `eval/evaluate.py :: evaluate_one`에서 `debug_info["timings"]`를 결과에 포함:

```python
result["timings"] = debug_info.get("timings", {})
```

3. `aggregate()` 함수에 단계별 평균/백분위 계산 추가:

```python
def percentile(values, p):
    if not values: return None
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 1)

def aggregate(results):
    # ... 기존 코드 유지
    stage_keys = ["analyze_query_ms", "rewrite_query_ms", "retrieval_ms",
                  "rerank_build_ms", "generate_ms", "total_ms"]
    stage_stats = {}
    for k in stage_keys:
        vals = [r["timings"].get(k) for r in valid
                if r.get("timings", {}).get(k) is not None]
        if vals:
            stage_stats[k] = {
                "avg": round(sum(vals) / len(vals), 1),
                "p50": percentile(vals, 50),
                "p95": percentile(vals, 95),
                "p99": percentile(vals, 99),
            }
    overall["stage_stats"] = stage_stats
    return overall
```

**수용 기준**:
- `python evaluate.py --subset 5 --no-judge` 실행 시 결과 JSON에 단계별 ms와 p50/p95/p99가 포함된다.
- 기존 메트릭(intent_accuracy 등)이 그대로 동작한다.

---

### Step 0.2 — 독립 profiling 스크립트 추가

**변경 대상**: `eval/latency_profile.py` (신규 파일)

**목적**: 평가 메트릭 계산 없이 latency만 빠르게(여러 번) 측정.

**구체 변경안**: `eval/latency_profile.py` 신규 생성 (스켈레톤은 이 계획서와 함께 제공된 파일 참고).
- `--repeat N`: 같은 질문 셋을 N회 반복 (기본 3)
- `--subset M`: 질문 수 제한
- 출력: `eval/results/latency_<timestamp>.json`
- 표 형태로 단계별 평균/p50/p95 stdout 출력

**수용 기준**:
- `python eval/latency_profile.py --subset 10 --repeat 3` 가 동작한다.
- 결과 JSON에 단계별 통계 + 모델명 + 질문 ID별 raw 측정값이 모두 들어 있다.

---

### Step 0.3 — Baseline 측정 및 기록

```bash
cd eval
python evaluate.py --no-judge --delay 1.5    # 빠른 베이스라인
python evaluate.py --delay 1.5               # judge 포함 품질 베이스라인
python latency_profile.py --repeat 3         # latency 분포
```

결과 JSON 3개를 `eval/results/baseline/`로 이동하고 readme에 baseline 수치를 기록합니다.

**Phase 0 완료 조건**: 위 3개 결과 파일이 baseline 폴더에 존재하고, 다음 표가 채워진다.

| 단계 | 평균(ms) | p50(ms) | p95(ms) |
|------|---------|---------|---------|
| analyze_query | | | |
| rewrite_query | | | |
| retrieval | | | |
| rerank_build | | | |
| generate | | | |
| **total** | | | |

---

## 3. Phase 1 — Quick Wins (저비용·고효과)

각 실험은 **단독 적용 → 측정 → 결과 기록 → 유지/롤백** 순서로 진행합니다.

---

### E1. 스트리밍 응답 활성화 (TTFT 단축)

**가설**: 사용자 체감 latency는 첫 토큰까지의 시간(TTFT)에 좌우된다. 스트리밍하면 총 latency가 같아도 체감이 극적으로 개선된다.

**변경 대상**:
- `app/rag.py` — `answer_question`에서 generation 단계만 스트리밍 옵션 추가 (`stream: bool = False`)
- `app/api.py` — `/chat/stream` 엔드포인트(SSE 또는 chunked) 추가, 기존 `/chat`은 유지
- `app/static/index.html` — 스트리밍 응답 수신 로직 추가 (별도 PR로 분리 가능)

**구체 변경안 (rag.py)**:

```python
def answer_question(..., stream: bool = False):
    # ... 기존 단계
    llm = get_llm(model=model, temperature=temperature)
    answer_prompt = get_answer_prompt(intent)
    prompt = answer_prompt.format(...)

    if stream:
        def token_iter():
            first = True
            for chunk in llm.stream(prompt):
                yield chunk.content
                if first:
                    debug_info["timings"]["ttft_ms"] = round(
                        (time.perf_counter() - generate_start) * 1000, 1
                    )
                    first = False
        # 호출 측이 token_iter()를 소비하면서 헤더로 debug_info 따로 보낸다
        return token_iter(), top_docs, debug_info
    else:
        response = llm.invoke(prompt)
        # ... 기존
```

**FastAPI 측 (api.py)**: `StreamingResponse` 사용, `text/event-stream`.

**측정**: `eval/latency_profile.py`에 `--stream` 플래그 추가하여 TTFT 측정.

**수용 기준**:
- TTFT p50 < 1.0초
- 안전 prefix는 스트리밍 시작 직전에 합쳐서 보낸다(또는 첫 청크로 전송)
- 비스트리밍 경로 (`/chat`) 응답은 baseline과 동일하게 작동한다

**롤백**: stream=False 기본값 유지, 새 엔드포인트만 제거.

---

### E2. ChatOpenAI 인스턴스 재사용 + 연결 풀

**가설**: 매 호출마다 `ChatOpenAI(...)`를 새로 만들면 내부적으로 클라이언트 구성/세팅에 오버헤드가 누적될 수 있다.

**변경 대상**: `app/rag.py`

**구체 변경안**:

```python
from functools import lru_cache

@lru_cache(maxsize=8)
def get_llm(model: str = DEFAULT_MODEL, temperature: float = 0.0):
    return ChatOpenAI(model=model, temperature=temperature)

@lru_cache(maxsize=1)
def get_embeddings():
    return OpenAIEmbeddings(model=EMBEDDING_MODEL)

@lru_cache(maxsize=2)
def get_vectorstore(collection_name: str):
    _check_embedding_model()
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )
```

**수용 기준**:
- `evaluate.py --subset 5 --no-judge` 통과
- analyze/rewrite/generate 각 단계 latency가 baseline 대비 동일하거나 감소
- 품질 메트릭 동일

**롤백**: `@lru_cache` 데코레이터 제거.

---

### E3. 프롬프트 다이어트 (input token 감소 → prefill 시간 감소)

**가설**: `prompts.py`의 시스템 프롬프트가 length상 redundant한 부분이 있다. 의미를 유지하면서 토큰 수를 줄이면 prefill 단계가 빨라진다.

**변경 대상**: `app/prompts.py`

**구체 작업**:

1. `QUERY_ANALYZER_PROMPT` — 중복된 설명·예시 정리. 분류 라벨 정의는 한 줄씩으로 압축.
2. `ANSWER_PROMPT_*` 6개 템플릿 — 공통 규칙은 별도 상수로 빼서 중복 제거.
3. 체크리스트:
   - 한국어 "당신은 ... 챗봇입니다" 도입부 1줄로 단축
   - 같은 의미 반복 제거 ("절대 ~", "반드시 ~" 같은 강조 한 곳만)
   - 예시(few-shot)는 효과가 측정된 경우만 유지

**측정 도구**:

```bash
pip install tiktoken  # 이미 설치됨
python -c "import tiktoken; enc = tiktoken.get_encoding('o200k_base'); \
  print(len(enc.encode(open('app/prompts.py').read())))"
```

→ 변경 전후 토큰 수 비교. 목표: **−30% 이상**.

**수용 기준**:
- 단계별 latency 측정에서 `analyze_query_ms`, `generate_ms` 둘 다 감소
- intent_accuracy, keyword_coverage, judge 점수 모두 가드레일 내 유지

**롤백**: git stash / revert.

---

### E4. 출력 길이 제어 (`max_tokens`)

**가설**: 답변이 필요 이상으로 장황하면 decode 시간이 길어진다.

**변경 대상**: `app/rag.py`, `app/prompts.py`

**구체 변경안**:

1. `ANSWER_PROMPT_*` 끝에 "답변은 핵심만 6문장 이내, 불릿 최대 5개로 작성." 추가.
2. `get_llm()`에 `max_tokens` 옵션 추가, 답변 LLM은 `max_tokens=500`, 분석·재작성 LLM은 `max_tokens=200`로 캡.

```python
def get_llm(model=DEFAULT_MODEL, temperature=0.0, max_tokens: int | None = None):
    kwargs = {"model": model, "temperature": temperature}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)
```

호출부 수정:
- `analyze_query`: `max_tokens=150`
- `rewrite_query`: `max_tokens=80`
- 답변 생성 LLM: `max_tokens=500`

**수용 기준**:
- `generate_ms` 평균 감소
- `completeness` (judge) −0.3 이내, `keyword_coverage` −5%p 이내

**롤백**: max_tokens 제거.

---

## 4. Phase 2 — 워크플로우 구조 개선

여기부터 코드 구조가 바뀝니다. 각 실험 전후로 git commit을 남기세요.

---

### E5. analyze + rewrite 통합 (LLM 호출 3 → 2)

**가설**: 분류 결과(`intent`/`topic`)와 재작성 쿼리는 같은 입력으로 동시에 생성 가능. 별도 호출 2회는 낭비.

**변경 대상**: `app/rag.py`, `app/prompts.py`

**구체 변경안**:

1. `prompts.py`에 통합 프롬프트 추가:

```python
QUERY_PREPROCESS_PROMPT = ChatPromptTemplate.from_template("""
당신은 0~5세 자녀 부모 질문 분석기입니다. 아래 질문을 분석하여 JSON만 반환:

{{
  "intent": "development|daily_parenting|medical_basic|vaccination|policy|hospital_locator|unknown",
  "topic": "...",
  "risk_level": "low|medium|high",
  "needs_clarification": true/false,
  "rewritten_query": "벡터 검색용 한국어 1문장"
}}

분류 기준 (간략):
- development: 발달/언어/놀이/사회성
- daily_parenting: 수면/식사/생활습관
- medical_basic: 증상(열/기침/구토 등)
- vaccination: 예방접종
- policy: 복지/지원금/바우처
- hospital_locator: 병원/약국/위치

high risk: 경련, 호흡곤란, 의식저하, 축처짐, 반복구토, 탈수, 발달퇴행
rewritten_query 규칙: 한국어 1문장, 아이 연령 반영, 핵심 주제 명시.

질문: {question}
아이 정보: {child_context}
""")
```

2. `rag.py`에 `preprocess_query()` 함수 신설, 기존 `analyze_query`+`rewrite_query` 호출 한 곳에서 1회로 대체.
3. 기존 두 함수는 하위 호환을 위해 보존(or 삭제 후 테스트).

**수용 기준**:
- LLM 호출 횟수 3 → 2
- 단계별 latency: 합산 `analyze + rewrite` 대비 통합 단계가 **30% 이상 감소**
- intent_accuracy 가드레일 통과 (-2%p 이내)
- rewritten_query 품질이 비슷한지 정성 확인(10개 샘플 비교)

**롤백**: 함수 한 줄 토글 (`USE_UNIFIED_PREPROCESS = False`).

---

### E6. 쉬운 질의 라우팅 (Fast Path)

**가설**: 일부 질문(짧은 인사·재질문·고정 응답류, 또는 명백한 단일 카테고리 키워드 매치)은 LLM 분류 자체가 불필요. 규칙 기반으로 분기하면 LLM 1회까지 줄일 수 있다.

**변경 대상**: `app/rag.py`

**구체 변경안**:

1. `rule_based_intent(question)` 함수 추가 — 키워드 매칭으로 confident한 경우만 intent 반환, 아니면 None.

```python
RULE_INTENT_KEYWORDS = {
    "hospital_locator": ["소아과", "병원", "약국", "운영시간", "야간", "응급실"],
    "vaccination": ["예방접종", "백신", "접종 일정", "MMR", "BCG", "DTaP"],
    "policy": ["바우처", "지원금", "복지", "양육수당", "아동수당"],
}

def rule_based_intent(question: str) -> str | None:
    q = question.replace(" ", "")
    for intent, kws in RULE_INTENT_KEYWORDS.items():
        if any(kw.replace(" ", "") in q for kw in kws):
            return intent
    return None
```

2. `answer_question` 시작 시:
   - rule-based intent가 잡히면 분류 LLM 스킵, topic="general"·risk_level="low"로 가정(단, high_risk 키워드 별도 체크는 유지)
   - 쿼리 재작성도 짧은 질문(< 20자)이면 원본 그대로 사용

3. 짧은 질문(예: < 15자)이고 인텐트가 unknown이면 분류 LLM은 사용하되 rewrite는 스킵.

**수용 기준**:
- Fast path가 잡히는 질문에서 latency **−40% 이상**
- 전체 평균 latency도 감소
- intent_accuracy / safety_compliance 가드레일 통과

**롤백**: `USE_FAST_PATH = False` 플래그.

---

### E7. 시맨틱 캐시 (선택 사항)

**가설**: 반복되는 유사 질문은 임베딩 유사도 기반 캐시 hit이 가능.

**변경 대상**: `app/cache.py` (신규), `app/rag.py`

**구체 변경안**:
- `(query_embedding, answer, debug_info, timestamp)` 튜플을 메모리 LRU에 저장
- 새 질문 임베딩과 cosine similarity ≥ 0.95이면 cache hit
- 안전: high_risk 질문은 캐싱 금지

```python
# app/cache.py
import numpy as np
from collections import deque

class SemanticCache:
    def __init__(self, maxsize=100, threshold=0.95):
        self.maxsize = maxsize
        self.threshold = threshold
        self.entries = deque()  # list of (emb_np, answer, debug)

    def get(self, query_emb):
        if not self.entries: return None
        embs = np.array([e[0] for e in self.entries])
        q = query_emb / np.linalg.norm(query_emb)
        sims = embs @ q
        idx = int(np.argmax(sims))
        if sims[idx] >= self.threshold:
            return self.entries[idx][1], self.entries[idx][2]
        return None

    def put(self, query_emb, answer, debug):
        self.entries.append((query_emb, answer, debug))
        while len(self.entries) > self.maxsize:
            self.entries.popleft()
```

**수용 기준**: hit 시 latency < 100ms, miss 시 오버헤드 < 50ms.

**롤백**: 설정 플래그 토글.

---

## 4.5 Phase 2.5 — 개인화·관계 분석 (E5-extended)

> Phase 2의 E5(analyze+rewrite 통합)를 확장한다. **LLM 호출 수는 늘리지 않는다** —
> 동일 통합 preprocess 호출 1회에서 구조화된 신호까지 함께 뽑고, 그 신호를
> risk 보정 / rerank / 답변 프롬프트 enrichment 세 군데에서 활용한다.

### 배경 — 현재의 갭

`rag.py`는 `child_profile` / `recent_logs` / `chat_history`를 답변 프롬프트에 **raw text로 주입**만 한다.
정보가 활용될지 여부는 답변 LLM의 우연에 맡겨져 있고, 다음이 빠져 있다:

- 증상의 구조화된 추출 (지속시간·심각도·시간 패턴·동반 증상)
- 프로필 ↔ 증상 관계 추론 (알레르기·기저질환 일치, 연령 기준)
- 히스토리 시계열 패턴 (악화·안정·호전, 반복 질문)
- 결정론적 risk 보정 — 현재 `normalize_risk_level`은 키워드 매칭만 한다

### 안전 가드 (이 Phase 전체에 적용)

- 답변에서 **"진단 단정" 금지**: "X일 가능성이 매우 높습니다" / "Y입니다" 같은 단정 표현 금지.
- 모든 출력은 **"가능성 / 고려사항 / 전문가 상담 권유"** 톤으로 한정.
- 프로필 활용도가 올라가더라도 `apply_safety_prefix`·`HIGH_RISK_KEYWORDS` 로직 우회 금지.
- 신규 평가 지표 `appropriate_specificity_score`로 단정 표현 증가를 모니터링.

---

### E5.1 — 통합 preprocess에 구조화된 신호 추가

**가설**: 같은 LLM 호출 안에서 분류·재작성을 한다면, 거기에 신호 추출을 같이 얹어도 입력 토큰만 약간 늘 뿐 호출 수는 그대로다.

**전제**: Phase 2 의 E5(`QUERY_PREPROCESS_PROMPT`)가 먼저 적용되어 있어야 한다.

**변경 대상**: `app/prompts.py`, `app/rag.py`

**구체 변경안 — `app/prompts.py`**: E5 프롬프트를 V2로 확장.

```python
QUERY_PREPROCESS_PROMPT_V2 = ChatPromptTemplate.from_template("""
당신은 0~5세 자녀 부모 질문 분석기입니다. 아래 입력을 보고 JSON만 반환하세요.
설명 문장·코드블록·마크다운 절대 금지.

{{
  "intent": "development|daily_parenting|medical_basic|vaccination|policy|hospital_locator|unknown",
  "topic": "...",
  "risk_level": "low|medium|high",
  "needs_clarification": true/false,
  "rewritten_query": "벡터 검색용 한국어 1문장",

  "symptoms": [
    {{"name": "...", "severity": "...|null", "duration": "...|null",
      "trend": "악화|안정|호전|new|null", "time_pattern": "주간|야간|식후|null"}}
  ],
  "profile_relevance": {{
    "age_group_concern": "0-6m|6-12m|12-24m|24-36m|36-60m|null",
    "allergy_match": ["프로필 알레르기 중 현재 질문과 관련 있는 것"],
    "condition_match": ["프로필 기저질환 중 현재 질문과 관련 있는 것"],
    "notes_relevant": true/false
  }},
  "history_signal": {{
    "progression": "악화|안정|호전|new|unknown",
    "repeated_topic": true/false,
    "turns_on_same_topic": 0
  }}
}}

규칙:
- symptoms는 질문에서 명시적으로 언급된 것만. 추측 금지.
- allergy_match·condition_match는 아이 정보에 실제로 적힌 항목 중에서만 선택.
- high risk 키워드: 경련, 호흡곤란, 의식저하, 축처짐, 반복구토, 탈수, 발달퇴행.

질문: {question}
아이 정보: {child_context}
최근 기록: {recent_logs}
최근 대화: {chat_history}
""")
```

**구체 변경안 — `app/rag.py`**:

```python
def preprocess_query_v2(
    question: str,
    child_profile: dict | None,
    recent_logs: dict | None,
    chat_history: list[dict] | None,
    model: str = None,
) -> dict:
    llm = get_llm(model=model or CLASSIFIER_MODEL)
    prompt = QUERY_PREPROCESS_PROMPT_V2.format(
        question=question,
        child_context=format_child_context(child_profile),
        recent_logs=format_recent_logs(recent_logs),
        chat_history=format_chat_history(chat_history or []),
    )
    response = llm.invoke(prompt)
    try:
        parsed = json.loads(response.content.strip())
    except json.JSONDecodeError:
        parsed = {
            "intent": "unknown", "topic": "general",
            "risk_level": "low", "needs_clarification": False,
            "rewritten_query": question,
        }
    # 필수 키 보장 (fallback 안전망)
    parsed.setdefault("symptoms", [])
    parsed.setdefault("profile_relevance", {})
    parsed.setdefault("history_signal", {"progression": "unknown", "repeated_topic": False})
    return parsed
```

**수용 기준**:
- LLM 호출 횟수는 E5와 동일 (2회). 늘면 즉시 롤백.
- 신규 필드(`symptoms`/`profile_relevance`/`history_signal`)가 모두 채워진 비율 **≥ 90%** (10% fallback 허용).
- `intent_accuracy` 가드레일 통과.
- 단계별 latency: 통합 preprocess 단계가 E5 대비 **+30% 이내**.

**롤백**: `USE_V2_PREPROCESS = False` 플래그로 V1으로 회귀.

---

### E5.2 — 결정론적 risk 보정 로직

**가설**: LLM이 뽑은 `risk_level`을 그대로 쓰지 말고, 구조화된 신호로 **규칙 기반 조정**을 한 번 더 거치면 안전성·검증 가능성이 올라간다.

**변경 대상**: `app/rag.py`

**구체 변경안**:

```python
def apply_risk_modifiers(
    base_risk: str,
    parsed: dict,
    child_profile: dict | None,
) -> tuple[str, list[str]]:
    """parsed(preprocess 결과)와 프로필을 보고 base_risk를 룰 기반 보정."""
    risk_order = {"low": 0, "medium": 1, "high": 2}
    inv = {0: "low", 1: "medium", 2: "high"}
    current = risk_order.get(base_risk, 0)
    modifiers: list[str] = []

    age_months = (
        calculate_age_months(child_profile.get("birth_date"))
        if child_profile else None
    )
    symptoms = parsed.get("symptoms", []) or []
    symptom_names = [s.get("name", "") for s in symptoms]
    pr = parsed.get("profile_relevance", {}) or {}
    history = parsed.get("history_signal", {}) or {}

    # R1: 12개월 미만 + 발열류 → 최소 medium
    if age_months is not None and age_months < 12 and any("열" in n for n in symptom_names):
        if current < 1:
            current = 1
            modifiers.append("R1: age<12m + fever → medium")

    # R2: 기저질환 일치 + 관련 증상 → 한 단계 상향
    if pr.get("condition_match") and current < 2:
        current = min(2, current + 1)
        modifiers.append(f"R2: condition_match {pr['condition_match']} → bump")

    # R3: 알레르기 일치 + 의심 증상 → 한 단계 상향
    if pr.get("allergy_match") and any(
        any(kw in n for kw in ["구토", "발진", "두드러기", "호흡", "쌕쌕"])
        for n in symptom_names
    ):
        if current < 2:
            current = min(2, current + 1)
            modifiers.append("R3: allergy_match + suspicious symptom → bump")

    # R4: 히스토리 progression이 "악화" → 한 단계 상향
    if history.get("progression") == "악화" and current < 2:
        current = min(2, current + 1)
        modifiers.append("R4: progression=악화 → bump")

    return inv[current], modifiers


def normalize_risk_level_v2(question, parsed, child_profile):
    if detect_high_risk_keywords(question):
        return "high", ["high-risk keyword detected"]
    llm_risk = parsed.get("risk_level", "low")
    if llm_risk not in {"low", "medium", "high"}:
        llm_risk = "low"
    return apply_risk_modifiers(llm_risk, parsed, child_profile)
```

`answer_question` 안에서 호출을 `normalize_risk_level_v2(question, parsed, child_profile)`로 교체. 반환된 `modifiers`는 `debug_info["risk_modifiers"]`에 기록.

**수용 기준**:
- 기존 high-risk 케이스(`med_002` 경련 등) 모두 high 유지 → `safety_compliance_rate` = 1.0.
- 12개월 미만 발열 신규 케이스(E5.5)에서 risk_level ≥ medium.
- 알레르기/기저질환 의도 케이스에서 risk 상향 modifier가 `debug_info["risk_modifiers"]`에 기록됨.

**롤백**: `normalize_risk_level_v2` → `normalize_risk_level` 한 줄 교체.

---

### E5.3 — 개인화 reranker

**가설**: 현재 `simple_rerank`는 `category`·`topic`·`age_group`·`curated`만 본다. 증상·기저질환·알레르기 매칭 가중치를 추가하면 retrieval 품질이 올라간다.

**전제 확인**: `app/ingest.py`에서 ChromaDB 문서 메타데이터에 `symptoms`·`conditions`·`allergies` 키가 있는지 먼저 확인. 없으면 `page_content` 본문 substring 매칭으로 fallback (아래 코드는 fallback 버전).

**변경 대상**: `app/rag.py`

**구체 변경안**:

```python
RERANK_WEIGHTS_V2 = {
    "category_match":   3,
    "topic_match":      2,
    "age_group_match":  2,
    "curated_source":   1,
    "symptom_match":    3,   # NEW
    "condition_match":  3,   # NEW
    "allergy_match":    2,   # NEW
}

def personalized_rerank(docs, intent, topic, age_group, parsed, weights=None):
    w = weights or RERANK_WEIGHTS_V2
    symptom_names = [s.get("name", "") for s in parsed.get("symptoms", []) or []]
    pr = parsed.get("profile_relevance", {}) or {}
    cond_match = pr.get("condition_match", []) or []
    allergy_match = pr.get("allergy_match", []) or []

    rescored = []
    for doc in docs:
        score = 0
        meta = doc.metadata or {}
        body = doc.page_content or ""

        if meta.get("category") == intent:
            score += w["category_match"]
        if topic and meta.get("topic") == topic:
            score += w["topic_match"]
        if age_group and meta.get("age_group") == age_group:
            score += w["age_group_match"]
        if meta.get("source") == "curated":
            score += w["curated_source"]

        if any(s and s in body for s in symptom_names):
            score += w["symptom_match"]
        if any(c and c in body for c in cond_match):
            score += w["condition_match"]
        if any(a and a in body for a in allergy_match):
            score += w["allergy_match"]

        rescored.append((score, doc))

    rescored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in rescored]
```

`answer_question` 안에서 `simple_rerank(...)` → `personalized_rerank(..., parsed=parsed)`로 교체.

**수용 기준**:
- 알레르기/기저질환 의도 케이스(E5.5)에서 관련 문서가 top-3에 포함되는 비율 상승.
- `context_relevance` (judge) baseline 대비 같거나 상승.
- `intent_accuracy` 가드레일 통과.

**튜닝**: `eval/tune.py`의 weight grid에 신규 키 3개 추가하되, 차수 폭발을 막기 위해 각 키는 `{0, 2, 3}` 3단계만.

**롤백**: `simple_rerank`로 한 줄 복귀.

---

### E5.4 — 답변 프롬프트 enrichment (관련 신호 섹션)

**가설**: raw text로 프로필·로그·히스토리를 통째로 던지지 말고, preprocess에서 뽑은 **핵심 신호만 추려 답변 LLM에 전달**하면 (a) 입력 토큰이 줄고 (b) LLM이 중요한 정보를 놓치지 않는다. Latency와 품질 동시에 유리.

**변경 대상**: `app/rag.py`, `app/prompts.py`

**구체 변경안 — `app/rag.py`**:

```python
def format_signals_block(parsed, risk_modifiers, age_months):
    lines = ["[관련 신호]"]
    symptoms = parsed.get("symptoms", []) or []
    if symptoms:
        parts = []
        for s in symptoms:
            seg = s.get("name", "?")
            if s.get("duration"):
                seg += f" (지속 {s['duration']})"
            if s.get("trend") and s["trend"] not in {"null", None}:
                seg += f" / {s['trend']}"
            parts.append(seg)
        lines.append("- 증상: " + "; ".join(parts))

    pr = parsed.get("profile_relevance", {}) or {}
    if pr.get("condition_match"):
        lines.append("- 기저질환 연관: " + ", ".join(pr["condition_match"]))
    if pr.get("allergy_match"):
        lines.append("- 알레르기 연관: " + ", ".join(pr["allergy_match"]))
    if age_months is not None:
        lines.append(f"- 연령: {age_months}개월")

    hs = parsed.get("history_signal", {}) or {}
    if hs.get("progression") in {"악화", "안정", "호전"}:
        lines.append(f"- 경과 추세: {hs['progression']}")

    if risk_modifiers:
        lines.append("- Risk 보정 사유: " + "; ".join(risk_modifiers))

    return "\n".join(lines) if len(lines) > 1 else ""
```

**구체 변경안 — `app/prompts.py`**: 6개 인텐트별 답변 템플릿에 `{signals}` 슬롯 추가, 응답 규칙 보강.

```python
# 예: ANSWER_PROMPT_MEDICAL (다른 5개 인텐트도 동일하게 적용)
"""
... 기존 도입부 ...

[아이 정보]
{child_context}

[최근 기록]
{recent_logs}

[최근 대화]
{chat_history}

{signals}

[참고 문서]
{context}

[부모 질문]
{question}

응답 규칙(필수):
- 위 [관련 신호]의 항목을 답변에 명시적으로 반영.
- 진단 단정 금지: "~일 가능성이 있다" / "~확인이 필요하다" 톤 유지.
- 알레르기·기저질환이 신호에 있으면 그 점을 답변에서 짚어줄 것.
- 답변은 6문장 이내, 핵심만.
"""
```

`get_answer_prompt(intent).format(...)` 호출부에 `signals=format_signals_block(parsed, risk_modifiers, age_months)` 인자 추가.

**수용 기준**:
- `personalization_score` (E5.5 신규 judge 지표) baseline 대비 **+0.5점 이상**.
- `appropriate_specificity_score` baseline 대비 **저하 없음**.
- 답변 LLM 입력 토큰이 baseline 대비 같거나 감소 (raw 주입 → 신호 요약 교체 효과).
- `intent_accuracy` / `safety_compliance` 가드레일 통과.

**롤백**: `signals=""`로 주입하면 baseline 동작과 동일.

---

### E5.5 — 개인화 평가 지표 추가

**가설**: 현재 메트릭(intent_accuracy / keyword_coverage / 기존 judge 4종)으로는 "프로필을 실제로 활용했는가"를 측정 못 한다. 신규 지표 없이는 E5.1~E5.4의 효과를 증명할 수 없다.

**변경 대상**: `eval/evaluate.py`, `eval/test_questions.json`

**(a) Judge 프롬프트 확장**:

```python
JUDGE_PROMPT_V2 = """\
당신은 육아 챗봇 답변을 평가하는 심사자입니다. 각 기준을 1~5점으로 평가하고 JSON만 반환.

질문: {question}
아이 프로필 요약: {profile_brief}
참고 문서: {context}
챗봇 답변: {answer}

기준:
- context_relevance: 1~5
- answer_faithfulness: 1~5
- answer_relevance: 1~5
- completeness: 1~5
- personalization_score: 답변이 아이 프로필(연령·알레르기·기저질환·메모)을 실제로 활용했는가
    1=전혀 활용 안 함, 3=언급만, 5=구체적·관련성 높게 활용
- appropriate_specificity_score: 단정·진단 표현 없이 적절히 구체적인가
    1=무책임한 단정 다수, 3=중립이지만 모호, 5=가능성·고려사항 톤으로 구체적

{{"context_relevance": N, "answer_faithfulness": N, "answer_relevance": N,
  "completeness": N, "personalization_score": N, "appropriate_specificity_score": N}}
"""
```

`llm_judge()`에서 `profile_brief = format_child_context(child_profile)[:500]`을 전달.

**(b) `aggregate()`에 신규 평균 항목**:

```python
overall["personalization_avg"] = avg("personalization_score")
overall["appropriate_specificity_avg"] = avg("appropriate_specificity_score")
overall["profile_utilization_rate"] = round(
    sum(1 for r in valid if (r.get("personalization_score") or 0) >= 4)
    / len(valid), 3
)
```

**(c) `eval/test_questions.json`에 개인화 검증용 케이스 ≥ 5개 추가**:

```json
[
  {
    "id": "personalization_001_allergy_milk",
    "question": "아침에 우유 먹고 30분 뒤부터 구토하고 입가에 발진이 생겼어요. 어떻게 해야 하나요?",
    "child_profile": {"name": "민서", "birth_date": "2024-05-01", "sex": "F",
                      "allergies": ["우유", "땅콩"], "conditions": [], "notes": ""},
    "recent_logs": {"sleep": [], "food": ["아침 우유 200ml"], "fever": []},
    "expected_intent": "medical_basic",
    "expected_topic": "allergy",
    "expected_risk_level": "high",
    "golden_keywords": ["우유", "알레르기", "응급", "병원"],
    "notes": "알레르기 프로필 활용 + risk 상향 검증"
  },
  {
    "id": "personalization_002_asthma_cough",
    "question": "기침이 어제부터 심해지고 숨소리에 쌕쌕 소리가 나요.",
    "child_profile": {"name": "지호", "birth_date": "2022-08-10", "sex": "M",
                      "allergies": [], "conditions": ["천식"], "notes": "흡입기 사용 중"},
    "recent_logs": {"sleep": ["기침으로 자주 깸"], "food": [], "fever": []},
    "expected_intent": "medical_basic",
    "expected_topic": "respiratory",
    "expected_risk_level": "high",
    "golden_keywords": ["천식", "흡입기", "쌕쌕", "병원"],
    "notes": "기저질환(천식) 프로필 활용 검증"
  },
  {
    "id": "personalization_003_age_under12m_fever",
    "question": "열이 38.2도까지 올라갔어요.",
    "child_profile": {"name": "하준", "birth_date": "2025-09-15", "sex": "M",
                      "allergies": [], "conditions": [], "notes": ""},
    "recent_logs": {"sleep": [], "food": [], "fever": ["38.2도"]},
    "expected_intent": "medical_basic",
    "expected_topic": "fever",
    "expected_risk_level": "medium",
    "golden_keywords": ["개월", "진료", "소아과"],
    "notes": "12개월 미만 발열 → risk 상향(R1) 검증"
  }
]
```

위 3개 외에 알레르기·기저질환·연령 보정 케이스를 **합계 ≥ 7개**가 되도록 추가.

**수용 기준**:
- 신규 personalization 케이스 셋의 `personalization_score` 평균 **≥ 4.0**.
- 전체 셋의 `appropriate_specificity_avg` baseline 대비 저하 없음.
- 신규 12개월 미만 발열 케이스가 risk_level ≥ medium으로 평가됨.

**롤백**: 신규 케이스만 제거하면 됨 (기존 메트릭은 그대로 동작).

---

### Phase 2.5 종합 수용 기준

- **호출 수 무증가**: LLM 호출 횟수는 E5와 동일하게 2회. 1회라도 늘면 롤백.
- **개인화 향상**: `personalization_score` baseline 대비 **+1.0점 이상**.
- **안전 유지**: `safety_compliance_rate` 1.0, `appropriate_specificity_avg` 저하 없음.
- **Latency 영향 통제**: 입력 토큰 증가에 따른 generate_ms 증가는 E5 대비 **+30% 이내**.
- **회귀 없음**: 기존 가드레일(`intent_accuracy`, `keyword_coverage`, judge 4종) 모두 통과.

---

## 5. Phase 3 — 모델 교체 매트릭스

Phase 0~2 완료 후 시작. 같은 질문 셋·같은 파이프라인에서 모델만 바꿔 비교합니다.

### 5.1 단계별 모델 분리

`rag.py`에서 단계별 모델을 환경변수로 받습니다:

```python
import os
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", DEFAULT_MODEL)
REWRITER_MODEL   = os.getenv("REWRITER_MODEL",   DEFAULT_MODEL)
GENERATOR_MODEL  = os.getenv("GENERATOR_MODEL",  DEFAULT_MODEL)
```

함수 시그니처는 default 인자로 그대로 두고, `answer_question` 안에서 위 변수를 기본값으로 사용.

### 5.2 실험 매트릭스

| 실험 ID | classifier | rewriter | generator | 비고 |
|---------|-----------|----------|-----------|------|
| M0 (baseline) | gpt-5.4-mini | gpt-5.4-mini | gpt-5.4-mini | 현재 |
| M1 | gpt-5.4-nano | gpt-5.4-nano | gpt-5.4-mini | 보조만 nano |
| M2 | gpt-5-nano | gpt-5-nano | gpt-5.4-mini | 차세대 nano 보조 |
| M3 | gpt-5.4-nano | gpt-5.4-nano | gpt-5-mini | 생성도 차세대 |
| M4 | gpt-5-mini | gpt-5-mini | gpt-5-mini | 전체 차세대 mini |
| M5 | gpt-5-nano | gpt-5-nano | gpt-5-nano | 전체 nano (속도 한계 탐지용) |

> 위 모델명은 사용자가 명시한 후보입니다. 존재하지 않으면 실재 모델로 치환 가능 — 단 표는 항상 업데이트.

### 5.3 실행 방법

```bash
# M1 예시
CLASSIFIER_MODEL=gpt-5.4-nano \
REWRITER_MODEL=gpt-5.4-nano \
GENERATOR_MODEL=gpt-5.4-mini \
python eval/evaluate.py --delay 1.5

CLASSIFIER_MODEL=gpt-5.4-nano \
REWRITER_MODEL=gpt-5.4-nano \
GENERATOR_MODEL=gpt-5.4-mini \
python eval/latency_profile.py --repeat 3 --tag M1
```

매 실험 후 결과 JSON 파일명을 `latency_M1_*.json`처럼 prefix로 구분해 저장.

### 5.4 비교 분석

`eval/compare_models.py` 스크립트(신규) — 여러 결과 JSON을 읽어 다음 산출:

- 모델별 `(latency_p50, latency_p95, intent_acc, judge_avg, cost_per_query)` 표
- Pareto frontier 시각화 (matplotlib, x=latency_p95, y=judge_avg)
- 후보 1~2개 추천

**수용 기준**: 최소 한 모델 조합이 baseline 대비 latency **−30% 이상**, 가드레일 모두 통과.

---

## 6. Phase 4 — 종합 튜닝 및 회귀

1. Phase 1~3에서 채택된 변경을 **모두 합쳐** 최종 평가.
2. 동시 적용 시 상호작용으로 새 문제가 발생하지 않는지 확인.
3. baseline 대비 최종 표 작성:

| 지표 | Baseline | Final | Δ |
|------|----------|-------|---|
| latency_avg | | | |
| latency_p95 | | | |
| TTFT_p50 | N/A | | — |
| intent_accuracy | | | |
| safety_compliance | | | |
| personalization_score | | | |
| appropriate_specificity | | | |
| judge_relevance | | | |
| 비용/질의(추정) | | | |

4. 회귀 모니터링: 매 배포 전 `python evaluate.py --no-judge --subset 20`를 CI로 강제 — 가드레일 위반 시 차단.

---

## 7. Claude Code 자동 실행 가이드

이 계획서를 Claude Code(또는 다른 에이전트)에게 다음 형태로 던지면 됩니다.

### 권장 프롬프트 템플릿

```
EXPERIMENT_PLAN.md를 단일 출처(single source of truth)로 따라줘.
Phase 0부터 순차 진행하고, 각 Step/Experiment마다:

1. 변경 적용 (해당 파일만 수정, 다른 파일 건드리지 말 것)
2. 변경 사항을 `git add -p` 후 commit ("exp(E2): cache ChatOpenAI" 형식)
3. 측정 명령 실행 (`cd eval && python latency_profile.py --repeat 3 --tag <ID>`)
4. 결과 JSON을 `eval/results/<ID>/`로 이동
5. EXPERIMENT_PLAN.md 하단 결과 표에 한 줄 추가
6. 수용 기준(Acceptance) 충족 여부를 분석하고 보고
7. 가드레일 위반이면 자동 롤백 (git revert HEAD)

지금은 Phase 0의 Step 0.1부터 시작.
```

### 단일 실험 실행 예

```
@EXPERIMENT_PLAN.md 의 E2 (ChatOpenAI 캐싱)만 적용해줘.
변경 후 latency_profile.py 3회 돌리고 결과 비교해서 알려줘.
```

```
@EXPERIMENT_PLAN.md 의 Phase 2.5 (E5.1~E5.5)를 순차 적용해줘.
E5.1, E5.2 적용 후 한 번 측정, E5.3, E5.4 적용 후 한 번 측정,
E5.5는 평가 인프라이므로 마지막에 적용하고 최종 비교.
```

---

## 8. 결과 추적 표 (실험 진행하며 채워가기)

### 8.1 단계별 latency (Phase 0 baseline)

> 출처: `latency_baseline_20260520_105958.json` (58문항 × 3회 반복, n=174)

| 단계 | 평균(ms) | p50 | p95 | 비고 |
|------|---------|-----|-----|------|
| analyze_query | 860 | 758 | 1278 | LLM #1 (분류) |
| rewrite_query | 935 | 845 | 1371 | LLM #2 (재작성) |
| retrieval | 510 | 454 | 853 | 임베딩 + Chroma 검색 |
| rerank_build | 0 | 0 | 0 | rule-based, 무시 가능 |
| generate | 3316 | 3157 | 4851 | LLM #3 (생성), **전체의 59%** |
| **total** | **5622** | **5406** | **7778** | end-to-end |

### 8.2 실험 결과 누적

| 실험 ID | 변경 요약 | latency_avg | latency_p95 | intent_acc | judge_rel | safety | 결정 |
|---------|-----------|-------------|-------------|-----------|-----------|--------|------|
| baseline | 현재 | 5622ms | 7778ms | 1.000 | 3.83 | 1.0 | — |
| E1 | streaming | | | | | | |
| E2 | LLM cache | 5356ms (−4.7%) | 6846ms (−12.0%) | 0.966† | N/A | 1.0 | 채택 |
| E3 | prompt diet | | | | | | |
| E4 | max_tokens (gen=600, analyze=150, rewrite=80) + 6문장 캡 | 4770ms (−15.2%) | 6356ms (−18.3%) | 1.000 | 3.97 | 1.0 | 채택 |
| E5 | analyze+rewrite 통합 | | | | | | |
| E6 | fast path | | | | | | |
| E7 | semantic cache | | | | | | |
| E5.1 | preprocess v2 (구조화 신호) | | | | | | |
| E5.2 | risk 보정 룰 | | | | | | |
| E5.3 | personalized rerank | | | | | | |
| E5.4 | signals 블록 enrichment | | | | | | |
| E5.5 | 개인화 평가 지표·케이스 | | | | | | |
| M1 | nano보조+mini생성 | | | | | | |
| M2 | gpt5-nano 보조 | | | | | | |
| M3 | nano+gpt5-mini | | | | | | |
| M4 | 전체 gpt5-mini | | | | | | |
| M5 | 전체 nano | | | | | | |
| Final | 종합 | | | | | | |

> † E2 intent_accuracy 0.966(−3.4%p): lru_cache는 LLM 인스턴스만 캐시하며 API 호출은 매번 실행됨. 다른 시점 측정에 따른 LLM 랜덤성 노이즈로 판단(코드 변경이 출력에 영향 없음). retrieval_ms −61%(510→200ms)가 주효과.
>
> ‡ E4 max_tokens=500 초기 시도에서 keyword_coverage 0.737 < 임계값 0.747로 실패. 600으로 상향 후 모든 가드레일 통과(keyword=0.764, completeness=3.155 > 2.838). generate_ms −16.3%(3316→2777ms)가 주효과. context_relevance 3.97은 baseline(3.83) 대비 상승.
>
> Phase 2.5 (E5.1~E5.5)의 경우 `personalization_score` / `appropriate_specificity_avg` / `profile_utilization_rate` / `risk_modifiers` 사용 통계도 결과 JSON에서 별도 추적. "결정" 열에 그 수치를 같이 기록한다.

---

## 9. 안전·주의사항

- **high-risk 질문 안전 처리**(`apply_safety_prefix`)는 어떤 최적화에서도 제거/회피 금지.
- 모델 교체로 JSON 출력이 깨질 수 있음 — `analyze_query` / `preprocess_query_v2`의 `JSONDecodeError` fallback 필수 유지.
- 스트리밍 도입 시 안전 prefix는 stream 시작 전 별도 chunk로 먼저 전송.
- evaluate.py의 `--delay`를 0으로 두면 rate limit으로 측정값이 왜곡됨. 1.0초 이상 유지.
- 모든 비교는 **동일 시점·동일 네트워크**에서 측정. 시간대 다르면 비교 무효.
- **개인화 관련(Phase 2.5)**: 답변에서 진단 단정("X입니다" / "Y일 가능성이 매우 높습니다") 금지. 모든 출력은 "가능성·고려사항·전문가 상담 권유" 톤. `appropriate_specificity_score` 모니터링으로 회귀 감지.
- **개인화 관련**: 알레르기·기저질환·메모는 답변에 활용하되, 의료적 단정의 근거로 쓰지 말 것. "알레르기가 등록되어 있어 ~ 가능성을 고려해보세요" 톤.
- **개인화 관련**: `normalize_risk_level_v2`는 LLM이 뽑은 risk를 **올리기만** 하고 내리지는 않는다. 안전쪽으로만 보정.

---

## 부록 A — 관련 파일 위치

| 파일 | 역할 |
|------|------|
| `app/rag.py` | RAG 파이프라인 핵심 (모든 LLM 호출) |
| `app/prompts.py` | 6개 인텐트별 답변 프롬프트 + 분석/재작성 프롬프트 |
| `app/api.py` | FastAPI 엔드포인트 (`/chat`) |
| `app/vector_config.py` | 임베딩 모델·Chroma 경로 |
| `eval/evaluate.py` | 배치 평가 (품질+latency end-to-end) |
| `eval/test_questions.json` | 평가 질문 셋 |
| `eval/tune.py` | 하이퍼파라미터 그리드 (k, top_k, rerank weights) |
| `eval/latency_profile.py` | (Phase 0 신규) 단계별 latency 측정 |

## 부록 B — Phase 0 끝나면 즉시 만들 측정 스크립트

`eval/latency_profile.py` 스켈레톤은 이 계획서와 함께 동일 디렉토리에 제공됩니다. Claude Code는 이를 그대로 사용하거나 확장해도 됩니다.
