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
- **Threat-model review:** read `docs/team/BRIEF_SECURITY.md`, `prompts/extract/v1.md`
  (prompt-injection framing), `app/core/config.py` + `.env.example` (secrets
  surface), `tests/test_enum_policy.py` (DB-enforcement pattern). Propose the
  highest-value security additions to CI (e.g. `pip-audit`/dependency scanning,
  a secret-scanning hook) and where the current posture is weakest.
- Or: review the **auth design** *before* it's built (it's unbuilt and
  founder-review-mandatory) — sessions vs JWT, CSRF, tenant-isolation test strategy.

## What good looks like
Concrete, weighs alternatives, honest about tradeoffs, tied to a real FR/phase.
Not "we should add X" — *"here's X, here's why, here's the cost, here's what I'd
verify."* The founder reviews and either merges it as a decision of record or
promotes it to an ADR.
