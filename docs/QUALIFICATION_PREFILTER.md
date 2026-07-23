# Qualification prefilter — open problem

**Status:** Open. No design decided. **Owner: Temesgen.**
**Requirements:** FR-5.1 (zero-cost keyword/rule prefilter first), FR-5.2 (LLM
qualification → `qualified`/`rejected`/`needs_review` + urgency + sector +
reasons + confidence; model + raw response persisted).

> This file states the problem and the facts around it. It does **not** propose
> a solution — that's the work, and it's yours. Bring what you know from outside
> this repo: your experience, how you've solved this before, current practice.
> This is deliberately incomplete, not a quiz with a hidden answer key.
>
> And this is one thing that needs deciding, not the only thing you can work on.
> If you see something more important, say so.

## The problem

`app/modules/matching/service.py` currently ranks every ingested tender with no
qualification step at all — its own docstring says so ("No sector pre-filter
yet: tenders don't carry a sector until qualification (M5, Week 4) assigns one").

Meanwhile a large share of what we ingest isn't biddable. Most World Bank
procurement notices are **contract awards** — records of a contract already
given to someone — not open solicitations. They typically have no
`closing_at`. Surfacing them in a "here's what to bid on" feed is noise at
best, misleading at worst.

Nothing decides which tenders are worth showing. That's the gap.

## Facts you'll need (verify them; don't trust this file)

- **What exists in the kernel:** `app/kernel/router.py` already has a `qualify`
  route (cheap model tier) and a `MAX_TOKENS["qualify"]` cap. Nothing calls it.
  There is no `prompts/qualify/` directory yet.
- **What data is available to filter on:** `app/modules/ingestion/models.py`
  `Tender` carries `closing_at`, `title`, `summary`, and `raw_data` — the full
  original adapter payload as JSONB, GIN-indexed. The World Bank adapter
  (`app/modules/ingestion/adapters/worldbank.py`) maps `notice_type` into
  `summary` and keeps everything in `raw_data`.
- **Real data to look at, rather than guess from:**
  ```
  docker compose exec -T db psql -U adera -d adera -c \
    "select raw_data->>'notice_type', count(*) from tenders group by 1 order by 2 desc;"
  ```
- **Nearest test patterns:** `tests/test_worldbank_adapter.py` and
  `tests/test_ingestion_idempotency.py` — fixture-based, no live network.
- **Related requirement:** FR-5.4 (review queue; corrections become golden
  labels) suggests the design should assume human correction exists eventually.

## Open questions — Temesgen closes these

- [ ] **TODO(temesgen): what actually distinguishes biddable from not?** Decide
  from real ingested data, not from assumption. Which fields carry the signal?
- [ ] **TODO(temesgen): rules, model, or both — and in what order?** FR-5.1 and
  FR-5.2 describe both a rule pass and an LLM pass. Whether both are needed, and
  which runs first, is a design decision with real cost implications. Yours.
- [ ] **TODO(temesgen): what does the filter output?** A hard drop, a flag, a
  score, a status column? This affects the schema and what `matching` consumes.
- [ ] **TODO(temesgen): how do you know it's working?** A rule that's too
  aggressive silently drops real biddable tenders — invisible, and worse than
  showing noise. What's the measurement approach with no labeled data yet?
- [ ] **TODO(temesgen): what's the honest scope for right now** versus what
  follows later?

## Where this fits

The qualification step sits between ingestion and matching. Whatever you decide
here changes what every client's feed shows, so it's worth deciding
deliberately. Write it up as a proposal PR (`docs/proposals/`, copy
`TEMPLATE.md`) — and if the design turns out to have architectural weight, it
may deserve a full ADR in `docs/ADRs/`.
