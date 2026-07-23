# Security brief — adera-api (cross-cutting)

*Read ONBOARDING.md first. This is your one-pager: the posture, where the real
risks live, and where to look on day one. The full threat model is
`docs/SECURITY.md` — read it before you pick your first task.*

## Why this product's threat model is unusual

ADERA **ingests untrusted documents as its core function** (scraped tender pages,
PDFs, later user uploads) and **feeds them to LLMs**. That makes prompt injection
a first-class, permanent threat — a tender PDF containing "ignore previous
instructions" must never steer the system. Add multi-tenancy (companies must never
see each other's matches), money (bid-bond amounts, payments), and **source-access
legitimacy** (do we have the right to hold this data at all — see below), and you
have the four risk pillars, in `docs/SECURITY.md` §3.

## There is a live, unresolved legal question waiting for you

The e-GP ingestion plan currently assumes logging in with the founder's own
credentials and driving Playwright. That may violate Ethiopia's **Computer Crime
Proclamation 958/2016** ("access in excess of authorization") —
`docs/ADRs/027-source-access-legality.md` (Status: **Proposed**) proposes never
authenticating to collect data, from anywhere, ever. It is not yet decided. This
is your Prompt A option in `docs/proposals/FIRST_TASK.md` and it is the single
most on-point task in this product for a cybersecurity background — genuine
computer-crime research, not a docs review.

## The standing doctrine (already enforced, verify don't trust)

1. **Untrusted-data posture (NFR-SEC-2):** every extraction prompt opens by
   declaring the document is data, never instructions — see `prompts/extract/v1.md`.
   Any new prompt must carry the same framing (recipe R4 in `docs/agents/SKILLS.md`).
2. **Tenant isolation (the fatal bug class):** every future authenticated endpoint
   declares `org = Depends(current_org)`; every tenant feature ships with a
   **two-org leak test**. Current public endpoints expose public tender facts only.
3. **Secrets & moat:** `.env` is gitignored; config only via `app/core/config.py`.
   The valuable data (tender corpus, law corpus) lives in Postgres + R2 object
   storage — **never in git**. Repo compromise ≠ data compromise.
4. **Money rules (future payments):** integer minor units, float lint-banned,
   double-entry ledger planned, webhook handlers must be replay-idempotent
   (NFR-MONEY-1/2). Payments/auth/billing are founder-review-mandatory.
5. **DB as enforcement layer:** constraints in Postgres, not just Python — e.g.
   enums get CHECK constraints via `pg_enum()` (a real bug we caught: the DB
   happily accepted `org_type='banana'` before it).
6. **Scraping conduct AND access authorization** — two different questions.
   Conduct: identified User-Agent, per-source rate limits, `robots.txt` honored
   (claimed but **not yet implemented** — a real gap, see `docs/SECURITY.md` G3).
   Authorization: whether we have the *right* to access a source at all —
   anonymous page reads, credentialed session automation, and public APIs are
   legally distinct acts (ADR-027) and must never be reasoned about as one thing.
   `sources.tos_status` currently only expresses the conduct question; ADR-027
   proposes a companion field for the authorization question.

## What CI enforces today vs. not yet

| Enforced now | Not yet (openings for you) |
|---|---|
| ruff `S` rules (bandit) on every PR | dependency audit (`pip-audit`) in CI |
| mypy strict (whole app) | secret-scanning hook (gitleaks) |
| enum/constraint regression tests | rate limiting on API routes |
| migrations-from-scratch check | authn/z design review (auth is unbuilt — get in early) |

Target bar: **OWASP ASVS Level 1** (NFR-SEC-1); Top-10-for-LLM-Apps is the lens
for everything in `app/kernel/` and `prompts/`.

## Day-1 reading path

`AGENTS.md` §4 (rules 8–9) → **`docs/SECURITY.md`** (the full threat model, 8
ranked gaps) → `docs/ADRs/027-source-access-legality.md` (the live legal
question) → `prompts/extract/v1.md` (injection framing) → `app/core/config.py` +
`.env.example` (secrets surface) → `tests/test_enum_policy.py` (DB-enforcement
pattern) → `app/kernel/budget.py` (spend breaker — DoS-by-bill protection). Then
`docs/proposals/FIRST_TASK.md` (Security track) for your actual first
deliverable — pick Prompt A (source-access legality) or Prompt B (threat model
+ CI gates).
