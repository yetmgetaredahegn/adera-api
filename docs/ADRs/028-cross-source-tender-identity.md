# ADR-028 — Cross-source tender identity: cluster, never merge

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-25 |
| **Decision** | A new `tender_groups` table represents one real-world opportunity. Every `tenders` row (one per source) points at a group. Matching, notifications, the feed, and slugs operate on groups, never on raw source rows. Grouping is additive and reversible: no source row is ever deleted or rewritten to "become" another. |

## Context

`Tender` is unique on `(source_id, source_tender_id)`
(`app/modules/ingestion/models.py:50`), and `upsert_tender` looks up existing rows by
exactly that pair. This guarantees **re-scraping one source never duplicates** — the
claim `docs/04_ARCHITECTURE_SYSTEM_DESIGN.md:18` makes. It says nothing about **two
sources publishing the same real-world tender**, which is now a live condition: e-GP
(`app/modules/ingestion/adapters/egp.py`) and the World Bank Ethiopia portal both carry
donor-funded Ethiopian projects, and nothing stops the same opportunity landing as two
independent `tenders` rows, each with its own matches, paid LLM explanation, and
notification.

No requirement in the master plan covers this. FR-17.5 ("dedupe against scraped corpus")
is anti-scam checking for *posted* tenders, a different problem with a different owner.
This ADR fills the gap for scraped ingestion.

**Why it matters, concretely:**
- Two or three cards for one opportunity is the category-dump experience ADERA exists to
  replace (master plan §1).
- FR-8.4's no-double-send key is `(user, tender, channel, event)` — a second `tender_id`
  for the same opportunity defeats it outright; a bidder gets the same tender emailed
  twice.
- Matching (FR-7.2) and the eligibility engine (M16) both call the LLM per tender row —
  a duplicate is a duplicate cost, not just a duplicate card.
- When sources disagree on `closing_at`, today both are shown silently. FR-4.4 exists
  specifically because a wrong deadline can cost someone a bid; an *unflagged conflict*
  between two sources is the same failure wearing a different hat.
- Corpus counts (a KPI, master plan §7) currently overstate real opportunity volume by
  however many tenders are cross-listed.

## The founder's constraint (binding on this design)

**Same source, same bid, posted again with a different timeline is a distinct
opportunity — never merge those.** A re-advertised tender with a pushed-back deadline is
a genuine second chance to bid, not noise to collapse away. This is not an edge case to
special-case; it must fall out of the grouping rule itself, or the design is wrong.

## Decision

### 1. Cluster, never merge

Every source row is kept exactly as fetched, forever — this is what FR-2.3's audit trail
and re-extraction guarantee already require, and grouping must not weaken it. A new
`tender_groups` row represents one real-world opportunity; `tenders.group_id` points at
it. A tender from a single source is a group of one — there is no special case for
"ungrouped."

### 2. Matching two rows — cheapest signal first, blocking before similarity

1. **Free, exact:** normalized reference/bid number + normalized buyer, where a source
   publishes a reference number. Immediate group match, no further check needed.
2. **Free, blocking:** candidates must share a normalized buyer **and** a `closing_at`
   within ±1 day of each other before anything else is compared. This is where the
   founder's constraint is enforced mechanically: two postings from the *same* source
   with *different* deadlines fall into different blocks by construction, so they can
   never reach the same group — re-advertisement is structurally protected, not
   special-cased.
3. **Already paid for:** cosine similarity on the existing tender embedding — **only
   between candidates that already passed step 2's block.** Similarity alone is
   rejected as a first-pass signal: it will happily score two distinct
   road-construction tenders in the same region as near-duplicates. Blocking first,
   similarity second, is the only order that avoids that failure.
4. **LLM, only for the uncertain band** inside a block — same discipline as
   qualification (FR-5.2): unsure goes to a review queue, never auto-merged.
5. **Never group across `bidding_track`** — a lookalike ICB and NCB notice are legally
   different opportunities (M16), independent of textual similarity.

**This ADR accepts steps 1–2 plus the review queue as the shipped scope.** Steps 3–4
(embedding similarity, LLM tie-break) are deferred to a follow-up PR gated by a labeled
eval set — a dedupe accuracy claim is exactly the kind of claim Appendix C's harness
exists to check, not something to ship on a demo.

### 3. Conflict handling

When two sources in the same group disagree on `closing_at`, the group carries a
`has_conflict` flag and both values, never a silent pick. **FR-4.4 extends: a group with
an unresolved deadline conflict is never notified**, exactly as a low-confidence
`closing_at` is never notified today. A `source_precedence` ordering (e-GP authoritative
for Ethiopian government deadlines; the originating donor portal for donor-funded rules)
resolves which fact displays by default, but the conflict stays visible, not erased.

### 4. What operates on groups vs. rows

Matching, notifications, the public feed, and slugs (once assigned, see the open slug
gap in `docs/11_API_REFERENCE.md`) all key on `group_id`. The tender detail page still
shows every source row inside the group ("also listed on: e-GP, World Bank") — clustering
must never hide which sources actually carry the opportunity.

## Rejected alternatives

- **Merge-on-write (overwrite the earlier row with the later source's data)** — destroys
  FR-2.3's audit trail and the re-extraction guarantee; also makes the founder's
  same-source-different-timeline case impossible to get right, because there would be
  nothing left to distinguish a re-advertisement from an update.
- **Single canonical source, others discarded** — throws away real information (e-GP and
  a donor portal often carry different authoritative facts for the same tender) and
  removes the audit trail entirely.
- **Hash-only matching (title + buyer text hash)** — cheap, but blind to the founder's
  constraint: a same-source re-post with a new deadline often has near-identical title
  and buyer text, so a naive hash would incorrectly collapse it. Rejected for exactly the
  case this ADR is built to protect.
- **Similarity-first (embed everything, threshold, done)** — rejected per step 3 above;
  it is the design that produces false merges across genuinely distinct opportunities.

## Consequences

**Gained:** one card per real opportunity; notifications and paid LLM calls fire once per
opportunity, not once per listing; deadline conflicts become visible facts instead of
silent inconsistencies; the founder's re-advertisement case is protected by construction,
not by a special-cased exception that could later be "cleaned up" away.

**Accepted:** grouping adds one more table and one more join to matching/notifications;
steps 3–4 (similarity, LLM tie-break) are explicitly deferred, so cross-source dedupe
recall is incomplete at launch — documented as a known gap, not claimed as solved.

## Reversal condition

If ingestion ever narrows to a single live source, grouping degenerates to one group per
tender at zero cost and can be left in place rather than reversed.
