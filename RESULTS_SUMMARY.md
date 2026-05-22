# 챗봇 Latency 최적화 — 실험 결과 요약

육아 RAG 챗봇 / 한성대 AI 캡스톤
측정 기준: 58문항 테스트셋, latency_profile `--repeat 3` (n=174), evaluate.py judge 포함 (n=58)

---

## 1. 한 줄 요약

5단계 실험을 통해 챗봇 응답 latency를 **평균 5,622ms → 4,104ms (−27.0%)** 로 단축했으며, 안전성·답변 품질은 측정 노이즈 범위 내에서 유지했다. 가장 큰 동인은 **LLM 직렬 호출 수 감소(3→2회)** 와 **벡터스토어 인스턴스 캐싱**이었고, **모델 교체는 이 환경에서 효과가 없음**을 데이터로 확인했다.

---

## 2. 문제 정의와 목적

- **문제**: 챗봇 응답 latency가 과도하게 김 (baseline 평균 5.6초, p95 7.8초).
- **목적**: latency를 줄이되 답변 성능(정확도·안전성·관련성)은 유지.
- **목표치**: latency −40% (self-imposed target).
- **제약**: high-risk(경련·호흡곤란 등) 질문의 안전 안내는 어떤 경우에도 유지.

---

## 3. 측정 방법론

최적화에 앞서 **측정 인프라부터 구축**했다. 이것이 전체 실험의 신뢰성을 좌우했다.

1. **단계별 timing 계측**: `answer_question`에 단계별 `timings`(preprocess / retrieval / rerank / generate)를 기록하도록 계측. 어디서 시간이 쓰이는지 분해.
2. **percentile 기반 평가**: 평균뿐 아니라 p50/p95/p99를 추적 (tail latency 포착).
3. **반복 측정**: 동일 설정 `--repeat 3` 이상으로 median 사용.
4. **노이즈 플로어 측정**: 코드 변경 없이 baseline을 4회 재측정해 자연 변동폭을 먼저 파악.
   - `intent_accuracy`: ±3.4%p (최대 2/58문항 흔들림)
   - `safety_compliance`: 변동 0 (항상 1.0) — 가장 신뢰할 수 있는 메트릭
   - judge 메트릭(context_relevance 등): ±0.3 (변동 큼)
5. **가드레일 판정**: 단일 run이 아닌 노이즈 플로어를 기준으로 통과/실패 판정.

> 핵심 교훈: judge 점수의 자연 변동폭(±0.3)이 실험 간 차이보다 클 수 있으므로, "품질 향상/저하"는 변동 없는 메트릭(safety)과 일관된 메트릭(keyword_coverage, latency)으로 판정해야 한다.

---

## 4. baseline 프로파일 (병목 식별)

| 단계 | 평균(ms) | 비중 |
|------|---------|------|
| analyze_query (LLM #1) | 860 | 15% |
| rewrite_query (LLM #2) | 935 | 17% |
| retrieval (embedding + Chroma) | 510 | 9% |
| rerank_build | 0 | ~0% |
| generate (LLM #3) | 3,316 | 59% |
| **total** | **5,622** | 100% |

**진단**: LLM 호출이 3회 직렬, generate가 단일 최대 병목(59%). retrieval은 Chroma 재초기화 비용이 포함되어 의외로 큼.

---

## 5. 실험별 결과

### 채택된 실험

| ID | 변경 | total avg | 누적 Δ | 핵심 효과 |
|----|------|-----------|--------|-----------|
| E2 | 인스턴스 캐싱 (`lru_cache`로 LLM/embedding/vectorstore 재사용) | 5,356ms | −4.7% | **retrieval −68%** (Chroma 재초기화 제거) |
| E4 | `max_tokens` 캡 (generate=600, 분류=150) + "6문장 이내" 지시 | 4,770ms | −15.2% | **generate −16%** (decode 단축) |
| E5 | analyze+rewrite를 단일 preprocess 호출로 통합 | 4,139ms | −26.4% | **LLM 호출 3→2회**, preprocess −35% |
| E8 | preprocess 출력 다이어트 (18단어 제한, `needs_clarification` 제거) | 4,104ms | −27.0% | preprocess p50 −12%, 소폭 |

### 기각된 실험 (모델 교체)

| ID | 설정 | total avg | 판정 |
|----|------|-----------|------|
| M1 | preprocess=gpt-5.4-nano | 4,821ms | 기각 (E5 대비 +16.5%) |
| M2 | preprocess=gpt-5-nano | 4,974ms | 기각 |
| M4 | 전체 gpt-5-mini | 9,060ms | 기각 (2× 느림) |

**발견**: `gpt-5.4-mini`가 이 환경에서 가장 빠른 모델. nano tier는 모델 추론은 빠를지 몰라도 **API tail latency가 커서**(p99가 16~20초까지 튐) 평균 latency가 오히려 악화. `gpt-5-mini`(차세대 mini)는 `gpt-5.4-mini`보다 2배 이상 느림. `.4` 접미사가 serving 최적화 버전으로 추정됨. **결론: latency 병목은 모델 선택이 아니라 직렬 호출 수.**

### 미실행 / 별도 트랙

- **E1 (스트리밍)**: 총 latency를 안 바꾸고 TTFT(체감)만 개선 → 목표 메트릭과 다른 축이라 본 실험에서 제외. 향후 UX 개선용 후보.
- **E3 (프롬프트 다이어트)**: 두 호출 모두 decode-bound로 확인되어 prefill 축소 효과가 제한적이라 판단, 건너뜀.
- **E6 (fast path)**: −27% 달성 후 ROI 부족으로 미실행.
- **E5.1~E5.5 (개인화·관계 분석)**: 별도 기능 트랙(EXPERIMENT_PLAN.md Phase 2.5)으로 분리.

---

## 6. 최종 성과

### Latency (n=174)

| 지표 | Baseline | Final | Δ |
|------|----------|-------|---|
| total avg | 5,622ms | 4,104ms | **−27.0%** |
| total p50 | 5,406ms | 3,903ms | −27.8% |
| total p95 | 7,778ms | 5,643ms | −27.4% |
| total p99 | 11,145ms | 8,546ms | −23.3% |

### 단계별 (avg)

| 단계 | Baseline | Final | Δ |
|------|----------|-------|---|
| preprocess (=analyze+rewrite) | 1,795ms | 1,162ms | −35.3% |
| retrieval | 510ms | 165ms | −67.6% |
| generate | 3,316ms | 2,777ms | −16.3% |
| **total** | **5,622ms** | **4,104ms** | **−27.0%** |

### 품질 (judge 포함, n=58)

| 지표 | Baseline | Final | 판정 |
|------|----------|-------|------|
| safety_compliance | 1.000 | 1.000 | 유지 (변동 0) |
| intent_accuracy | 1.000 | 0.983 | 유지 (노이즈 ±3.4%p 내) |
| keyword_coverage | 0.797 | 0.758 | 유지 (가드레일 0.747 초과) |
| context_relevance (judge) | 3.93 | 4.21 | 유지 (judge 노이즈 ±0.3 내) |
| answer_relevance (judge) | 3.83 | 3.78 | 유지 |
| LLM 호출 수/질의 | 3 | 2 | −1 |

---

## 7. 핵심 교훈

1. **측정이 8할**: 노이즈 플로어를 먼저 측정한 덕분에 "0.966은 회귀가 아니라 노이즈"를 정확히 판정할 수 있었다. 측정 인프라 없이 단일 run으로 판단했다면 잘못된 롤백/채택을 반복했을 것.
2. **병목은 아키텍처지 모델이 아니다**: 모델 교체 4종을 모두 시도해 전부 기각. latency를 실제로 줄인 건 호출 수 감소(E5)와 인스턴스 캐싱(E2). 직관("작은 모델 = 빠름")이 API tail latency 앞에서 깨졌다.
3. **negative result도 결과다**: nano/차세대 모델이 더 느리다는 발견은 향후 의사결정을 절약한다 (모델 교체 재시도 불필요).
4. **decode-bound 작업은 출력으로만 단축된다**: E8에서 preprocess 출력을 줄이려 했으나, rewritten_query가 retrieval 품질과 결합되어 있어 출력 단축이 곧 검색 품질 저하로 이어졌다 (12단어 → context_relevance −0.40). 18단어 절충으로 품질 유지 시 latency 이득은 소폭에 그침.
5. **목표는 숫자가 아니라 의도**: −40%엔 미달했지만 원래 목적("latency 줄이며 성능 유지")은 −27%로 충족. 나머지 13%p는 품질 트레이드오프나 코드 복잡도를 요구해 ROI상 종료가 합리적.

---

## 8. 채택된 최종 파이프라인

```
사용자 질문
    │
    ▼
[preprocess (LLM 1회)]   ← E5: 분류+재작성 통합, E8: 출력 다이어트
    │  intent / risk / rewritten_query
    ▼
[벡터 검색 (ChromaDB)]    ← E2: 인스턴스 캐싱 (retrieval −68%)
    │
    ▼
[Reranking (rule-based)]
    │
    ▼
[답변 생성 (LLM 1회)]     ← E4: max_tokens 캡 + 간결화 지시
    │
    ▼
최종 답변 (+ high-risk 안전 prefix, 전 구간 유지)
```

채택 변경: **E2 + E4 + E5 + E8**. LLM 호출 3→2회, 평균 5.6초 → 4.1초.

---

## 9. 향후 과제

- **E1 (스트리밍)**: 총 latency는 그대로지만 TTFT를 1초 이내로 줄여 체감 응답성 대폭 개선. 사용자 만족도 관점에서 가장 효과 큰 후속 작업.
- **E6 (fast path)**: 병원/약국 위치 등 키워드 명확 질의는 preprocess를 건너뛰어 추가 단축 가능.
- **E5.1~E5.5 (개인화)**: 아이 프로필·증상 관계 분석으로 답변 구체성 향상 (별도 트랙).
- **회귀 가드**: 배포 전 `evaluate.py --no-judge --subset 20`을 CI로 강제해 가드레일 위반 차단.

---

## 부록 — 결과 파일 위치

| 실험 | latency 결과 | eval 결과 |
|------|-------------|-----------|
| baseline | `eval/results/baseline/latency_baseline_*.json` | `eval/results/baseline/eval_*.json` |
| E2 | `eval/results/E2_llmcache/` | — |
| E4 | `eval/results/E4_maxtokens/` | `eval/results/E4_maxtokens/eval_E4_600_*.json` |
| E5 | `eval/results/E5_unified/` | `eval/results/E5_unified/eval_*.json` |
| E8 | `eval/results/latency_E8_*.json` | `eval/results/E8_preprocess_diet/`, `eval/results/eval_20260522_094243.json` |
| M1 | `eval/results/M1_preprocess_nano/` | — |
| M2 | `eval/results/latency_M2_quick_*.json` | — |
| M4 | `eval/results/latency_M4_*.json` | — |

상세 실험 설계·코드 변경안은 `EXPERIMENT_PLAN.md` 참조.
