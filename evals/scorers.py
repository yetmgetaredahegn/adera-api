"""AI Eval Harness Scorers (Master Plan Appendix C, 06 §9).

Implements scoring logic for:
- C1: Extraction field-F1 and closing_at accuracy.
- C2: Qualification status precision and recall.
- C3: Explanation grounding checks.
"""

from typing import Any

_STOPWORDS = frozenset(
    {
        "about",
        "above",
        "across",
        "after",
        "again",
        "along",
        "already",
        "also",
        "always",
        "among",
        "another",
        "around",
        "because",
        "before",
        "behind",
        "below",
        "between",
        "beyond",
        "company",
        "could",
        "direct",
        "directly",
        "during",
        "every",
        "first",
        "fits",
        "further",
        "handles",
        "having",
        "inside",
        "into",
        "itself",
        "might",
        "other",
        "others",
        "out",
        "over",
        "procurement",
        "should",
        "since",
        "still",
        "their",
        "there",
        "these",
        "they",
        "thing",
        "things",
        "this",
        "those",
        "through",
        "under",
        "until",
        "which",
        "while",
        "would",
        "your",
        "tender",
        "tenders",
    }
)


def compute_extraction_f1(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
    """Compute field-level F1 and closing_at accuracy (C1)."""
    total_fields = 0
    matched_fields = 0

    for key, exp_val in expected.items():
        if key.startswith("_"):
            continue
        total_fields += 1
        act_val = actual.get(key)

        if act_val == exp_val:
            matched_fields += 1
        elif isinstance(act_val, str) and isinstance(exp_val, str):
            if act_val.strip().lower() == exp_val.strip().lower():
                matched_fields += 1

    precision = matched_fields / len(actual) if actual else 0.0
    recall = matched_fields / total_fields if total_fields else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    closing_match = 1.0 if actual.get("closing_at") == expected.get("closing_at") else 0.0

    return {
        "field_precision": precision,
        "field_recall": recall,
        "field_f1": f1,
        "closing_at_accuracy": closing_match,
    }


def compute_qualification_metrics(
    actual_list: list[str], expected_list: list[str]
) -> dict[str, float]:
    """Compute qualification precision and recall across a batch of verdicts (C2)."""
    if not expected_list:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for act, exp in zip(actual_list, expected_list, strict=False):
        if act == exp:
            if act == "qualified":
                true_positives += 1
        else:
            if act == "qualified":
                false_positives += 1
            elif exp == "qualified":
                false_negatives += 1

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 1.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 1.0
    )
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


def check_explanation_grounding(
    explanation: str, profile_facts: list[str], tender_facts: list[str]
) -> bool:
    """Check that explanation contains zero unsupported claims (C3)."""
    if not explanation:
        return False

    context = " ".join(profile_facts + tender_facts).lower()
    words = [
        w.strip(".,!?;:()")
        for w in explanation.lower().split()
        if len(w) > 3 and w.strip(".,!?;:()") not in _STOPWORDS
    ]

    if not words:
        return True

    matches = sum(1 for w in words if w in context)
    ratio = matches / len(words)
    return ratio >= 0.70
