# PROGRESS — adera-api (backend)

*The committed, team-facing status board for THIS repo's domain. Distinct from
`HANDOFF.md` (gitignored, agent working-memory). **Rule: update this file in the
same PR as the change it describes.** Every `[x]` cites evidence — a commit, a
test, or a command that proves it.*

**Updated:** 2026-07-24 · **Phase:** 1 (ingestion spine) done → deep into Phase 2.
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
- [x] **e-GP source — built and proven live, public-data-only.**
  `app/modules/ingestion/adapters/egp.py`. Not the authenticated-Playwright
  path this row used to describe — that's still rejected under
  `docs/ADRs/027-source-access-legality.md`. Instead: e-GP's own public
  `/bids/all` page was loaded in a headless browser with NO credentials
  (never touched a login field) to observe its network calls, which revealed
  a real, unauthenticated JSON API backing it — confirmed with a bare `curl`,
  zero cookies, zero auth headers. **220 real e-GP tenders ingested** (
  `uv run python -m app.cli ingest egp`), idempotency re-verified (`created=0`
  on re-run). Two real data-shape bugs found live and fixed: `procuring_entity`
  sometimes arrives as a localized `{"am":..., "en":...}` object instead of a
  plain string; and the API itself returns slightly different field values
  (`submission_deadline` flipping between a real value and `null`) across
  near-consecutive calls on some tenders — a live-system quirk, not our bug,
  handled by the existing upsert UPDATE path. ADR-027 updated with this
  finding; still `Proposed`, still Eyasu's to validate or demolish.
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
- [x] **Auth (sessions/JWT) — built and proven live**, per explicit tech-lead
  direction (rule 14's review requirement, satisfied by that direction).
  `app/core/security.py` (argon2, itsdangerous-signed session cookies, CSRF
  double-submit, short-lived bot JWT) · `app/core/deps.py`
  (`current_user`/`current_org`, the tenant-isolation anchor) · new `sessions`
  table (migration `b8709aa823de`) · `app/modules/identity/router.py`:
  AUTH-1/2/3/4 (register/login/logout/me) live at `/api/v1/auth/*`. AUTH-5/6
  (verify-email, password-reset) NOT built — no email delivery path exists.
  RFC-7807 error shape via `app/core/errors.py`. Also fixed SECURITY.md gap
  **G1**: `SECRET_KEY` now rejects its known-insecure default at startup if
  `env=prod`. **Full flow proven live** via real `curl`: register → me (200)
  → matches (200, real query) → logout (204) → me again correctly 401s
  "session revoked or expired" — genuine server-side revocation, not a
  client-side cookie clear (proven by replaying the pre-logout cookie value
  explicitly in tests). Real trap found: cookies are `Secure`, so a real
  *browser* over plain HTTP silently won't send them back (though `curl`
  will) — relevant once web/mobile integrate locally without TLS.
- [x] **Per-org matches endpoint** — `GET /api/v1/matches`
  (`app/modules/matching/router.py`). Reads persisted `Match` rows (ranking
  itself, with its LLM call, happens out-of-request via `match_org()` —
  never synchronously per GET). Tenant isolation proven with a real two-org
  test: org A and org B each get a seeded match, org A's default (no
  `?org_id=`) call returns only its own, and an explicit cross-org
  `?org_id=<org B>` request 404s (never 403 — no confirming org B exists).
- [ ] Tender-doc Q&A over SSE — Phase 3 — 🔑 needs key (key now exists; not built)

## Eligibility & Notifications — later phases
- [x] **NCB/ICB classifier + eligibility chips v1 (M16) — real MVP built and
  proven live**, ahead of any assignment, same "build now, rework later"
  principle as qualification. `app/modules/eligibility/`: `LawChunk` model +
  vector retrieval (`retrieve_relevant_chunks`, mirrors
  `ingestion.rank_by_embedding`) + prompt B6 (`prompts/eligibility/v1.md`) +
  `assess_eligibility()` with **two refusal gates**: a retrieval-similarity
  floor (nothing relevant found → `unknown`, never guess) and a citation
  floor (a non-`unknown` verdict citing nothing real ingested is downgraded,
  not trusted). **Real law corpus seeded**: Article 2 (definitions) of the
  Federal Public Procurement and Property Administration Proclamation No.
  1333/2024, fetched from PPA's own official PDF (not a third-party copy),
  38 real definitions extracted + embedded (`uv run python -m app.cli
  seed-law`) — 2 of 40 raw regex matches were correctly DROPPED, not
  included garbled, after a live bug was found: those two swallowed an
  entire intervening Amharic block across a page boundary because their
  true terminator wasn't the plain `;` the parser expected. **Only Article 2
  is ingested — not the articles that actually govern bidder eligibility**
  (bidding methods, nationality-based participation rules); extending this
  needs careful, non-rushed extraction (a wrong citation is worse than none,
  NFR-LEGAL-1), so it's honest follow-up work, not claimed as complete.
  **Live proof, two real cases:** both correctly returned `verdict=unknown`
  with substantive reasoning naming real retrieved definitions (proving
  retrieval genuinely worked) while correctly refusing to guess eligibility
  the corpus doesn't yet support — exactly the NFR-LEGAL-1 behavior this was
  built to guarantee.
- [ ] TZ-aware digests (email + Telegram) — Phase 2 (M8)
- [ ] Eval harness in CI (gates all AI work after it) — Phase 2, high priority

## Reference material / open decisions landed this session (2026-07-23)
- [x] `docs/COMPETITORS.md` — GetChereta/2Merkato/AfroTender/EthiopianTender/e-GP landscape
- [x] `docs/QUALIFICATION_PREFILTER.md` — now documents a real, working
  implementation + Temesgen's open questions on it (not a blank problem
  statement anymore)

---

## What's next (the tech lead's build queue)
1. Extend the eligibility law corpus past Article 2 — the articles that
   actually govern bidder eligibility (bidding methods, nationality
   restrictions) aren't ingested yet; needs careful, non-rushed extraction.
2. Wire qualified tenders' `sector` into `matching/service.py`'s ranking.
3. Eval harness in CI — still nobody's.
4. AUTH-5/6 (verify-email, password-reset) — needs an email/Telegram delivery
   path first.
5. Temesgen's review of the qualification prefilter, Eyasu's review of
   ADR-027 (now with the e-GP public-API finding) — rework whatever their
   research says is wrong.

## Blocked on the founder
- ADR-027 resolution (security review of source-access legality; possibly a
  PPA data-sharing conversation) → unblocks the primary tender source. Not the
  same blocker as before — see `docs/SECURITY.md` and `docs/ADRs/027-*`.
