"""
eval/latency_profile.py

RAG 파이프라인의 단계별 latency를 측정·집계하는 스크립트.
evaluate.py 와 달리 품질 메트릭은 계산하지 않고 latency만 빠르게 측정한다.

Phase 0의 Step 0.1 (rag.py answer_question 안의 timings 측정)이 선행되어야
debug_info["timings"]가 채워진다. 그렇지 않으면 단계별 ms는 None으로 기록된다.

사용 예:
    cd eval
    python latency_profile.py --repeat 3
    python latency_profile.py --subset 10 --repeat 3 --tag baseline
    python latency_profile.py --tag E2_llmcache
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "app"))

from rag import answer_question  # noqa: E402


STAGE_KEYS = [
    "preprocess_ms",
    "analyze_query_ms",
    "rewrite_query_ms",
    "retrieval_ms",
    "rerank_build_ms",
    "generate_ms",
    "ttft_ms",
    "total_ms",
]


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 1)


def load_questions(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_one(item: dict) -> dict:
    question = item["question"]
    child_profile = item.get("child_profile")
    recent_logs = item.get("recent_logs")

    t0 = time.perf_counter()
    try:
        answer, _docs, debug_info = answer_question(
            question=question,
            child_profile=child_profile,
            recent_logs=recent_logs,
        )
        wall_ms = round((time.perf_counter() - t0) * 1000, 1)
        timings = debug_info.get("timings", {}) if isinstance(debug_info, dict) else {}
        # rag.py가 아직 timings를 안 채우면 wall만이라도 기록
        if "total_ms" not in timings:
            timings["total_ms"] = wall_ms
        return {
            "id": item["id"],
            "ok": True,
            "wall_ms": wall_ms,
            "answer_len": len(answer) if isinstance(answer, str) else None,
            "timings": timings,
            "intent": debug_info.get("intent") if isinstance(debug_info, dict) else None,
            "model": debug_info.get("model") if isinstance(debug_info, dict) else None,
        }
    except Exception as e:
        return {"id": item["id"], "ok": False, "error": str(e)}


def aggregate(records: list[dict]) -> dict:
    valid = [r for r in records if r.get("ok")]
    out: dict = {"n_total": len(records), "n_ok": len(valid)}
    if not valid:
        return out

    stage_stats = {}
    for k in STAGE_KEYS:
        vals = [r["timings"].get(k) for r in valid if r["timings"].get(k) is not None]
        if vals:
            stage_stats[k] = {
                "n": len(vals),
                "avg": round(mean(vals), 1),
                "p50": percentile(vals, 50),
                "p95": percentile(vals, 95),
                "p99": percentile(vals, 99),
                "min": round(min(vals), 1),
                "max": round(max(vals), 1),
            }

    out["stage_stats"] = stage_stats
    return out


def print_table(stats: dict) -> None:
    print("\n" + "=" * 78)
    print(f"  Profiled: {stats['n_ok']}/{stats['n_total']} successful runs")
    print("=" * 78)
    header = f"  {'stage':<22} {'n':>4} {'avg':>9} {'p50':>9} {'p95':>9} {'p99':>9}"
    print(header)
    print("  " + "-" * 70)
    for k in STAGE_KEYS:
        s = stats.get("stage_stats", {}).get(k)
        if not s:
            continue
        print(
            f"  {k:<22} {s['n']:>4} "
            f"{s['avg']:>8}ms {s['p50']:>8}ms "
            f"{s['p95']:>8}ms {s['p99']:>8}ms"
        )
    print()


def main():
    parser = argparse.ArgumentParser(description="RAG latency profiler")
    parser.add_argument(
        "--questions",
        default=str(Path(__file__).parent / "test_questions.json"),
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).parent / "results"),
    )
    parser.add_argument("--subset", type=int, default=None,
                        help="질문 수 제한 (기본 전체)")
    parser.add_argument("--repeat", type=int, default=3,
                        help="동일 질문 셋 반복 횟수 (median 안정화)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="질문 간 sleep(초)")
    parser.add_argument("--tag", default="run",
                        help="결과 파일/디렉토리 prefix (예: baseline, E2_llmcache, M1)")
    parser.add_argument("--intent", default=None,
                        help="특정 인텐트만 측정")
    args = parser.parse_args()

    questions = load_questions(Path(args.questions))
    if args.intent:
        questions = [q for q in questions if q.get("expected_intent") == args.intent]
    if args.subset:
        questions = questions[: args.subset]

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Profiling: {len(questions)} questions × {args.repeat} rounds "
          f"(tag={args.tag})")

    all_records: list[dict] = []
    round_summaries = []
    for r in range(1, args.repeat + 1):
        print(f"\n── Round {r}/{args.repeat} ──")
        round_records = []
        for i, item in enumerate(questions, 1):
            print(f"  [{r}.{i}/{len(questions)}] {item['id']} ...", end=" ", flush=True)
            rec = run_one(item)
            rec["round"] = r
            total = rec.get("timings", {}).get("total_ms") or rec.get("wall_ms")
            if rec["ok"]:
                print(f"{total}ms")
            else:
                print(f"ERR {rec.get('error')}")
            round_records.append(rec)
            all_records.append(rec)
            if args.delay > 0:
                time.sleep(args.delay)
        round_summaries.append(aggregate(round_records))

    overall = aggregate(all_records)
    print_table(overall)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"latency_{args.tag}_{ts}.json"
    report = {
        "timestamp": ts,
        "tag": args.tag,
        "config": {
            "questions_file": args.questions,
            "n_questions": len(questions),
            "repeat": args.repeat,
            "delay_sec": args.delay,
            "intent_filter": args.intent,
        },
        "overall": overall,
        "rounds": round_summaries,
        "records": all_records,
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
