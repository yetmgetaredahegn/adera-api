"""Pins _strip_code_fence's behavior — found via a real live failure: a
qualification response wrapped JSON in a fence AND appended trailing prose
after the closing fence, which the previous (last-line-only) stripping logic
did not handle, producing a ValidationError that silently degraded a real
verdict to NEEDS_REVIEW. See app/kernel/router.py for the full story."""

from app.kernel.router import _strip_code_fence


def test_strips_bare_fence_with_nothing_after() -> None:
    raw = '```json\n{"a": 1}\n```'
    assert _strip_code_fence(raw) == '{"a": 1}'


def test_strips_fence_with_trailing_commentary_after() -> None:
    # The exact failure mode observed live (qualification, real OpenRouter call).
    raw = '```json\n{"a": 1}\n```\n\n**Note:** some trailing prose the model added.'
    assert _strip_code_fence(raw) == '{"a": 1}'


def test_strips_fence_with_leading_prose_before() -> None:
    raw = 'Sure, here is the JSON:\n```json\n{"a": 1}\n```'
    assert _strip_code_fence(raw) == '{"a": 1}'


def test_passes_through_bare_json_with_no_fence() -> None:
    raw = '{"a": 1}'
    assert _strip_code_fence(raw) == '{"a": 1}'


def test_strips_unlabeled_fence_not_just_json_labeled() -> None:
    raw = '```\n{"a": 1}\n```'
    assert _strip_code_fence(raw) == '{"a": 1}'
