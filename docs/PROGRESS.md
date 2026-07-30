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
- [x] **Profile save now auto-triggers matching — built and proven live,
  2026-07-30 (second pass, same day).** Found live: the founder's own real
  account had a saved profile but zero matches, because nothing anywhere
  ever called `match_org()` automatically — the very first version of the
  profile endpoint shipped that gap. `PUT /api/v1/org/profile` now calls
  `match_org(session, org.id, kernel=build_kernel())` synchronously right
  after `upsert_profile()`, best-effort (a matching failure is logged, never
  fails the profile save; `AudienceRestricted` for local orgs is expected and
  silently skipped, matching the CLI demo's own behavior). Idempotent per
  (org, GROUP), so editing an already-matched profile again costs nothing
  extra. New test proves the actual behavior, not just that it doesn't
  break anything: `test_put_profile_automatically_triggers_matching` seeds a
  real qualified/embedded tender, PUTs a matching profile, and asserts a real
  `Match` row exists afterward via `GET /matches` — no separate endpoint or
  script involved. **Honest limitation, not fixed here:** still nothing
  re-runs matching for tenders ingested *after* a profile was last saved — a
  scheduled sweep is the real fix, out of scope for this pass.
- [x] `adera-web`: the profile-setup gate is now MANDATORY for bidder orgs
  (diaspora/foreign) — `AppGate` checks `GET /org/profile` and redirects any
  `/dashboard/*` visit to `/profile-setup` until one exists; local orgs are
  exempt (ADR-029, they never receive matching). Editing an existing profile
  afterward stays entirely optional. Real bug found and fixed in the same
  pass: without invalidating the gate's cached "no profile" query on save,
  the very next `/dashboard/*` visit re-read the stale cached result and
  bounced the user right back to `/profile-setup` even though the save had
  just succeeded — fixed with `queryClient.removeQueries(...)` on submit, not
  just `invalidateQueries` (which alone still serves stale data on the next
  mount under React Query's stale-while-revalidate default). Also added an
  "All Tenders" link to the dashboard header (`/tenders`, the existing public
  listing) — logged-in users previously had no way to browse beyond their
  matched subset. Known trade-off, not fixed: `/tenders` renders the public
  marketing chrome, not the dashboard header, so the nav visibly changes on
  that click.
- [x] **Profile HTTP endpoints (PRO-2/PRO-3) — built and proven live, 2026-07-30.**
  `GET/PUT /api/v1/org/profile` (`app/modules/profiles/router.py`) — the model
  and `upsert_profile()` service already existed (CLI-only, `seed-profiles`);
  this is the first time a real registered org can create/edit the profile
  `match_org()` runs against, closing the gap where every fresh signup was
  permanently stuck at an empty match feed. Two-org tenant isolation proven
  (`tests/test_profiles_tenant_isolation.py`). Real bug found and fixed while
  building this: `qualification/service.py::get_qualified_tender_ids` filters
  tenders by an exact string match on the LLM-freeform `Qualification.sector`
  field, and `ingestion/service.py::rank_by_embedding` treats an empty
  restrict-list as "match nothing," not "no restriction" — so a hand-picked
  sector chip list could silently and permanently empty a real org's match
  feed. Fixed with a new `GET /api/v1/tenders/sectors` (TEN-5) sourcing real
  distinct sectors from the qualified corpus instead
  (`qualification/service.py::list_qualified_sectors`) — proven live to return
  actual corpus phrasing (`"ICT / e-payment systems"`, not a guessed "ICT").
  **PRO-1 (LLM-drafts-chips-from-pasted-text) is explicitly deferred** — a
  separate, bigger feature (new prompt file, new kernel route, eval).
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
- [x] **Save/dismiss (MAT-2/MAT-3) — built and proven live, 2026-07-30.**
  `POST /api/v1/matches/{id}/save` and `/dismiss`
  (`app/modules/matching/router.py`, `service.py::save_match`/`dismiss_match`).
  `GET /matches?state=` now supports an exact-match filter (`new`/`saved`/
  `dismissed`), which is what makes a real "Saved" tab possible — previously
  the only client-side state was a `Set` that reset on reload. Save 409s
  `expired` for a tender whose *known* `closing_at` has passed; a null/unknown
  deadline (the common World Bank case) is never treated as expired. Dismiss
  has no expiry rule by design — a user must always be able to dismiss.
  4 new tests (`tests/test_matches_save_dismiss.py`): save-then-filterable,
  dismiss-never-resurfaces-in-default-feed, save-on-expired-is-409-but-dismiss-
  still-works, and a two-org 404 leak check. 118/118 tests pass.
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
- [x] **Eval harness — in CI, real but thin.** `evals/harness.py` + `evals/scorers.py`,
  golden sets under `evals/golden/` (1–3 rows each), `make eval-smoke` wired into
  `.github/workflows/ci.yml`. Ran clean this session (`uv run python -m
  evals.harness --smoke` → extraction/qualification/explanation all PASS). The
  gate exists; the golden sets are too small to have much teeth yet — growing
  them (Appendix C: "grow from every admin correction and user error-report")
  is real follow-up, not done. Previously listed as `[ ]` in this file in error.

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
- **ADR-030 (new, 2026-07-29): identity verification/vetting mechanism for all
  three org-facing actors** — bidder self-declaration (`org_type`), facilitator
  vetting (M14), poster KYB (M17). The master plan already decided *that* each
  actor needs checking and sketched a schema (Appendix A); nobody has decided
  *how* — what documents, what tooling, manual vs. vendor. Blocks Phase 3's own
  DoD (10 active facilitators, first KYB-verified posted tender). Not started.
- Whether `adera-mobile`'s offline/low-bandwidth investment still deserves the
  same priority now that its bidder audience is diaspora-abroad, not local SMEs
  on patchy Ethiopian data (see that repo's `docs/PROGRESS.md`).
