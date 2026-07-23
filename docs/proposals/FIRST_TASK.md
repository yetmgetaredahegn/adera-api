# Your first task (adera-api) — research, then a proposal PR. No code yet.

Welcome. Before writing code, understand the system, look hard at what else
exists in this market, and give me your own read on it. This also safely
exercises our branch → PR → review flow on something low-risk.

**Timing:** we're building ADERA at the Cursor hackathon in 2 days, and there's
a team meeting tonight (3–4 evening). Bring your direction to the meeting — a
paragraph is fine. The written proposal follows tonight or tomorrow.

## Do this

1. **Understand our product.** `docs/team/ONBOARDING.md` → `docs/SYSTEM.md`
   (how the 3 repos connect) → your brief (`docs/team/BRIEF_BACKEND.md` or
   `BRIEF_SECURITY.md`) → `docs/05_BACKEND_GUIDE.md` → `docs/PROGRESS.md` →
   skim `docs/00_MASTER_PLAN.md`.
2. **Run it.** `make install && make up && make migrate && make demo` — real
   tenders, real matches. `make api` → open `/docs`.
3. **Study the competition yourself.** `docs/COMPETITORS.md` is a starting
   point, not the research. Go use the actual products (web versions —
   GetChereta, 2Merkato, AfroTender, EthiopianTender, e-GP). Read that doc's
   access boundary first.
4. **Compare.** Where are we better, where are we worse, what are we missing,
   what are they doing that we haven't thought about?
5. **Form your own view**, then write it up: a proposal PR (`docs/proposals/`,
   copy `TEMPLATE.md`).

## Pick your research prompt

### Backend (Python / FastAPI) track — Temesgen

- **Where should we differentiate?** Given what competitors already ship, what
  should the backend actually invest in — and what should we not bother
  competing on? This is genuinely open; I don't have the answer.
- **The award-history question.** Some competitors answer "who won, at what
  price." That needs a corpus we may not have — or may already be ingesting
  without realising (a lot of what we pull from the World Bank *is* award
  data). Worth finding out, because it changes what's possible.
- **Qualification prefilter** — a first implementation now exists
  (`app/modules/qualification/`, built ahead of your research so there's
  something real to react to, not a blank page). `docs/QUALIFICATION_PREFILTER.md`
  has what was built, why, and the open questions it left — review it, verify
  the claims yourself, and rework whatever your own judgment says is wrong.
  Real next build item (FR-5.1/5.2), and it decides what every client's feed shows.
- **RAG critique** — `docs/06_RAG_AI_PIPELINE_GUIDE.md` + ADR-024. Chunking,
  reranking, the law-corpus/tender-corpus split, eval strategy. What's weak?
- **API design review** — `contracts/openapi.json` + `docs/11_API_REFERENCE.md`.
  What would you change *before* two clients generate against it?
- **Multi-language reality** — 2Merkato serves Amharic/Oromiffa/Tigrinya. Our
  pipeline is English-centric and nothing tests Amharic. What breaks first?
- **Architecture** — modular monolith (ADR-001), Celery io/cpu split, kernel as
  the only model door. Keep, change, or challenge?
- **Eval harness** — how we test AI quality in CI (Appendix C).

### Security track — Eyasu

Read `docs/SECURITY.md` first either way — it's the canonical threat model and
both prompts start from it. Pick one:

- **Prompt A — Source-access legality (the live, blocking problem; recommended).**
  Our plan for e-GP (the primary tender source) currently assumes logging in
  with my credentials and driving Playwright. That may violate Ethiopia's
  **Computer Crime Proclamation 958/2016** ("access in excess of
  authorization") — `docs/ADRs/027-source-access-legality.md` (Status:
  **Proposed**) records the concern and an alternative, but it needs your
  research, not mine. Research what "in excess of authorization" has meant in
  Ethiopian practice; assess our *specific* access patterns against it
  (anonymous page fetch vs. credentialed session automation vs. public API are
  legally different acts — don't collapse them); bring relevant precedent
  (`hiQ v. LinkedIn`, `Van Buren v. US`, `Meta v. Bright Data`) and say honestly
  how much weight foreign precedent deserves here. **Validate or demolish
  ADR-027** — it's `Proposed` precisely so you can argue with it. Deliver a
  recommendation with citations, plus exactly what you'd want a lawyer to
  confirm.
- **Prompt B — Threat model + CI gates.** Review `docs/SECURITY.md` §4's gaps
  (G1–G8). Re-rank them by *real* risk, not ease of fix — say which you'd close
  first and why. Propose the CI additions you'd make (`pip-audit`, secret
  scanning, etc.) and what each actually buys. Flag anything wrong or missing in
  the threat model itself — it was written without a security professional's
  review, so it probably has errors.
- **Optional stretch:** draft the *technical content* of a private, no-strings
  heads-up to PPA about a TLS certificate-chain issue on their institutional
  domains — I decide whether/when to send it.

## This is a starting point, not a boundary

These prompts are a heads-up on what I already know needs deciding — not the
limit of what you can work on. If your research surfaces something more
valuable, or you spot work we've missed entirely, propose that instead. Bring
knowledge from outside this repo: your experience, other systems you've built,
current practice. Nobody here has the full picture.

## What good looks like

Concrete, weighs alternatives, honest about tradeoffs, tied to a real FR/phase.
Not "we should add X" — *"here's X, here's why, here's the cost, here's what I'd
verify."* Disagreeing with something in these docs, with evidence, is exactly as
valuable as confirming it. I review and merge; strong proposals get promoted to
a real ADR.
