# Qualification prefilter

**Status:** A first implementation exists (`app/modules/qualification/`) — built
ahead of your research, at the tech lead's explicit direction, so it's a
working baseline rather than a blank page. **It is not final. Rework or
replace any part of it that your research says is wrong — that's still the
point of this task, not a formality.**
**Owner: Temesgen.**
**Requirements:** FR-5.1 (zero-cost keyword/rule prefilter first), FR-5.2 (LLM
qualification → `qualified`/`rejected`/`needs_review` + urgency + sector +
reasons + confidence; model + raw response persisted).

> Bring what you know from outside this repo: your experience, how you've
> solved this before, current practice. Reviewing and critiquing a real
> implementation is exactly as valuable as designing one from scratch — more,
> if you can find what's wrong with it.
>
> And this is one thing to review, not the only thing you can work on. If you
> see something more important, say so.

## What was actually built (verify all of this yourself — don't trust this file)

Two stages, cheapest first, in `app/modules/qualification/service.py`:

1. **Rule stage (free).** `_rule_reject(tender)` checks
   `tender.raw_data["notice_type"]` against a hardcoded reject set — currently
   just `{"Contract Award"}`. This was **not guessed**: verified against the
   real ingested corpus before writing any code —
   ```
   docker compose exec -T db psql -U adera -d adera -c \
     "select raw_data->>'notice_type', count(*), count(closing_at) from tenders group by 1;"
   ```
   gave 121/121 "Contract Award" notices with no `closing_at`, and 0/15 of
   every other notice type missing one. That correlation is the entire
   justification for the rule — it is a World-Bank-specific empirical fact,
   not a general principle, and it may not hold for other sources at all.
2. **LLM stage (prompt B2, `prompts/qualify/v1.md`)** for everything the rule
   didn't reject: `kernel.complete(task="qualify", schema=QualifyOut)` returns
   `status`/`urgency`/`sector`/`reasons`/`confidence`. A failure (bad JSON,
   rate limit, budget breaker) persists `NEEDS_REVIEW` with confidence 0 and a
   reason saying qualification failed — **never a guessed status**
   (AGENTS.md rule 11).

**Schema:** a new `qualifications` table (`app/modules/qualification/models.py`,
migration `677995c87c69`) — one row per tender, FK to `tenders`, updated in
place on re-run (not appended). Carries `method` (rule/llm, for cost
transparency), `model` + `raw_response` (FR-5.2's audit requirement — JSONB,
`none_as_null=True` set deliberately; see the comment on that column for a real
bug this caught), and `corrected_status`/`correction_note` as an unused landing
spot for FR-5.4's human-correction flow.

**CLI:** `uv run python -m app.cli qualify` runs it over every tender without a
verdict yet.

**Live-proven, not just tested:** run against the full real corpus (136
tenders): **121 rejected** (rule stage, matching the empirical count exactly),
**14 qualified**, **1 needs_review** (a genuinely ambiguous case — a 2027
closing date on a thin summary — not a failure; confidence 0.35 with real
reasoning). Two real bugs were found and fixed while proving this live, both in
`app/kernel/router.py` (repo-wide, not qualification-specific — see
`_strip_code_fence` and the `none_as_null` note above): a model response that
put commentary *after* a closing code fence broke the old fence-stripping
logic, silently turning 11/15 real verdicts into fake `NEEDS_REVIEW` failures
before the fix.

## Open questions — Temesgen closes these (unchanged from before, still real)

- [ ] **TODO(temesgen): does the rule stay this narrow?** One notice type, one
  source. Is there more free signal being left on the table, or is the current
  scope exactly right and anything broader is guessing?
- [ ] **TODO(temesgen): is the two-stage order right?** Rule-reject only
  (never qualify) vs. rule-flag-and-still-send-to-LLM vs. something else
  entirely — the current code hard-skips the LLM on a rule reject. Right call?
- [ ] **TODO(temesgen): is a single `qualifications` table the right shape**,
  or should this live differently (e.g. columns on `Tender` directly)? The
  current choice followed the existing `matches`-table pattern (own table, FK)
  rather than adding columns to `Tender` — worth challenging.
- [ ] **TODO(temesgen): how do you know it's working**, with no labeled data
  yet? The 14/121/1 split is a real run, not a golden-set evaluation — is that
  distinction being made clearly enough elsewhere (PROGRESS.md, eval harness)?
- [ ] **TODO(temesgen): what's missing entirely?** FR-5.3 (re-qualification on
  revision) has no trigger anywhere. FR-5.4 (the correction review queue) has
  schema fields and zero endpoint. Both are real gaps, not implemented, and not
  necessarily this task's job to close — but say so if either should move up.

## Where this fits

The qualification step sits between ingestion and matching — `matching/service.py`
still has no sector pre-filter wired in, so a qualified tender's `sector` field
isn't consumed by anything downstream yet. That wiring is also open. Write your
findings up as a proposal PR (`docs/proposals/`, copy `TEMPLATE.md`) — and if
your rework has architectural weight, it may deserve a full ADR in `docs/ADRs/`.
