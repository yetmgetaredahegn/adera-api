---
name: verify
description: Verify an ADERA change end-to-end — static checks plus behavior proof against the live pipeline (CLI ingest/tenders, psql schema truth). Run before claiming any task done; required by AGENTS.md §7.5.
---

# Verify an ADERA change

Two levels. Both mandatory. Paste real output for each — a claim without command
output is not a verification.

## Level 1 — static (CI-equivalent)

```bash
make check          # ruff format --check, ruff, mypy strict, unit tests
```

If the change touched DB behavior:

```bash
make up && make migrate
make test-int
```

If the change touched migrations, also prove the from-scratch path CI runs:

```bash
uv run alembic downgrade base && uv run alembic upgrade head   # data is disposable in Phase 1
```

## Level 2 — behavior proof (pick every row that applies)

| Change touched | Prove it with |
|---|---|
| Ingestion / adapters | `DEBUG=false uv run python -m app.cli ingest <key>` **twice** → second run `created=0`; then `docker compose exec -T db psql -U adera -d adera -c "SELECT kind,status,items_created,items_unchanged FROM run_ledger ORDER BY started_at DESC LIMIT 2;"` |
| Schema / models | `docker compose exec -T db psql -U adera -d adera -c "\d <table>"` — constraints/types as intended (the ORM is not the schema; psql is) |
| API endpoints | `make api` → exercise via `curl` or `/docs`, paste status + body; `curl -s localhost:8000/healthz` still `{"ok":true,...}` |
| Enums | insert via Python, `SELECT` the raw column → lowercase **value** stored; garbage insert rejected by CHECK (see `tests/test_enum_policy.py`) |
| Tenant-scoped features | run the two-org leak test |
| Prompts / kernel | if no `ANTHROPIC_API_KEY` in env, the path is **built-but-unexercised** — report exactly that; never simulate model output |

## Level 3 — closeout

1. Update `HANDOFF.md`: verified state (+ evidence line), unexercised list, next step.
2. Report: built-and-proven vs built-but-unexercised vs assumed. No unverified "done".
3. Do NOT commit — standing founder instruction (CLAUDE.md).
