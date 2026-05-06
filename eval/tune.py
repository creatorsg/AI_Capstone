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

    for item in questions:
        try:
            answer, docs, debug_info = answer_question(
                question=item["question"],
                child_profile=item.get("child_profile"),
                recent_logs=item.get("recent_logs"),
                k=k,
                top_k=top_k,
                temperature=temperature,
            )
        except Exception:
            errors += 1
            continue

        intent_hits.append(debug_info["intent"] == item["expected_intent"])
        risk_hits.append(debug_info["risk_level"] == item["expected_risk_level"])
        keyword_covs.append(keyword_coverage(answer, item.get("golden_keywords", [])))
        safety_hits.append(safety_compliance(answer, item["expected_risk_level"]))

        if delay > 0:
            time.sleep(delay)

    n = len(intent_hits)
    if n == 0:
        return {"error": "모든 질문 실패"}

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
    }


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
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    questions = load_questions(Path(args.questions))
    # 인텐트 균형을 위해 인텐트별로 골고루 샘플
    from collections import defaultdict
    by_intent: dict[str, list] = defaultdict(list)
    for q in questions:
        by_intent[q["expected_intent"]].append(q)

    subset: list[dict] = []
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
        print(f"  → composite={result.get('composite_score', 'N/A')}")

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
        "config": {
            "questions_file": args.questions,
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
