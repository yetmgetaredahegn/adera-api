"""Prompt registry (ADR-014, §14 "prompts are versioned software").

Prompts live on disk at prompts/<task>/v<N>.md, never inline in code. Loading by
(task, version) means an explanation can always be traced back to the exact text
that produced it, and a prompt change is a reviewable diff with an eval attached.
"""

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


class PromptNotFound(FileNotFoundError):
    pass


@lru_cache
def load_prompt(task: str, version: str) -> str:
    path = PROMPTS_DIR / task / f"{version}.md"
    if not path.exists():
        raise PromptNotFound(f"no prompt at {path}")
    return path.read_text(encoding="utf-8")


def latest_version(task: str) -> str:
    """Highest vN present for a task, e.g. 'v2'. Lets callers pin or float."""
    task_dir = PROMPTS_DIR / task
    versions = sorted(
        (p.stem for p in task_dir.glob("v*.md")),
        key=lambda s: int(s[1:]) if s[1:].isdigit() else -1,
    )
    if not versions:
        raise PromptNotFound(f"no prompts under {task_dir}")
    return versions[-1]
