# PROGRESS — adera-api (backend)

*The committed, team-facing status board for THIS repo's domain. Distinct from
`HANDOFF.md` (gitignored, agent working-memory). **Rule: update this file in the
same PR as the change it describes.** Every `[x]` cites evidence — a commit, a
test, or a command that proves it.*

**Updated:** 2026-07-25 · **Phase:** 1 (ingestion spine) done → deep into Phase 2.
Legend: `[x]` done · `[~]` in progress · `[ ]` not started · 🔑 blocked.

**This update corrects the previous version of this file, which under-reported its
own branch** — it still listed sector-wiring, the eval harness, and TZ-aware
digests as not-started while all three were already built in earlier commits on
the same chain. Fixed below; the `docs/PROGRESS.md` update-in-the-same-PR rule
(AGENTS.md rule 17) applies to this file matching reality, not just to new work.

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
- [x] **Qualified tenders' `sector` IS wired into ranking** — `match_org()`
  restricts candidates via `get_qualified_tender_ids(session, profile.sectors)`
  before embedding rank (`app/modules/matching/service.py`,
  `app/modules/qualification/service.py`). Previously listed as `[ ]` in this
  file in error — it landed in an earlier commit on this chain.

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
- [x] **TZ-aware digest scheduling — built, not yet SENDING.** `app/modules/notifications/`:
  `should_send_digest_now()` (zoneinfo, DST-correct), `record_notification()`
  (insert-then-send idempotency), hourly Celery Beat sweep
  (`notifications.send_digest_sweep`). **Honest gap: no email/Telegram sender
  exists** — the scheduling and no-duplicates spine works; nothing is actually
  delivered yet. Previously listed as `[ ]` in this file in error.
- [~] **Eval harness — exists, but the gate is DECORATIVE and cannot fail.**
  `evals/harness.py` + `evals/scorers.py`, golden sets under `evals/golden/`
  (1–3 rows each), `make eval-smoke` wired into `.github/workflows/ci.yml`.
  **This row previously claimed "real but thin" — that was too generous, and the
  2026-07-25 baseline disproved it.** The harness scores a **pre-recorded
  `actual` field stored inside the golden JSONL** against `expected` in the same
  row, and in every row of `evals/golden/*.jsonl` the two are byte-identical, so
  the score is pinned at 1.0 by construction. **It never calls a model** —
  `make eval-smoke` finishes in 381 ms with no network, which is also how CI
  passes this step while running `uv sync --frozen` *without* the `ai` extra
  (litellm is never imported). And `harness.py::main()` **never exits non-zero
  on FAIL**, so even a genuine failure would not break CI. Consequence: no claim
  about model quality anywhere in this repo is currently backed by this gate.
  Fixing it (invoke the model, exit non-zero, then grow the sets per Appendix C)
  is Phase 7 of the execution phase map.

## ADR-028 / ADR-029 — audience narrowing + cross-source dedupe (2026-07-25)

- [x] **ADR-029: consumer audience narrowed to diaspora/foreign.** Local orgs
  are supply-side only (facilitator/poster, Phase 3); the gate gate is
  `org_type == LOCAL` on the existing `org_type` field (`identity/service.py::
  require_bidder_audience`) — no new column. Enforced as a service-layer guard,
  not a query filter, so it can't be silently forgotten:
  - `matching.service.match_org()` raises `AudienceRestricted`, proven live —
    `make demo` prints `audience_restricted: local orgs don't receive AI
    matching (ADR-029)` for the one local demo profile kept specifically to
    prove the gate, while the other two (diaspora, foreign) still match normally.
  - `GET /api/v1/matches` 403s `audience_restricted` for a local org even
    without calling `match_org()` (it reads persisted rows directly) —
    `tests/test_matching_audience_gate.py`.
  - `eligibility.service.assess_eligibility()` raises before any retrieval or
    LLM call — `tests/test_eligibility_service.py::test_audience_restricted_for_local_org`.
  - `notifications.service.get_user_digest_items()` silently skips local orgs
    (a bulk sweep, not a client-facing call) — `tests/test_notifications_audience_gate.py`.
  - `POST /auth/register` response now carries `org` + `audience_note`
    (non-null, states plainly what a local org can't do) — new `RegisterOut`
    schema, contract regenerated. **Q&A (`POST /tenders/{id}/qa`) is NOT
    gated** — it has no auth at all yet (public, unquota'd), a pre-existing
    contract-shape gap; the audience gate will apply once auth lands there.
  - Self-selection (a local company registering as `diaspora`) is an accepted
    Phase-2 risk, not solved — recorded in the ADR, mitigated later by KYB.
- [x] **ADR-028: cross-source tender identity.** New `tender_groups` table
  (migration `a1c3e8f92b71`), `tenders.group_id` (NOT NULL, backfilled for
  pre-existing rows in the same migration). `find_or_create_group()`
  (`ingestion/service.py`) blocks on normalized buyer + `closing_at` within
  ±1 day against tenders from OTHER sources — **never** on title similarity,
  and never across a same-source re-advertisement with a different deadline
  (the founder's binding constraint, protected by construction: different
  deadlines fall outside the window, so they can never share a group).
  Conflicting deadlines within the window flag `has_conflict`, never silently
  pick one. Matching (`match_org`) and notifications
  (`make_idempotency_key`/`record_notification`) now key on `group_id`, not
  the raw tender row — a sibling tender from another source in an
  already-matched/already-notified group is never matched or notified again.
  **Proven live** against the real corpus: 60 World Bank + 266 e-GP tenders
  ingested, `distinct_groups == total_tenders` before and after a second
  idempotent ingest run (no drift). Honest gap: today's real corpus has zero
  cross-source overlaps to demonstrate an actual multi-source group forming
  (WB is 8/60 rows with any `closing_at` at all, mostly Contract Awards with
  none — nothing to block on safely most of the time, which is the *correct*
  fallback per ADR-028 step 1, not a bug) — the mechanism itself is proven
  against controlled fixtures in `tests/test_tender_grouping.py` and
  `tests/test_matching_group_dedup.py` (four and one test respectively,
  covering: two sources collapse to one group; same-source re-advertisement
  with a new deadline stays separate; a deadline conflict within the window
  flags `has_conflict` rather than merging silently; nothing-to-block-on never
  guesses a merge; two sibling tenders in one group produce exactly one
  persisted `Match`). Steps 3–4 (embedding similarity, LLM tie-break for the
  uncertain band) are explicitly deferred to a follow-up behind an eval set —
  not built, not claimed as built.
  Public contract: `TenderCard.also_listed_on[]` is a **planned, not-yet-built**
  addition (`docs/11_API_REFERENCE.md` TEN-1) — `group_id` exists on the row,
  nothing exposes it yet.
- [x] **Branch hygiene, landing the `feat/backend-core` chain.** Removed
  committed debris (`patch_ingestion.py`, `test_cookie*.py`) · fixed
  `notifications/service.py`/`tasks.py` import order (ruff `I`) · settled the
  rule-1 ruling (cross-module model-type imports go through the owning
  module's `service.py` re-export idiom — `AGENTS.md` §4.1) and applied it to
  `notifications`/`matching.router` · fixed a real pre-existing bug found
  running the suite on Windows (`tests/test_eligibility_ingest.py` read its
  UTF-8/Amharic fixture with no explicit encoding, failing under cp1252) ·
  closed two test-cleanup gaps that silently leaked `Source`/`Tender` rows on
  every green run (`test_matches_tenant_isolation.py` never deleted its
  `Source`; this session's own new `test_notifications_audience_gate.py` had
  the same gap on first draft, fixed before landing).
- [x] **Full verification, this session:** `make check` (ruff format + lint +
  mypy strict) green · migrations apply clean from scratch, including the new
  `a1c3e8f92b71` · **110/110 tests pass** · live ingest proven on both real
  sources (worldbank 60, egp 266; idempotent re-run `created=0`/`0`) ·
  `make eval-smoke` green (extraction/qualification/explanation all PASS) ·
  `make openapi` regenerated cleanly (the only diff is the deliberate
  `RegisterOut` shape change).

## Phase 0 — baseline re-verification (2026-07-25)

*First phase of the execution phase map. Verification only — no production code
touched. Every claim below is a command that was run, per rule 11.*

- [x] **Full green baseline re-established on a fresh database.** Migrations apply
  clean from an EMPTY volume, all 8 in order (`0001` → … → `a1c3e8f92b71`) — the
  real from-scratch proof, not `downgrade base` against a dirty local DB (the
  AGENTS.md §6 `down_revision` trap). `make check` green: ruff format (103 files),
  ruff check, **mypy strict on 76 source files**, 82 unit tests. `make test-int`
  green: 28 integration tests. **110/110 total.**
- [x] **Live ingest re-proven on both real sources, idempotency intact.**
  `worldbank` created=60 → re-run created=0/unchanged=60; `egp` created=263 →
  re-run created=0/unchanged=255. **323 real tenders.** The 11 `updated` rows on
  the e-GP re-run are the already-documented deadline-flip quirk, not a bug.
- [x] **ADR-028 conflict flagging has now fired on REAL data**, not just fixtures:
  `total_tenders=323`, `distinct_groups=323`, **`has_conflict=1`**. Still zero
  genuine cross-source overlaps in today's corpus (the honest documented gap), so
  the one flag most likely came through the e-GP deadline-flip UPDATE path —
  worth a look, but the mechanism erring toward "flag it" rather than silently
  picking a deadline is exactly the ADR-028 contract.
- [x] **The orphaned-path claim is now measured, not asserted.** On the freshly
  ingested real corpus: `parsed_docs=0 · classified_track=0 · embedded=0 ·
  qualified=0` (with `with_deadline=271`). Every one of 323 tenders reads
  `bidding_track='unknown'` because `classify_bidding_track()` is never called;
  `tender_documents` is empty because `documents.parse_tender_document` is never
  dispatched. This is the "before" measurement Phase 2 will be judged against.
- [x] **Two environment traps found and recorded** (both in `HANDOFF.md`, both
  durable enough for AGENTS.md §6): the local venv was **Python 3.14** while the
  project targets 3.12 (`mypy python_version`/`ruff target-version` both `py312`),
  and on 3.14 `uv sync --extra ai` fails outright because litellm 1.92 has no
  cp314 wheel and falls back to compiling a Rust/pyo3 bridge — nothing pins the
  interpreter in-repo, and **CI doesn't either**. And: an `OPENROUTER_API_KEY` in
  `.env` is **silently inert**, because `Settings` never declares the field and
  pydantic-settings does not export to `os.environ`, while `app/kernel/router.py`
  depends on litellm reading that env var itself — so the one value the kernel
  needs is the one value not flowing through `Settings` (rule 7).

## Phase 1 — security & edge gaps closed (2026-07-25)

- [x] **The admin API was unauthenticated. It no longer is.** `/api/v1/admin/run-ledger`
  and `/spend` (ADM-2, ADM-5) had **no auth dependency at all** — anyone with the
  URL read the run ledger and the AI spend figures. New `current_admin`
  (`app/core/deps.py`) finally reads `users.is_staff`, a column that had existed
  since the core schema with nothing consuming it. Declared as a **router-level**
  dependency, not per-route, so a future ADM-* endpoint added to that file cannot
  ship unguarded by forgetting an argument. **Proven live by curl, all three
  outcomes:** unauthenticated → `401 unauthenticated`; registered non-staff user →
  `403 forbidden` "staff privileges required"; then `UPDATE users SET is_staff=true`
  and **the same unchanged session cookie** → `200` with 4 real ledger rows and a
  real spend summary. That last step is the point: the 200 can only come from
  `is_staff` being re-read per request, not from anything cached in the cookie.
  Contract regenerated — the only diff is the two admin endpoints now declaring
  the session cookie parameter.
- [x] **Middleware `app/main.py` documented but never installed now exists.**
  - **CORS** with an explicit origin list from `settings.cors_origins`
    (comma-separated env var accepted). Wildcard is impossible here by spec:
    cookie auth means credentialed requests. `X-CSRF-Token` is in
    `allow_headers`, without which every unsafe browser request would fail at
    preflight rather than at the CSRF check. **Proven live:** preflight from
    `http://localhost:3000` returns `access-control-allow-credentials: true`
    and echoes the origin.
  - **Rate limiting** (`app/core/ratelimit.py`): Redis fixed-window counter,
    added first so it is outermost and rejects a flood before any router work.
    Returns the doc-11 shape — **429 + `application/problem+json` +
    `Retry-After`**. **Fails OPEN** on a Redis error: a limiter outage must not
    escalate into an API outage. `/healthz` and the docs are exempt so an uptime
    probe can't be throttled into a false alarm. **Proven live** with
    `RATE_LIMIT_PER_MIN=5`: requests 1-5 → 200, 6 and 7 → 429 with
    `retry-after: 7` and the correct RFC-7807 body; `/healthz` still 200 after.
  - `X-Forwarded-For` is only trusted when `TRUST_PROXY_HEADERS=true`, because
    trusting it unconditionally lets any client forge a fresh identity per
    request and walk around the limiter one header at a time.
- [x] **FR-2.5 is enforced instead of merely documented: robots.txt + per-source
  rate limits.** `sources.rate_limit_per_min` was a decorative column that
  nothing read. New `app/modules/ingestion/politeness.py` implements it as an
  **httpx transport** (`build_polite_client`), not a helper each adapter must
  remember to call — politeness an adapter can forget is politeness the project
  doesn't have. Every adapter is now gated with **zero changes inside
  `adapters/`**, including e-GP's paginated calls, and the same client backs
  `dry_run_source` (a dry run is still a real fetch). robots.txt is fetched once
  per host; **absent/unreadable robots.txt means allowed** — that is what the
  standard says, not a fail-open shortcut — while an explicit `Disallow` raises
  `RobotsDisallowed` so it lands in the run ledger rather than looking like a
  source with no new notices. The gate enforces even *spacing*, not a burst
  bucket: 20/min as a burst of 20 hits a source exactly as hard as no limit at
  all for that first second. **Proven live on real traffic:** e-GP's 6 paginated
  requests went from ~2.6s to **19.3s** — precisely the 3s spacing 20/min
  implies — and ingest remained correct and idempotent
  (`worldbank created=0/unchanged=60`, `egp created=0/unchanged=255`).
  *Ingestion is deliberately slower now; that is the FR-2.5 trade, not a regression.*
- [x] **The `Secure`-cookie trap that silently breaks browsers is fixed.**
  `_set_auth_cookies` hardcoded `secure=True`, so a real browser on
  `http://localhost` **never sends the session back** — while `curl` and httpx
  ignore the flag entirely, which is exactly why the auth flow could be proven
  live and still be unusable for the web/mobile developers. Now driven by
  `settings.cookie_secure`, which defaults to False **only** for `ENV=local` and
  stays True everywhere else, overridable via `COOKIE_SECURE`. Verified in the
  live curl cookie jar (`secure` column = `FALSE` under env=local) and pinned by
  `tests/test_cookie_secure_policy.py` — a policy test, because no HTTP client we
  verify with can observe the failure it prevents.
- [x] **Verification:** `make check` green (ruff format 108 files, ruff, mypy
  strict on 78 source files) · **126/126 tests pass (98 unit + 28 integration)**,
  up from 110 — 16 new: `tests/test_politeness.py` (7), `tests/test_ratelimit.py`
  (6), `tests/test_cookie_secure_policy.py` (3) — plus
  `test_runledger.py::test_runledger_admin_api_requires_staff`, which **replaces
  a test that had been asserting `200` for an unauthenticated admin call**, i.e.
  the suite was pinning the hole open. The rate limiter is disabled suite-wide by
  an autouse fixture (one shared client identity would otherwise make an
  unrelated test flake into a 429) and re-enabled deliberately in its own tests.

## Phase 2 (partial) — mobile contract alignment + MAT-2/3 (2026-07-25)

*Driven by `adera-mobile`'s backend-needs review. Its top three asks turned out
to be: one thing already done (the merge — auth/matches/search/Q&A have been on
`main` since `3ba327c`; the mobile repo's contract copy was simply three paths
stale), one thing that is ops rather than code (run the pipeline, see below),
and one real code gap — the contract does not admit that errors exist.*

- [x] **"RFC 7807 everywhere" was not true, on exactly the endpoints mobile
  calls most.** `GET /tenders/{id}` raised FastAPI's `HTTPException`, so a
  missing tender returned `{"detail":"tender not found"}` as
  `application/json` — a second error shape for clients to special-case, on the
  public read path. Now three handlers cover every route out of the app
  (`app/core/errors.py`): `APIError`, Starlette's `HTTPException` (also covers
  unrouted paths and wrong methods), and `RequestValidationError`. A 422 keeps
  its per-field detail as an RFC 7807 **extension member** (`errors`) rather
  than losing it to consistency. **Proven live:** `GET
  /api/v1/tenders/<unknown-uuid>` → `404 application/problem+json`
  `…/errors/not_found`; `GET /api/v1/tenders?limit=999` → `422
  application/problem+json` with `detail:"query.limit: Input should be less
  than or equal to 100"` and the full `errors` array.
- [x] **Errors are now declared in the contract, not just emitted.** A client
  generated from `contracts/openapi.json` could not model a single failure:
  `/matches` documented only 200 and 422, so ADR-029's `403
  audience_restricted` — a *named product state* in the mobile design — was
  invisible to codegen. New `problems()` helper + a `Problem` catalog mirroring
  docs/11 §0; `ProblemDocumentedFastAPI` publishes the shared `ProblemDetail`
  and `ValidationProblem` components and rewrites FastAPI's auto-generated 422s
  (which advertised `application/json` + `HTTPValidationError`, a shape this API
  no longer returns; both dead models are now dropped from the document so
  clients don't generate classes for them). `tests/test_problem_contract.py`
  pins document and wire together.
- [x] **MAT-2 / MAT-3 (save + dismiss) built** — the mobile Saved tab was
  client-local memory, which cannot keep FR-7.3's promise across devices.
  `POST /matches/{id}/save` and `/dismiss`, org-scoped, audience-gated, CSRF-
  required, returning the updated `MatchOut` (a superset of docs/11's
  `{state:…}`, so the card redraws without a refetch). Dismissal is a state
  change, never a delete: only a remembered row keeps a dismissed match from
  being re-ranked later. `GET /matches` gained the documented `state=new|saved`
  filter — and `MatchStateFilter` deliberately has no `dismissed` member, so no
  listing this endpoint offers can resurface one. **Proven live** end-to-end
  over HTTP with a real cookie jar (`scripts/proof_mobile_alignment.sh`): save
  → 200 `state:"saved"` → visible under `?state=saved`; dismiss → 200 → empty
  under all three listings while the row remains `dismissed` in Postgres;
  `?state=dismissed` → 422.
- [x] **`require_csrf` is a dependency now** (`app/core/deps.py`), not logic
  copy-pasted inside logout. Same reasoning as `current_org` for tenancy: the
  next unsafe endpoint should have to *remove* protection to be unprotected.
  Logout was refactored onto it; behavior unchanged, pinned by the existing
  auth-flow tests plus a new "write without CSRF is refused" case.
- [x] **`GET /auth/me` and `GET /matches` can no longer disagree about which
  org you are.** `/me` took the *first* membership row while every org-scoped
  route resolves through `current_org`; for a multi-org user `/me` named an org
  that `/matches` would then refuse to serve without `?org_id=`. `/me` now uses
  `current_org` too. **Tech-lead-review-mandatory (rule 14): this is an auth
  surface behavior change** — multi-org users now get `400 org_id_required`
  from `/me` instead of a silently arbitrary org. Single-org accounts (all of
  them today) are unaffected.
- [x] **`MatchOut.eligibility` is exposed** (FR-16.2). It is `unknown` on every
  row and will stay that way until M16 has a pipeline stage — which is exactly
  why it should be on the wire: mobile renders one of four chips, and an
  omitted field forces the client to hardcode a verdict it cannot justify.
- [x] **Verification:** `make check` green (ruff, mypy strict 78 files) ·
  **144/144 tests pass (111 unit + 33 integration)**, up from 126 — 13 new
  across `tests/test_problem_contract.py` (8, all pure-logic) and
  `tests/test_matches_save_dismiss.py` (5 integration: save round-trip,
  FR-7.3 never-resurfaces, CSRF refusal, cross-org 404 leak check, local-org
  403). Contract regenerated: 12 → 14 paths.
- [ ] **Not done, and it is the bigger mobile blocker:** the pipeline behind
  these endpoints has still never run past ingest (`parsed_docs=0 ·
  classified_track=0 · embedded=0 · qualified=0`, HANDOFF.md). Mobile can now
  wire auth, tenders, matches, save, and dismiss against a contract that tells
  the truth — but every AI-derived field it renders will be `unknown`, null, or
  an empty list until Phase 2's chain runs. `classify_bidding_track()` is
  deterministic and needs no API key; applying it would turn 323 tenders'
  `bidding_track` from `unknown` into real values, but storing FR-16.1's
  confidence + evidence alongside needs a migration on an existing table, which
  is founder-review-mandatory (R2 step 5) — so it was not done here.

## Reference material / open decisions landed this session (2026-07-23)
- [x] `docs/COMPETITORS.md` — GetChereta/2Merkato/AfroTender/EthiopianTender/e-GP landscape
- [x] `docs/QUALIFICATION_PREFILTER.md` — now documents a real, working
  implementation + Temesgen's open questions on it (not a blank problem
  statement anymore)

---

## What's next (the tech lead's build queue)
0. **Run the pipeline** (Phase 2's chain: ingest → parse → classify → embed →
   qualify → match). Everything mobile needs now exists as an endpoint; what it
   lacks is populated data. Cheapest first step with real user-visible payoff:
   `classify_bidding_track()` over the existing 323 tenders — deterministic, no
   API key — but decide first whether to add FR-16.1's confidence/evidence
   columns (migration on an existing table = your call, R2 step 5).
1. Extend the eligibility law corpus past Article 2 — the articles that
   actually govern bidder eligibility (bidding methods, nationality
   restrictions) aren't ingested yet; needs careful, non-rushed extraction.
2. AUTH-5/6 (verify-email, password-reset) — needs an email/Telegram delivery
   path first. Same blocker means the digest scheduler has nothing to send
   through yet either (item 3).
3. A real notification sender (Brevo/Resend for email, aiogram for Telegram) —
   the digest scheduling/idempotency spine is done and proven; nothing is
   actually delivered.
4. ADR-028 steps 3–4 (embedding-similarity + LLM tie-break for the uncertain
   dedup band) behind a labeled eval set — deliberately deferred this session.
5. `also_listed_on[]` on the public tender contract (TEN-1) — `group_id`
   exists, nothing exposes it yet; needed before the web/mobile card can show
   "also listed on e-GP, World Bank."
6. Confirm or reject the Telegram-channel repurposing proposed in ADR-029
   (local-bidder digest → facilitator/poster supply signal) — founder call,
   not decided by this session.
7. Temesgen's review of the qualification prefilter, Eyasu's review of
   ADR-027 (now with the e-GP public-API finding) — rework whatever their
   research says is wrong.
8. Growing the eval golden sets past 1–3 rows each — the CI gate exists but
   has little statistical teeth yet (Appendix C).

## Blocked on the founder
- ADR-027 resolution (security review of source-access legality; possibly a
  PPA data-sharing conversation) — the adapter itself is built and proven live
  (220+ e-GP tenders, public-API-only, no-login-ever rule enforced by
  construction); the review is about the ADR's `Proposed` status, not the code.
- ADR-029's Telegram-repurposing question (item 6 above).
- Whether `adera-mobile`'s offline/low-bandwidth investment still deserves the
  same priority now that its bidder audience is diaspora-abroad, not local SMEs
  on patchy Ethiopian data (see that repo's `docs/PROGRESS.md`).
