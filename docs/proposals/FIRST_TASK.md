# Your first task (adera-api) — research, then a proposal PR. No code yet.

> **Tonight's team meeting (3–4 evening) is the deadline.** Before it: do the
> hands-on work below and bring your observations. **The proposal PR is not
> due tonight** — it follows, informed by what we decide together at the
> meeting. **If you only manage one thing, it's the item marked ★.**

Welcome. Before writing any code, spend time understanding the system and
bringing your thinking to the meeting. This also safely exercises our
branch → PR → tech-lead-approval flow on something low-risk, once the PR follows.

## Do this
1. **Read:** `docs/team/ONBOARDING.md` → `docs/SYSTEM.md` (how the 3 repos connect)
   → your brief (`docs/team/BRIEF_BACKEND.md` or `BRIEF_SECURITY.md`) →
   `docs/05_BACKEND_GUIDE.md` → `docs/PROGRESS.md` → skim `docs/00_MASTER_PLAN.md`.
2. **Run it:** `make install && make up && make migrate && make demo` — see real
   tenders and real matches. `make api` → open `/docs`.
3. **Proposal PR comes after the meeting** (`docs/proposals/`, copy `TEMPLATE.md`).

## Pick your research prompt

### Backend (Python / FastAPI) track — Temesgen

Read `docs/COMPETITORS.md` first — the competitive landscape (GetChereta,
2Merkato, AfroTender, EthiopianTender, e-GP, GlobalTenders/TendersOnTime),
**web products only**, and its hard boundary on how to research them.

- **★ Before tonight:** get the stack running (step 2 above) so you've *seen*
  real tenders and real matches, then spend an hour in the competitors' web
  products. Come to the meeting with an answer to the headline question below —
  it decides what the backend builds next, and it's not something one person
  should decide alone.
- **The headline question:** GetChereta already ships AI proposal drafting +
  win-rate prediction. AfroTender already ships historical win/price analytics.
  Our own v2 design (`05-win-brief.png`, in the client repos'
  `docs/design/v2/`) proposes essentially the same thing. Is that still our
  differentiator — and if so, *what specifically* makes ours better — or should
  we invest the backend elsewhere? Argue it either way; `docs/COMPETITORS.md`
  has the starting analysis, not the answer.
- **Competitive teardown, backend angle:** infer their engines from their web
  products. How does 2Merkato summarize at their volume? What data model would
  AfroTender need to answer "who won, at what price" — **do we even have that
  data?** (We ingest live notices; award-history is a different corpus
  entirely — this may be a real gap.) Where would GetChereta's win-prediction
  plausibly get its training signal?
- **RAG critique** — read `docs/06_RAG_AI_PIPELINE_GUIDE.md` and ADR-024
  (hand-rolled, staged). What's missing: chunking, reranking, the
  law-corpus/tender-corpus split, eval strategy?
- **API design review** — read `contracts/openapi.json` and
  `docs/11_API_REFERENCE.md`. What would you change *before* two clients
  generate against it and it gets expensive to change?
- **Multi-language reality check** — 2Merkato serves Amharic/Oromiffa/Tigrinya.
  Our extraction/embedding path is English-centric (BGE-M3 is multilingual, but
  nothing tests it on Amharic). What breaks first?
- **Architecture** — modular monolith (ADR-001), Celery io/cpu split, the
  kernel as the sole model door. What would you change, what would you keep?
- **Still real, still next:** the qualification prefilter (drop
  already-awarded/no-deadline noise before the LLM, FR-5.1/5.2) and the eval
  harness design (Appendix C).

### Security track — Eyasu

Read `docs/SECURITY.md` first either way — it's the canonical threat model and
both prompts below start from it. Pick one:

- **Prompt A — Source-access legality (the live, blocking problem; recommended).**
  ADERA's plan for e-GP (the primary tender source) currently assumes logging in
  with the tech lead's credentials and driving Playwright. That may violate
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
  and why (this makes the already-budgeted legal consult sharper and cheaper,
  not redundant — the legal *conclusion* still routes through counsel before
  it's the company's formal position, same as any security team's research
  feeds into, rather than replaces, legal sign-off).
- **Prompt B — Threat model + CI gates.** Review `docs/SECURITY.md` §4's gaps
  (G1-G8). Re-rank them by *real* risk, not ease of fix — say which you'd
  close first and why. Propose the CI additions you'd make (`pip-audit`, secret
  scanning, etc.) and what each actually buys. Flag anything wrong or missing in
  the threat model itself — it was written without a security professional's
  review, so it probably has errors.
- **Optional stretch (either prompt):** draft the *technical content* of a
  private, no-strings heads-up to PPA about a TLS certificate-chain issue found
  on their institutional domains — the tech lead decides whether/when to send it.
- **★ Before tonight:** read `docs/SECURITY.md`, pick a prompt, and bring your
  read on it to the meeting — a direction, not a finished proposal.

## What good looks like
Concrete, weighs alternatives, honest about tradeoffs, tied to a real FR/phase.
Not "we should add X" — *"here's X, here's why, here's the cost, here's what I'd
verify."* The proposal PR (after tonight) gets reviewed and either merged as a
decision of record or promoted to an ADR.
