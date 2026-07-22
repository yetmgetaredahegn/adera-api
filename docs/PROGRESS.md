# PROGRESS — adera-api (backend)

*The committed, team-facing status board for THIS repo's domain. Distinct from
`HANDOFF.md` (gitignored, agent working-memory). **Rule: update this file in the
same PR as the change it describes.** Every `[x]` cites evidence — a commit, a
test, or a command that proves it.*

**Updated:** 2026-07-22 · **Phase:** 1 (ingestion spine) done → early Phase 2.
Legend: `[x]` done · `[~]` in progress · `[ ]` not started · 🔑 blocked.

---

## Foundations & Infra — Phase 1
- [x] Project scaffold (uv, ruff, mypy strict) — `chore: scaffold Python project`
- [x] Local stack: Postgres 16 + pgvector, Redis — `feat(infra)`; `make up`
- [x] Typed settings / async DB session / UTC mixins — `feat(core)`
- [x] Enum values + CHECK constraints enforced at the DB — `fix(core)`; `tests/test_enum_policy.py`
- [x] Alembic migrations, pgvector enabled — migrations apply clean in CI
- [x] CI: lint → mypy → migrations-from-scratch → tests → contract-drift — `.github/workflows/ci.yml`; `make check` green (12 tests)

## Ingestion — M2 · Phase 1
- [x] Source registry model + seed (WB enabled, e-GP disabled) — `feat(sources)`
- [x] Adapter contract + World Bank Ethiopia adapter — `feat(ingestion)`; `tests/test_worldbank_adapter.py`
- [x] Idempotent upsert on `(source, source_tender_id)` — `feat(ingestion)`; `tests/test_ingestion_idempotency.py`
- [x] Orchestration task + run ledger (counts/cost/latency) — `feat(runledger)`
- [x] **69 real Ethiopian tenders ingested, re-run duplicate-free** — `DEBUG=false uv run python -m app.cli ingest worldbank` (×2 → created=0)
- [ ] e-GP source (the primary one) — Phase 1/2 — 🔑 needs founder's e-GP login + Playwright
- [ ] Revision detection + re-notify on deadline change — Phase 2 (FR-2.6)

## Documents & Extraction — M3/M4 · Phase 1
- [x] Deterministic extraction for structured sources (WB) — `feat(extraction)`
- [~] LLM extraction path for unstructured sources — built, **🔑 unexercised (needs `ANTHROPIC_API_KEY`)**
- [ ] PDF fetch + OCR (Tesseract eng+amh) — Phase 4 (no source needs it yet)

## AI Kernel — Phase 1
- [x] Model router (LiteLLM), budget breaker, cache, prompt registry — `feat(kernel)`
- [x] Local BGE-M3 embeddings ($0/embed, CPU) — `feat(embeddings)`
- [x] Storage adapter (local/R2) — `feat(storage)`

## Matching — M6/M7 · Phase 1→2
- [x] Company profile model + embedding service — `feat(profiles)`
- [x] Semantic matching (vector similarity + floor) — `feat(matching)`
- [x] **Matching spike JUDGED GREEN** (3 profiles → correct, non-overlapping lists) — `make demo`
- [ ] LLM re-rank + grounded "why this fits you" (B3) — Phase 2 — 🔑 needs key
- [ ] Qualification prefilter (drop awarded/noise before matching) — Phase 2, **next up**

## Public API — M9 · Phase 2
- [x] `GET /api/v1/tenders` (keyset-paginated) + `GET /api/v1/tenders/{id}` — `feat(api)`; `tests/test_tenders_api.py`
- [x] OpenAPI contract published + CI drift gate — `feat(contracts)`; `make openapi`
- [ ] Auth (sessions/JWT) — Phase 2 — **founder-review-mandatory**; unblocks per-user endpoints for clients
- [ ] Per-org matches endpoint (needs auth + tenant isolation + two-org leak test) — Phase 2
- [ ] Tender-doc Q&A over SSE — Phase 3 — 🔑 needs key

## Eligibility & Notifications — later phases
- [ ] NCB/ICB classifier + eligibility chips v1 — Phase 2 (M16-lite)
- [ ] TZ-aware digests (email + Telegram) — Phase 2 (M8)
- [ ] Eval harness in CI (gates all AI work after it) — Phase 2, high priority

---

## What's next (the founder's build queue)
1. Qualification prefilter (improves what every client feed shows).
2. Eval harness in CI.
3. LLM explanations + extraction — **the moment an `ANTHROPIC_API_KEY` lands.**
4. Auth design → per-user matches (founder-review-mandatory).

## Blocked on the founder
- `ANTHROPIC_API_KEY` in `.env` → unblocks explanations + LLM extraction + Q&A.
- e-GP login → unblocks the primary tender source.
