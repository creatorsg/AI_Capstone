"""
eval/evaluate.py

RAG 시스템 배치 평가 스크립트.

메트릭:
  - intent_accuracy       : 예측 인텐트 vs 기대 인텐트 (rule-based)
  - risk_level_accuracy   : 예측 risk_level vs 기대 risk_level (rule-based)
  - keyword_coverage      : 정답 키워드가 답변에 몇 % 포함됐는지 (rule-based)
  - context_relevance     : LLM-as-judge (1~5)
  - answer_faithfulness   : LLM-as-judge (1~5)
  - answer_relevance      : LLM-as-judge (1~5)
  - completeness          : LLM-as-judge (1~5)
  - safety_compliance     : high-risk 질문에 안전 경고 포함 여부 (rule-based)

사용법:
  cd eval
  python evaluate.py [--questions test_questions.json] [--output results/] [--subset N] [--no-judge]
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# app/ 디렉토리를 경로에 추가
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "app"))

from rag import answer_question, build_context  # noqa: E402

JUDGE_MODEL = "gpt-5.4-mini"

JUDGE_PROMPT = """\
당신은 육아 챗봇 답변을 평가하는 심사자입니다.
아래 정보를 보고 각 기준을 1~5점으로 평가한 뒤 반드시 JSON으로만 답하세요.
설명 문장, 코드블록, 마크다운은 절대 쓰지 마세요.

질문: {question}

참고 문서 (검색 결과):
{context}

챗봇 답변:
{answer}

평가 기준:
- context_relevance: 검색된 문서가 질문에 얼마나 관련있는가 (1=무관, 5=매우 관련)
- answer_faithfulness: 답변이 제공된 문서에 근거하는가 (1=완전히 벗어남, 5=완전히 근거)
- answer_relevance: 답변이 질문을 실제로 해결하는가 (1=전혀 관련없음, 5=완벽히 해결)
- completeness: 답변이 충분히 완전한가 (1=매우 불완전, 5=매우 완전)

{{"context_relevance": N, "answer_faithfulness": N, "answer_relevance": N, "completeness": N}}"""

SAFETY_SIGNAL = "응급 가능성을 배제할 수 없습니다"


def load_questions(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def keyword_coverage(answer: str, golden_keywords: list[str]) -> float:
    if not golden_keywords:
        return 1.0
    hit = sum(1 for kw in golden_keywords if kw in answer)
    return round(hit / len(golden_keywords), 3)


def safety_compliance(answer: str, expected_risk: str) -> bool:
    if expected_risk == "high":
        return SAFETY_SIGNAL in answer
    return True


def llm_judge(question: str, context: str, answer: str, llm: ChatOpenAI) -> dict:
    prompt = JUDGE_PROMPT.format(
        question=question,
        context=context[:2000],
        answer=answer[:1500],
    )
    try:
        response = llm.invoke(prompt)
        scores = json.loads(response.content.strip())
        for key in ("context_relevance", "answer_faithfulness", "answer_relevance", "completeness"):
            scores.setdefault(key, None)
        return scores
    except Exception as e:
        return {
            "context_relevance": None,
            "answer_faithfulness": None,
            "answer_relevance": None,
            "completeness": None,
            "judge_error": str(e),
        }


def evaluate_one(item: dict, use_judge: bool, judge_llm: ChatOpenAI | None) -> dict:
    question = item["question"]
    child_profile = item.get("child_profile")
    recent_logs = item.get("recent_logs")

    try:
        t0 = time.perf_counter()
        answer, docs, debug_info = answer_question(
            question=question,
            child_profile=child_profile,
            recent_logs=recent_logs,
        )
        latency = round(time.perf_counter() - t0, 3)
    except Exception as e:
        return {
            "id": item["id"],
            "question": question,
            "error": str(e),
        }

    context_str = build_context(docs)

    result = {
        "id": item["id"],
        "question": question,
        "expected_intent": item["expected_intent"],
        "predicted_intent": debug_info["intent"],
        "intent_correct": debug_info["intent"] == item["expected_intent"],
        "expected_risk": item["expected_risk_level"],
        "predicted_risk": debug_info["risk_level"],
        "risk_correct": debug_info["risk_level"] == item["expected_risk_level"],
        "keyword_coverage": keyword_coverage(answer, item.get("golden_keywords", [])),
        "safety_compliance": safety_compliance(answer, item["expected_risk_level"]),
        "needs_clarification_predicted": debug_info.get("needs_clarification", False),
        "needs_clarification_expected": item.get("needs_clarification", False),
        "answer_preview": answer[:300],
        "retrieved_docs_count": debug_info["retrieved_docs_count"],
        "latency_sec": latency,
    }

    result["timings"] = debug_info.get("timings", {})
    result["json_fallback"] = debug_info.get("json_fallback", False)
    result["preprocess_model"] = debug_info.get("preprocess_model")
    result["generator_model"] = debug_info.get("generator_model")

    if use_judge and judge_llm is not None:
        scores = llm_judge(question, context_str, answer, judge_llm)
        result.update(scores)

    return result


def percentile(values: list, p: float):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 1)


def aggregate(results: list[dict]) -> dict:
    valid = [r for r in results if "error" not in r]
    if not valid:
        return {}

    def avg(key):
        vals = [r[key] for r in valid if r.get(key) is not None and isinstance(r[key], (int, float))]
        return round(sum(vals) / len(vals), 3) if vals else None

    overall = {
        "total": len(results),
        "valid": len(valid),
        "errors": len(results) - len(valid),
        "intent_accuracy": round(sum(r["intent_correct"] for r in valid) / len(valid), 3),
        "risk_level_accuracy": round(sum(r["risk_correct"] for r in valid) / len(valid), 3),
        "keyword_coverage_avg": avg("keyword_coverage"),
        "safety_compliance_rate": round(
            sum(r["safety_compliance"] for r in valid) / len(valid), 3
        ),
        "context_relevance_avg": avg("context_relevance"),
        "answer_faithfulness_avg": avg("answer_faithfulness"),
        "answer_relevance_avg": avg("answer_relevance"),
        "completeness_avg": avg("completeness"),
        "latency_avg_sec": avg("latency_sec"),
        "latency_min_sec": round(min(r["latency_sec"] for r in valid if r.get("latency_sec") is not None), 3) if any(r.get("latency_sec") is not None for r in valid) else None,
        "latency_max_sec": round(max(r["latency_sec"] for r in valid if r.get("latency_sec") is not None), 3) if any(r.get("latency_sec") is not None for r in valid) else None,
    }

    stage_keys = ["preprocess_ms", "analyze_query_ms", "rewrite_query_ms",
                  "retrieval_ms", "rerank_build_ms", "generate_ms", "total_ms"]
    stage_stats = {}
    for stage_key in stage_keys:
        vals = [r["timings"].get(stage_key) for r in valid
                if r.get("timings", {}).get(stage_key) is not None]
        if vals:
            stage_stats[stage_key] = {
                "avg": round(sum(vals) / len(vals), 1),
                "p50": percentile(vals, 50),
                "p95": percentile(vals, 95),
                "p99": percentile(vals, 99),
            }
    overall["stage_stats"] = stage_stats

    return overall


def aggregate_by_intent(results: list[dict]) -> dict:
    from collections import defaultdict
    by_intent: dict[str, list] = defaultdict(list)
    for r in results:
        if "error" not in r:
            by_intent[r["expected_intent"]].append(r)

    summary = {}
    for intent, items in by_intent.items():
        summary[intent] = {
            "count": len(items),
            "intent_accuracy": round(sum(i["intent_correct"] for i in items) / len(items), 3),
            "risk_accuracy": round(sum(i["risk_correct"] for i in items) / len(items), 3),
            "keyword_coverage_avg": round(
                sum(i["keyword_coverage"] for i in items) / len(items), 3
            ),
        }
    return summary


def print_summary(overall: dict, by_intent: dict) -> None:
    print("\n" + "=" * 60)
    print("전체 평가 요약")
    print("=" * 60)
    for k, v in overall.items():
        label = k.replace("_", " ").title()
        print(f"  {label:<35} {v}")

    print("\n인텐트별 분석")
    print("-" * 60)
    for intent, stats in by_intent.items():
        print(f"\n  [{intent}]  (n={stats['count']})")
        print(f"    인텐트 정확도: {stats['intent_accuracy']:.1%}")
        print(f"    리스크 정확도: {stats['risk_accuracy']:.1%}")
        print(f"    키워드 커버리지: {stats['keyword_coverage_avg']:.1%}")
    print()


def main():
    parser = argparse.ArgumentParser(description="RAG 시스템 평가")
    parser.add_argument(
        "--questions",
        default=str(Path(__file__).parent / "test_questions.json"),
        help="테스트 질문 파일 경로",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).parent / "results"),
        help="결과 저장 디렉토리",
    )
    parser.add_argument(
        "--subset",
        type=int,
        default=None,
        help="평가할 질문 수 제한 (기본: 전체)",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="LLM-as-judge 평가를 건너뜀 (빠른 실행)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="질문 간 API 호출 딜레이(초), 기본 1.0",
    )
    parser.add_argument(
        "--intent",
        default=None,
        help="특정 인텐트 질문만 평가 (예: --intent hospital_locator)",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        default=None,
        help="특정 질문 ID만 평가 (예: --ids pha_001 pha_002 pha_003)",
    )
    args = parser.parse_args()

    questions_path = Path(args.questions)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    questions = load_questions(questions_path)

    if args.ids:
        id_set = set(args.ids)
        questions = [q for q in questions if q["id"] in id_set]
    elif args.intent:
        questions = [q for q in questions if q["expected_intent"] == args.intent]

    if args.subset:
        questions = questions[: args.subset]

    use_judge = not args.no_judge
    judge_llm = ChatOpenAI(model=JUDGE_MODEL, temperature=0) if use_judge else None

    print(f"평가 시작: {len(questions)}개 질문 | LLM Judge: {'ON' if use_judge else 'OFF'}")

    total_start = time.perf_counter()
    results = []
    for i, item in enumerate(questions, start=1):
        print(f"  [{i}/{len(questions)}] {item['id']}: {item['question'][:50]}...")
        result = evaluate_one(item, use_judge=use_judge, judge_llm=judge_llm)
        results.append(result)
        lat = result.get("latency_sec")
        if lat is not None:
            print(f"    ⏱ {lat:.1f}s")
        if args.delay > 0:
            time.sleep(args.delay)
    total_elapsed = round(time.perf_counter() - total_start, 1)

    overall = aggregate(results)
    by_intent = aggregate_by_intent(results)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = output_dir / f"eval_{timestamp}.json"

    report = {
        "timestamp": timestamp,
        "total_runtime_sec": total_elapsed,
        "config": {
            "questions_file": str(questions_path),
            "filter_intent": args.intent,
            "filter_ids": args.ids,
            "total_questions": len(questions),
            "judge_model": JUDGE_MODEL if use_judge else None,
        },
        "overall": overall,
        "by_intent": by_intent,
        "details": results,
    }

    with result_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print_summary(overall, by_intent)
    print(f"결과 저장: {result_path}")


if __name__ == "__main__":
    main()
