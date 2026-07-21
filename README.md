# ADERA (አደራ)

**AI-native tender intelligence for Ethiopian public procurement.** ADERA ingests
tenders from e-GP, donor portals, and org sites; extracts structured fields; matches
them to company profiles with local embeddings; and explains *why this fits you* in
plain language. Later phases add an eligibility engine citing Ethiopian procurement
law and a vetted facilitator marketplace.

> Working on this repo (human or AI)? **Start with [`AGENTS.md`](AGENTS.md)** — the
> working contract — then `HANDOFF.md` (gitignored living state; recreate from
> AGENTS.md §9 on a fresh clone). Source of truth for requirements:
> [`docs/00_MASTER_PLAN.md`](docs/00_MASTER_PLAN.md).

## Quickstart

```bash
make install        # uv sync + .env from example
make up             # Postgres 16 + pgvector (:5435) and Redis (:6380)
make migrate        # apply migrations
make api            # http://localhost:8000/docs

# run the pipeline by hand:
DEBUG=false uv run python -m app.cli seed
DEBUG=false uv run python -m app.cli ingest worldbank   # real Ethiopian tenders
DEBUG=false uv run python -m app.cli tenders
```

`make check` = the CI gate (format, lint, mypy strict, unit tests).
`make test-int` = DB-backed tests (needs the stack up).

Ports are non-default (5435/6380) deliberately — see AGENTS.md §5.

## Architecture (ADR-001)

One Python 3.12 codebase, three process roles — `api` (FastAPI) · `worker` (Celery,
io/cpu queues) · `beat` (scheduler) — over one Postgres (+pgvector) and one Redis.
Modules under `app/modules/` talk through `service.py` interfaces only. All model
I/O goes through `app/kernel/` (LiteLLM router, versioned prompts, budget breaker,
content-hash cache). Frontend (Phase 2): Next.js 14.

```
fetch → parse → extract → upsert → prefilter → qualify → embed → match → notify
     every stage idempotent, retried, cost-metered in run_ledger
```

## Repository map

| Path | What |
|---|---|
| `app/core/` | settings, db, storage adapter, enum policy, mixins |
| `app/modules/<m>/` | one folder per master-plan module (models/schemas/service/router/tasks) |
| `app/kernel/` | the only door to any LLM/embedding model (ADR-014) |
| `prompts/<task>/vN.md` | versioned prompts — prompts are software (§14) |
| `migrations/` | Alembic (new models.py files MUST be imported in env.py) |
| `docs/` | master plan (source of truth), build guides 01–11, ADRs, agent docs |
| `design-reference/` | design bundle; implement from `docs/agents/DESIGN.md`, not the mocks |
| `templates/agentic-workflow/` | reusable context-engineering template for other projects |

## Status

Phase 1 (ingestion spine) in progress — see `HANDOFF.md` for verified current state.
