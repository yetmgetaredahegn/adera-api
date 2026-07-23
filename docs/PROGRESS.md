# PROGRESS — adera-api (backend)

*The committed, team-facing status board for THIS repo's domain. Distinct from
`HANDOFF.md` (gitignored, agent working-memory). **Rule: update this file in the
same PR as the change it describes.** Every `[x]` cites evidence — a commit, a
test, or a command that proves it.*

**Updated:** 2026-07-23 (evening) · **Phase:** 1 (ingestion spine) done → early Phase 2, moving fast.
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
- [ ] e-GP source (the primary one) — Phase 1/2 — 🔒 blocked on `docs/ADRs/027-source-access-legality.md`
  (Proposed): authenticated scraping may violate Proclamation 958/2016. Blocked
  on security review + possibly an official PPA data-sharing agreement, **not**
  on Playwright engineering time.
- [ ] Revision detection + re-notify on deadline change — Phase 2 (FR-2.6)

## Documents & Extraction — M3/M4 · Phase 1
- [x] Deterministic extraction for structured sources (WB) — `feat(extraction)`
- [x] LLM extraction path for unstructured sources — **live, proven** via
  `OPENROUTER_API_KEY` — real synthetic tender doc → correct `TenderExtraction`
  (fields, TZ-aware dates, integer-minor-unit money). Two kernel bugs found +
  fixed in the process (`max_tokens` cap; OpenRouter markdown-fence stripping) —
  see `app/kernel/router.py`, `HANDOFF.md`.
- [ ] PDF fetch + OCR (Tesseract eng+amh) — Phase 4 (no source needs it yet)

## AI Kernel — Phase 1
- [x] Model router (LiteLLM), budget breaker, cache, prompt registry — `feat(kernel)`
- [x] Local BGE-M3 embeddings ($0/embed, CPU) — `feat(embeddings)`
- [x] Storage adapter (local/R2) — `feat(storage)`

## Matching — M6/M7 · Phase 1→2
- [x] Company profile model + embedding service — `feat(profiles)`
- [x] Semantic matching (vector similarity + floor) — `feat(matching)`
- [x] **Matching spike JUDGED GREEN** (3 profiles → correct, non-overlapping lists) — `make demo`
- [x] **LLM re-rank + grounded "why this fits you" (B3) — live, proven.**
  `match_org()` now takes an optional `kernel`; `_explain()` in
  `app/modules/matching/service.py` builds a grounded prompt from confirmed
  profile facts + extracted tender fields, calls `kernel.complete(task="explain")`,
  and persists `explanation`/`prompt_version` on new matches only (never
  re-explains an existing match — budget discipline). `make demo` run live:
  24/24 new matches got a grounded explanation, verified in Postgres
  (`select count(explanation) from matches` = 24) and Redis
  (`kernel:spend:2026-07-23` = $0.058586 for the run). Quality is real, not
  cherry-picked — one explanation correctly told a software company a water-
  supply tender was a poor fit rather than forcing a positive spin. A model
  failure (bad JSON, rate limit, budget breaker) returns `None`, never a faked
  explanation (AGENTS.md rule 11).
- [x] **Qualification prefilter (M5, FR-5.1/5.2) — built and proven live.**
  Two stages in `app/modules/qualification/`: a free rule stage
  (`_rule_reject`) rejects World Bank "Contract Award" notices — verified
  empirically first, not assumed: 121/121 awards in the real corpus have no
  `closing_at`, 0/15 non-award notices lack one. Everything the rule doesn't
  reject goes to an LLM stage (prompt B2, `prompts/qualify/v1.md`) for the
  real `status`/`urgency`/`sector`/`reasons`/`confidence` judgment. New
  `qualifications` table (migration `677995c87c69`), CLI:
  `uv run python -m app.cli qualify`. **Run against the full real corpus:
  121 rejected, 14 qualified, 1 needs_review** (a genuinely ambiguous case,
  not a failure — confidence 0.35 with real reasoning about a suspicious
  2027 closing date). Two real bugs found + fixed while proving this live,
  both in `app/kernel/router.py` (repo-wide fixes, not qualification-only —
  see HANDOFF.md): the fence-stripping helper broke on trailing commentary
  after a closing fence (was silently turning 11/15 real verdicts into fake
  failures before the fix); a JSONB column stored Python `None` as the JSON
  literal `null` instead of SQL `NULL` (`none_as_null=True` fixes it).
  Built ahead of Temesgen's research at the tech lead's explicit direction —
  `docs/QUALIFICATION_PREFILTER.md` documents exactly what exists and the
  open questions he still owns; not a design he must accept as-is.
- [ ] Qualified tenders' `sector` isn't consumed downstream yet —
  `matching/service.py` still has no sector pre-filter wired in. Real next
  wiring task, not started.

## Public API — M9 · Phase 2
- [x] `GET /api/v1/tenders` (keyset-paginated) + `GET /api/v1/tenders/{id}` — `feat(api)`; `tests/test_tenders_api.py`
- [x] OpenAPI contract published + CI drift gate — `feat(contracts)`; `make openapi`
- [ ] Auth (sessions/JWT) — Phase 2 — **tech-lead-review-mandatory**; implementation
  plan proposed (not built) in `docs/proposals/001-auth-implementation-plan.md` —
  session cookie + CSRF for web, JWT for the bot, per the architecture already
  decided in the master plan. Rule 14 forbids implementing this without review.
- [ ] Per-org matches endpoint (needs auth + tenant isolation + two-org leak test) — Phase 2
- [ ] Tender-doc Q&A over SSE — Phase 3 — 🔑 needs key

## Eligibility & Notifications — later phases
- [ ] NCB/ICB classifier + eligibility chips v1 — Phase 2 (M16-lite)
- [ ] TZ-aware digests (email + Telegram) — Phase 2 (M8)
- [ ] Eval harness in CI (gates all AI work after it) — Phase 2, high priority

## Reference material / open decisions landed this session (2026-07-23)
- [x] `docs/COMPETITORS.md` — GetChereta/2Merkato/AfroTender/EthiopianTender/e-GP landscape
- [x] `docs/QUALIFICATION_PREFILTER.md` — now documents a real, working
  implementation + Temesgen's open questions on it (not a blank problem
  statement anymore)

---

## What's next (the tech lead's build queue)
1. Review `docs/proposals/001-auth-implementation-plan.md` — the actual next
   unblock (per-org matches endpoint waits on it).
2. Wire qualified tenders' `sector` into `matching/service.py`'s ranking.
3. Eval harness in CI — still nobody's.
4. Per-org matches endpoint, once auth lands.
5. Temesgen's review of the qualification prefilter — rework whatever his
   research says is wrong.

## Blocked on the founder
- ADR-027 resolution (security review of source-access legality; possibly a
  PPA data-sharing conversation) → unblocks the primary tender source. Not the
  same blocker as before — see `docs/SECURITY.md` and `docs/ADRs/027-*`.
