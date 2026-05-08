"""
eval/tune.py

RAG 하이퍼파라미터 튜닝 스크립트.

재인제스트 없이 튜닝 가능한 파라미터:
  - k           : retrieval 문서 수 (기본 6)
  - top_k       : reranking 후 LLM에 전달할 문서 수 (기본 4)
  - temperature : LLM temperature (기본 0.0)

재인제스트가 필요한 파라미터 (이 스크립트에서 다루지 않음):
  - chunk_size, chunk_overlap

평가 메트릭 (LLM Judge 제외, 빠른 실행):
  - intent_accuracy
  - risk_level_accuracy
  - keyword_coverage
  - safety_compliance

사용법:
  cd eval
  python tune.py [--subset 15] [--output results/]
"""

import argparse
import itertools
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "app"))

from rag import (  # noqa: E402
    answer_question,
    build_context,
    DEFAULT_MODEL,
)

PARAM_GRID = {
    "k": [4, 6, 8],
    "top_k": [3, 4, 5],
    "temperature": [0.0, 0.2],
}

QUESTIONS_PATH = Path(__file__).parent / "test_questions.json"


def load_questions(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def keyword_coverage(answer: str, golden_keywords: list[str]) -> float:
    if not golden_keywords:
        return 1.0
    hit = sum(1 for kw in golden_keywords if kw in answer)
    return hit / len(golden_keywords)


def safety_compliance(answer: str, expected_risk: str) -> bool:
    if expected_risk == "high":
        return "응급 가능성을 배제할 수 없습니다" in answer
    return True


def evaluate_config(
    questions: list[dict],
    k: int,
    top_k: int,
    temperature: float,
    delay: float = 0.5,
) -> dict:
    intent_hits = []
    risk_hits = []
    keyword_covs = []
    safety_hits = []
    errors = 0
    details = []

    latencies = []

    for item in questions:
        t0 = time.perf_counter()
        try:
            answer, docs, debug_info = answer_question(
                question=item["question"],
                child_profile=item.get("child_profile"),
                recent_logs=item.get("recent_logs"),
                k=k,
                top_k=top_k,
                temperature=temperature,
            )
            latency = round(time.perf_counter() - t0, 3)
        except Exception as e:
            errors += 1
            print(f"    [오류] {item['id']}: {type(e).__name__}: {e}")
            details.append({
                "id": item["id"],
                "question": item["question"],
                "error": f"{type(e).__name__}: {e}",
                "latency_sec": None,
            })
            continue

        intent_correct = debug_info["intent"] == item["expected_intent"]
        risk_correct = debug_info["risk_level"] == item["expected_risk_level"]
        kw_cov = keyword_coverage(answer, item.get("golden_keywords", []))
        safe = safety_compliance(answer, item["expected_risk_level"])

        intent_hits.append(intent_correct)
        risk_hits.append(risk_correct)
        keyword_covs.append(kw_cov)
        safety_hits.append(safe)
        latencies.append(latency)

        details.append({
            "id": item["id"],
            "question": item["question"],
            "answer": answer,
            "expected_intent": item["expected_intent"],
            "predicted_intent": debug_info["intent"],
            "intent_correct": intent_correct,
            "expected_risk": item["expected_risk_level"],
            "predicted_risk": debug_info["risk_level"],
            "risk_correct": risk_correct,
            "keyword_coverage": round(kw_cov, 3),
            "safety_compliance": safe,
            "rewritten_query": debug_info.get("rewritten_query", ""),
            "retrieved_docs_count": debug_info.get("retrieved_docs_count", 0),
            "latency_sec": latency,
        })

        if delay > 0:
            time.sleep(delay)

    n = len(intent_hits)
    if n == 0:
        return {"k": k, "top_k": top_k, "temperature": temperature,
                "error": "모든 질문 실패", "details": details}

    return {
        "k": k,
        "top_k": top_k,
        "temperature": temperature,
        "n_evaluated": n,
        "errors": errors,
        "intent_accuracy": round(sum(intent_hits) / n, 3),
        "risk_accuracy": round(sum(risk_hits) / n, 3),
        "keyword_coverage": round(sum(keyword_covs) / n, 3),
        "safety_compliance": round(sum(safety_hits) / n, 3),
        "composite_score": round(
            (sum(intent_hits) / n) * 0.35
            + (sum(risk_hits) / n) * 0.25
            + (sum(keyword_covs) / n) * 0.25
            + (sum(safety_hits) / n) * 0.15,
            3,
        ),
        "latency_avg_sec": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "latency_min_sec": round(min(latencies), 3) if latencies else None,
        "latency_max_sec": round(max(latencies), 3) if latencies else None,
        "details": details,
    }


def recalculate_metrics(k: int, top_k: int, temperature: float, details: list[dict]) -> dict:
    valid = [d for d in details if "error" not in d]
    errors = len(details) - len(valid)
    n = len(valid)
    if n == 0:
        return {"k": k, "top_k": top_k, "temperature": temperature,
                "error": "모든 질문 실패", "details": details}

    intent_hits = [d["intent_correct"] for d in valid]
    risk_hits = [d["risk_correct"] for d in valid]
    keyword_covs = [d["keyword_coverage"] for d in valid]
    safety_hits = [d["safety_compliance"] for d in valid]
    latencies = [d["latency_sec"] for d in valid if d.get("latency_sec") is not None]

    return {
        "k": k,
        "top_k": top_k,
        "temperature": temperature,
        "n_evaluated": n,
        "errors": errors,
        "intent_accuracy": round(sum(intent_hits) / n, 3),
        "risk_accuracy": round(sum(risk_hits) / n, 3),
        "keyword_coverage": round(sum(keyword_covs) / n, 3),
        "safety_compliance": round(sum(safety_hits) / n, 3),
        "composite_score": round(
            (sum(intent_hits) / n) * 0.35
            + (sum(risk_hits) / n) * 0.25
            + (sum(keyword_covs) / n) * 0.25
            + (sum(safety_hits) / n) * 0.15,
            3,
        ),
        "latency_avg_sec": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "latency_min_sec": round(min(latencies), 3) if latencies else None,
        "latency_max_sec": round(max(latencies), 3) if latencies else None,
        "details": details,
    }


def merge_results(existing_path: Path, new_all_results: list[dict]) -> list[dict]:
    with existing_path.open("r", encoding="utf-8") as f:
        existing_report = json.load(f)

    existing_by_key: dict[tuple, dict] = {}
    for r in existing_report.get("all_results", []):
        key = (r["k"], r["top_k"], r["temperature"])
        existing_by_key[key] = r

    merged = []
    new_keys: set[tuple] = set()

    for new_r in new_all_results:
        key = (new_r["k"], new_r["top_k"], new_r["temperature"])
        new_keys.add(key)
        old_r = existing_by_key.get(key)
        if old_r is None:
            merged.append(new_r)
            continue

        old_details = old_r.get("details", [])
        new_details = new_r.get("details", [])
        new_ids = {d["id"] for d in new_details}
        combined = new_details + [d for d in old_details if d["id"] not in new_ids]
        merged.append(recalculate_metrics(new_r["k"], new_r["top_k"], new_r["temperature"], combined))

    for key, old_r in existing_by_key.items():
        if key not in new_keys:
            merged.append(old_r)

    return merged


def print_results_table(results: list[dict]) -> None:
    sorted_res = sorted(results, key=lambda x: x.get("composite_score", 0), reverse=True)

    header = f"{'순위':<4} {'k':>3} {'top_k':>6} {'temp':>6} | {'intent':>8} {'risk':>8} {'keyword':>9} {'safety':>8} | {'composite':>10}"
    print("\n" + "=" * len(header))
    print("하이퍼파라미터 튜닝 결과 (composite score 기준 정렬)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for rank, r in enumerate(sorted_res, start=1):
        if "error" in r:
            continue
        print(
            f"{rank:<4} {r['k']:>3} {r['top_k']:>6} {r['temperature']:>6.1f} | "
            f"{r['intent_accuracy']:>8.3f} {r['risk_accuracy']:>8.3f} "
            f"{r['keyword_coverage']:>9.3f} {r['safety_compliance']:>8.3f} | "
            f"{r['composite_score']:>10.3f}"
        )

    best = sorted_res[0]
    print("\n최적 파라미터:")
    print(f"  k={best['k']}, top_k={best['top_k']}, temperature={best['temperature']}")
    print(f"  composite_score={best['composite_score']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="RAG 하이퍼파라미터 튜닝")
    parser.add_argument(
        "--questions",
        default=str(QUESTIONS_PATH),
        help="테스트 질문 파일 경로",
    )
    parser.add_argument(
        "--subset",
        type=int,
        default=20,
        help="평가에 사용할 질문 수 (기본: 20, 비용 절감)",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).parent / "results"),
        help="결과 저장 디렉토리",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="질문 간 딜레이(초), 기본 0.5",
    )
    parser.add_argument(
        "--k-values",
        nargs="+",
        type=int,
        default=PARAM_GRID["k"],
        help="탐색할 k 값들 (예: --k-values 4 6 8)",
    )
    parser.add_argument(
        "--top-k-values",
        nargs="+",
        type=int,
        default=PARAM_GRID["top_k"],
        help="탐색할 top_k 값들 (예: --top-k-values 3 4 5)",
    )
    parser.add_argument(
        "--temp-values",
        nargs="+",
        type=float,
        default=PARAM_GRID["temperature"],
        help="탐색할 temperature 값들 (예: --temp-values 0.0 0.2)",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        default=None,
        help="평가할 질문 ID 지정 (예: --ids pha_001 pha_002). 지정 시 --subset 무시.",
    )
    parser.add_argument(
        "--merge",
        default=None,
        help="기존 튜닝 결과 JSON 경로. 지정 시 새 결과를 기존 결과에 병합.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    questions = load_questions(Path(args.questions))

    if args.ids:
        id_set = set(args.ids)
        subset = [q for q in questions if q["id"] in id_set]
        print(f"ID 필터 적용: {sorted(id_set)} → {len(subset)}개 질문")
    else:
        from collections import defaultdict
        by_intent: dict[str, list] = defaultdict(list)
        for q in questions:
            by_intent[q["expected_intent"]].append(q)

        subset = []
        per_intent = max(1, args.subset // len(by_intent))
        for items in by_intent.values():
            subset.extend(items[:per_intent])
        subset = subset[: args.subset]

    param_combinations = list(
        itertools.product(args.k_values, args.top_k_values, args.temp_values)
    )
    total = len(param_combinations)

    print(f"튜닝 시작: {total}개 조합 × {len(subset)}개 질문 = {total * len(subset)}번 RAG 호출")
    print(f"파라미터 그리드: k={args.k_values}, top_k={args.top_k_values}, temperature={args.temp_values}")

    total_start = time.perf_counter()
    all_results = []
    for idx, (k, top_k, temperature) in enumerate(param_combinations, start=1):
        print(f"\n[{idx}/{total}] k={k}, top_k={top_k}, temperature={temperature}")
        result = evaluate_config(
            questions=subset,
            k=k,
            top_k=top_k,
            temperature=temperature,
            delay=args.delay,
        )
        all_results.append(result)
        lat = result.get("latency_avg_sec")
        lat_str = f" | avg {lat:.1f}s/질문" if lat is not None else ""
        print(f"  → composite={result.get('composite_score', 'N/A')}{lat_str}")
    total_elapsed = round(time.perf_counter() - total_start, 1)
    print(f"\n총 실행시간: {total_elapsed}초")

    if args.merge:
        merge_path = Path(args.merge)
        print(f"\n기존 결과 병합 중: {merge_path}")
        all_results = merge_results(merge_path, all_results)
        print(f"병합 완료: {len(all_results)}개 조합")

    print_results_table(all_results)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"tune_{timestamp}.json"

    best = max(
        [r for r in all_results if "composite_score" in r],
        key=lambda x: x["composite_score"],
        default=None,
    )

    report = {
        "timestamp": timestamp,
        "total_runtime_sec": total_elapsed,
        "config": {
            "questions_file": args.questions,
            "new_ids": args.ids,
            "merged_from": args.merge,
            "subset_size": len(subset),
            "param_grid": {
                "k": args.k_values,
                "top_k": args.top_k_values,
                "temperature": args.temp_values,
            },
        },
        "best": best,
        "all_results": sorted(
            all_results, key=lambda x: x.get("composite_score", 0), reverse=True
        ),
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"결과 저장: {output_path}")

    if best:
        print("\n[적용 방법]")
        print("rag.py의 answer_question() 호출 시 아래 파라미터를 사용하세요:")
        print(f"  k={best['k']}, top_k={best['top_k']}, temperature={best['temperature']}")
        print("또는 rag.py의 DEFAULT_K, DEFAULT_TOP_K 상수를 수정하세요.")


if __name__ == "__main__":
    main()
