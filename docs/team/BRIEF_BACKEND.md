# Backend brief — FastAPI (adera-api)

*Read ONBOARDING.md first. This is your one-pager. Coming from Django? You'll be
productive fast — `docs/05_BACKEND_GUIDE.md` §3 maps every concept.*

## The system in five lines

One Python 3.12 codebase, **three processes from one image**: `api` (FastAPI) ·
`worker` (Celery, io/cpu queues) · `beat` (scheduler) — over one Postgres 16
(+pgvector for embeddings) and one Redis. The pipeline:
`fetch → parse → extract → upsert → qualify → embed → match → notify`,
every stage idempotent and cost-logged in `run_ledger`.

## Django → here (the 30-second map)

| Django | Here |
|---|---|
| `settings.py` | `app/core/config.py` (pydantic-settings; `os.getenv` elsewhere is a bug) |
| app | module: `app/modules/<name>/{models,schemas,service,router,tasks}.py` |
| `Model.objects...` | explicit `session` + `select(...)` — no global manager |
| `urls.py`+views | `router.py` (`@router.get`), mounted in `app/main.py` |
| DRF serializer | Pydantic schema (also the LLM output contract!) |
| `makemigrations` | `make revision m="..."` — **but** new `models.py` MUST be imported in `migrations/env.py` or the migration is silently empty |
| `INSTALLED_APPS` trap | same trap twice here: `migrations/env.py` imports AND `celery_app.py` `imports=` |

## The five laws (each one guards a real past bug — details in `AGENTS.md` §4/§6)

1. Cross-module imports go through `service.py` only — never another module's models.
2. All LLM/embedding calls go through `app/kernel/` — never a provider SDK directly.
3. Money = integer minor units + currency column. Floats are lint-banned.
4. Time = UTC in storage (`DateTime(timezone=True)`), localized at render.
5. Enums via `pg_enum()` from `app/core/enums.py` — plain `sa.Enum` stores the
   member NAME and skips the CHECK constraint (bit us; test-pinned).

## Daily commands

```bash
make install && make up && make migrate     # stack on :5435/:6380 (NOT default ports — see AGENTS §5)
make api                                    # localhost:8000/docs
make check                                  # THE gate: format+lint+mypy strict+tests — green before any PR
make test-int                               # DB-backed tests
DEBUG=false uv run python -m app.cli ingest worldbank   # run the real pipeline
make demo                                   # matching judgment sheet (real tenders)
```

## Where to start coding

Pick a recipe from `docs/agents/SKILLS.md` (add-a-source is the flagship — one
adapter file + registry row + fixture tests). Never freehand what a recipe covers.

## Definition of done (any change)

`make check` green + **behavior proof** (run the actual thing, paste output) +
update `HANDOFF.md`. A claim without command output is not a claim here.
