# ADERA (አደራ)

**AI-native tender intelligence for Ethiopian public procurement.** ADERA ingests
tenders from e-GP, donor portals, and org sites; extracts structured fields; matches
them to company profiles with local embeddings; and explains *why this fits you* in
plain language. Later phases add an eligibility engine citing Ethiopian procurement
law and a vetted facilitator marketplace.

## This repo is `adera-api` — one of three (polyrepo, ADR-025)

| Repo | Contents | Language | Status |
|---|---|---|---|
| **`adera-api`** (this repo) | API + pipeline workers + scheduler + canonical docs | Python 3.12 · FastAPI · Celery | **built** (Phase 1) |
| `adera-mobile` | mobile app | Flutter/Dart | starting (hackathon) |
| `adera-web` | web app (SEO pages + authenticated app) | Next.js 14 · TS | Phase 2 |

Why three repos: the stacks share **zero code** (Python/Dart/TS) and have separate
release trains (server deploy vs app stores) — only the **API contract** crosses.
Clients are **generated** from [`contracts/openapi.json`](contracts/openapi.json)
(regenerate with `make openapi`; CI blocks drift). The moat (law corpus, tender
data) lives in Postgres + R2, **never in git**; secrets live in `.env` (gitignored).
Full analysis: `docs/ADRs/025-repo-strategy-polyrepo.md`. Team onboarding:
[`docs/team/ONBOARDING.md`](docs/team/ONBOARDING.md).

## Start here — by what you're doing

- **Backend / FastAPI (from Django too):** this README → [`docs/05_BACKEND_GUIDE.md`](docs/05_BACKEND_GUIDE.md) (has a Django→FastAPI map) → [`docs/agents/SKILLS.md`](docs/agents/SKILLS.md) (step-by-step recipes)
- **AI / pipeline / prompts:** [`docs/06_RAG_AI_PIPELINE_GUIDE.md`](docs/06_RAG_AI_PIPELINE_GUIDE.md) → `app/kernel/` → `prompts/`
- **Frontend (Phase 2):** [`docs/07_FRONTEND_GUIDE.md`](docs/07_FRONTEND_GUIDE.md) → [`docs/agents/DESIGN.md`](docs/agents/DESIGN.md) (design tokens + components)
- **AI agent (any model):** [`AGENTS.md`](AGENTS.md) is the working contract; `HANDOFF.md` (gitignored) is the live state
- **Requirements / the "why":** [`docs/00_MASTER_PLAN.md`](docs/00_MASTER_PLAN.md) is the source of truth; [`docs/00_INDEX.md`](docs/00_INDEX.md) is the reading order

## Quickstart

```bash
make install        # uv sync + .env from example
make up             # Postgres 16 + pgvector (:5435) and Redis (:6380)
make migrate        # apply migrations
make api            # http://localhost:8000/docs

# run the pipeline by hand (the admin dry-run surface until the UI exists):
DEBUG=false uv run python -m app.cli seed
DEBUG=false uv run python -m app.cli ingest worldbank   # real Ethiopian tenders
DEBUG=false uv run python -m app.cli tenders
make demo           # embed + match 3 demo profiles, print the judgment sheet
```

`make check` = the CI gate (format, lint, mypy strict, unit tests).
`make test-int` = DB-backed tests (needs the stack up).
Ports are non-default (5435/6380) on purpose — the n8n prototype owns 5432/6379 (AGENTS.md §5, §13).

## Architecture (ADR-001)

One Python 3.12 codebase, three process roles — `api` (FastAPI) · `worker` (Celery,
io/cpu queues) · `beat` (scheduler) — over one Postgres (+pgvector) and one Redis.
Modules under `app/modules/` talk through `service.py` interfaces only. All model
I/O goes through `app/kernel/` (LiteLLM router, versioned prompts, budget breaker,
content-hash cache).

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
| `migrations/` | Alembic (new `models.py` files MUST be imported in `env.py`) |
| `tests/` | pytest (unit + `@pytest.mark.integration` for DB-backed) |
| `contracts/` | the published OpenAPI spec — what client repos generate from |
| `docs/team/` | onboarding package + per-role briefs (mobile/web/backend/security) |
| `docs/` | master plan (source of truth), build guides 01–11, `ADRs/`, `agents/` |
| `design-reference/` | design bundle; implement from `docs/agents/DESIGN.md`, not the mocks |
| `infra/` | deployment (prod compose, Caddy) — Phase 1 §9 |
| `templates/agentic-workflow/` | reusable context-engineering template for other projects |

## Status

Phase 1 (ingestion spine) in progress — Weeks 1–3 built and verified. See `HANDOFF.md`
for the current verified state, the honest built-but-unexercised list, and what's next.
