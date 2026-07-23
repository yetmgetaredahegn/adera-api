# Your first task (adera-api) — research, then a proposal PR. No code yet.

Welcome. Before writing any code, spend your first day understanding the system and
giving the founder your thinking. This also safely exercises our
branch → PR → founder-approval flow on something low-risk.

## Do this
1. **Read:** `docs/team/ONBOARDING.md` → `docs/SYSTEM.md` (how the 3 repos connect)
   → your brief (`docs/team/BRIEF_BACKEND.md` or `BRIEF_SECURITY.md`) →
   `docs/05_BACKEND_GUIDE.md` → `docs/PROGRESS.md` → skim `docs/00_MASTER_PLAN.md`.
2. **Run it:** `make install && make up && make migrate && make demo` — see real
   tenders and real matches. `make api` → open `/docs`.
3. **Write a proposal** (`docs/proposals/`, copy `TEMPLATE.md`, open a PR).

## Pick your research prompt

### Backend (Python / FastAPI) track
- **Qualification prefilter** (the actual next build item): most World Bank notices
  are already-awarded contracts with no deadline — noise in the feed. Propose the
  design of a `qualification` step that drops them *before* the LLM, per
  FR-5.1/5.2. Pure-function keyword rules first, then LLM. What rules? What's the
  test strategy? (This is a real ticket — a strong proposal becomes your first
  build task.)
- Or: the **eval harness** design (how we test AI quality in CI, Appendix C).

### Security track
Read `docs/SECURITY.md` first either way — it's the canonical threat model and
both prompts below start from it. Pick one:

- **Prompt A — Source-access legality (the live, blocking problem; recommended).**
  ADERA's plan for e-GP (the primary tender source) currently assumes logging in
  with the founder's credentials and driving Playwright. That may violate
  Ethiopia's **Computer Crime Proclamation 958/2016** ("access in excess of
  authorization") — `docs/ADRs/027-source-access-legality.md` (Status:
  **Proposed**) records the concern and a proposed alternative, but it needs your
  research, not mine. Research what "in excess of authorization" has meant in
  Ethiopian practice; assess our *specific* access patterns against it
  (anonymous page fetch vs. credentialed session automation vs. public API are
  legally different acts — don't collapse them); bring the relevant precedent
  (`hiQ v. LinkedIn`, `Van Buren v. US`, `Meta v. Bright Data`) and say honestly
  how much weight foreign precedent deserves here. **Validate or demolish
  ADR-027** — it's `Proposed` precisely so you can argue with it. Deliver a
  recommendation with citations, plus exactly what you'd ask counsel to confirm
  and why (this makes the founder's already-budgeted legal consult sharper and
  cheaper, not redundant — the legal *conclusion* still routes through counsel
  before it's the company's formal position, same as any security team's
  research feeds into, rather than replaces, legal sign-off).
- **Prompt B — Threat model + CI gates.** Review `docs/SECURITY.md` §4's seven
  gaps (G1-G8). Re-rank them by *real* risk, not ease of fix — say which you'd
  close first and why. Propose the CI additions you'd make (`pip-audit`, secret
  scanning, etc.) and what each actually buys. Flag anything wrong or missing in
  the threat model itself — it was written without a security professional's
  review, so it probably has errors.
- **Optional stretch (either prompt):** draft the *technical content* of a
  private, no-strings heads-up to PPA about a TLS certificate-chain issue found
  on their institutional domains — the founder decides whether/when to send it.

## What good looks like
Concrete, weighs alternatives, honest about tradeoffs, tied to a real FR/phase.
Not "we should add X" — *"here's X, here's why, here's the cost, here's what I'd
verify."* The founder reviews and either merges it as a decision of record or
promotes it to an ADR.
