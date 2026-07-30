"""Celery configuration (ADR-005).

Two queues, one image, three roles (ADR-001):
  io  — network-bound: fetching pages/documents. High concurrency.
  cpu — OCR, embedding, parsing. Concurrency ~= cores, or they fight.

This split is what buys independent scaling and crash isolation WITHOUT
microservices (ADR-001 §3) — a runaway Playwright scrape cannot take the API down.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery("adera")

celery_app.conf.update(
    broker_url=str(settings.redis_url),
    result_backend=str(settings.redis_url),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",  # NFR-INTL-1: schedules reason in UTC, render local
    enable_utc=True,
    task_track_started=True,
    # Retry semantics (§12.2): every stage idempotent, retried x3, dead-lettered.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="io",
    task_queues={
        "io": {"exchange": "io", "routing_key": "io"},
        "cpu": {"exchange": "cpu", "routing_key": "cpu"},
    },
    # Every module with a tasks.py MUST be listed here — the worker only knows
    # tasks it imports. Forgetting this line is invisible at dispatch time
    # (.delay() happily queues the message) and fails only in the worker with
    # NotRegistered. Found the hard way; see AGENTS.md §6.
    imports=(
        "app.modules.ingestion.tasks",
        "app.modules.notifications.tasks",
        "app.modules.documents.tasks",
        "app.modules.matching.tasks",
    ),
    beat_schedule={
        "send-digest-sweep-hourly": {
            "task": "notifications.send_digest_sweep",
            "schedule": 3600.0,  # Run hourly sweep
        },
        "rerun-matching-sweep-hourly": {
            "task": "matching.rerun_sweep",
            "schedule": 3600.0,
        },
    },
)
