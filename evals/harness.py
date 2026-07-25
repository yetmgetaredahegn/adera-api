"""AI Eval Harness CLI (Master Plan Appendix C, 06 §9).

Runs smoke/full evaluations over golden datasets in `evals/golden/`.
Usage:
    uv run python -m evals.harness [--smoke] [--task TASK]
"""

import argparse
import json
from pathlib import Path

from evals.scorers import (
    check_explanation_grounding,
    compute_extraction_f1,
    compute_qualification_metrics,
)

GOLDEN_DIR = Path(__file__).parent / "golden"


def run_extraction_eval(limit: int | None = None) -> dict[str, float]:
    golden_file = GOLDEN_DIR / "extraction.jsonl"
    if not golden_file.exists():
        print(f"Skipping extraction eval: {golden_file} not found.")
        return {"field_f1": 0.0, "closing_at_accuracy": 0.0}

    records = []
    with open(golden_file, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    if limit:
        records = records[:limit]

    if not records:
        print("No extraction golden records found.")
        return {"field_f1": 0.0, "closing_at_accuracy": 0.0}

    total_f1 = 0.0
    total_closing_acc = 0.0

    for rec in records:
        actual = rec.get("actual", {})
        expected = rec.get("expected", {})
        metrics = compute_extraction_f1(actual, expected)
        total_f1 += metrics["field_f1"]
        total_closing_acc += metrics["closing_at_accuracy"]

    n = len(records)
    avg_f1 = total_f1 / n
    avg_closing_acc = total_closing_acc / n

    print(f"\n--- Extraction Eval ({n} samples) ---")
    print(f"Field F1: {avg_f1:.4f} (Target: >= 0.90)")
    print(f"Closing Date Accuracy: {avg_closing_acc:.4f} (Target: >= 0.98)")

    passed = avg_f1 >= 0.90 and avg_closing_acc >= 0.98
    print(f"Result: {'PASS' if passed else 'FAIL'}")

    return {"field_f1": avg_f1, "closing_at_accuracy": avg_closing_acc}


def run_qualification_eval(limit: int | None = None) -> dict[str, float]:
    golden_file = GOLDEN_DIR / "qualification.jsonl"
    if not golden_file.exists():
        print(f"Skipping qualification eval: {golden_file} not found.")
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    records = []
    with open(golden_file, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    if limit:
        records = records[:limit]

    if not records:
        print("No qualification golden records found.")
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    actuals = [r.get("actual_status", "") for r in records]
    expecteds = [r.get("expected_status", "") for r in records]

    metrics = compute_qualification_metrics(actuals, expecteds)

    print(f"\n--- Qualification Eval ({len(records)} samples) ---")
    print(f"Precision: {metrics['precision']:.4f} (Target: >= 0.90)")
    print(f"Recall: {metrics['recall']:.4f} (Target: >= 0.85)")

    passed = metrics["precision"] >= 0.90 and metrics["recall"] >= 0.85
    print(f"Result: {'PASS' if passed else 'FAIL'}")

    return metrics


def run_explanation_eval(limit: int | None = None) -> dict[str, float]:
    golden_file = GOLDEN_DIR / "explanation.jsonl"
    if not golden_file.exists():
        print(f"Skipping explanation eval: {golden_file} not found.")
        return {"grounded_ratio": 0.0}

    records = []
    with open(golden_file, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    if limit:
        records = records[:limit]

    if not records:
        print("No explanation golden records found.")
        return {"grounded_ratio": 0.0}

    grounded_count = 0
    for rec in records:
        explanation = rec.get("explanation", "")
        profile_facts = rec.get("profile_facts", [])
        tender_facts = rec.get("tender_facts", [])
        if check_explanation_grounding(explanation, profile_facts, tender_facts):
            grounded_count += 1

    ratio = grounded_count / len(records)
    print(f"\n--- Grounded Explanation Eval ({len(records)} samples) ---")
    print(f"Grounded Ratio: {ratio:.4f} (Target: 1.00 - zero unsupported claims)")
    print(f"Result: {'PASS' if ratio == 1.0 else 'FAIL'}")

    return {"grounded_ratio": ratio}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI Eval Harness")
    parser.add_argument(
        "--smoke", action="store_true", help="Run 20-sample smoke test for PR checks"
    )
    parser.add_argument(
        "--task",
        choices=["all", "extraction", "qualification", "explanation"],
        default="all",
        help="Task class to evaluate",
    )
    args = parser.parse_args()

    limit = 20 if args.smoke else None

    print(f"Running Eval Harness (smoke={args.smoke}, task={args.task})...")

    if args.task in ["all", "extraction"]:
        run_extraction_eval(limit)

    if args.task in ["all", "qualification"]:
        run_qualification_eval(limit)

    if args.task in ["all", "explanation"]:
        run_explanation_eval(limit)


if __name__ == "__main__":
    main()
