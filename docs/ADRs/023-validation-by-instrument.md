# ADR-023 — Validation by instrument, not by interview (G0 restated)

| | |
|---|---|
| **Status** | Proposed — founder decision required. Amends Master Plan §19 (G0) and §8 (persona casting rule); rewrites Doc 10 Phase 0 |
| **Date** | 2026-07-15 |
| **Context** | Founder directive: *"don't worry about interview cause we can get feedback after we published it using their feedback."* |

## The directive, taken seriously

The founder is right about the **defect in interviews** and wrong about the **replacement**. Both halves matter.

**Right:** G0 as written measures *stated* preference — "≥8/15 A1 say yes at $79." Stated willingness-to-pay is the weakest signal in startups. People are polite, hypothetical, and free with imaginary money. A room of enthusiastic yeses converts at single digits. Doc 10's own further-reading cites The Mom Test for exactly this reason, then specifies the instrument the book warns about.

**Wrong:** "publish, then use their feedback" **assumes an audience that does not exist yet.** ADERA today has no brand, no domain authority, no email list, no Telegram channel, no network in the diaspora. Publishing into that condition produces **silence**, and silence is unfalsifiable — it cannot distinguish "the product is wrong" from "nobody has heard of it." That is not a fast learning loop; it is a coin flip resolved at month 4 instead of week 2.

## Decision

**Replace G0's stated-preference instrument with revealed-preference instruments. Do not replace it with nothing.**

Validation stops being a *phase that blocks building* and becomes **a set of always-on instruments that run while the positioning-independent spine gets built**. The founder's instinct — start building — is honoured. The evidence requirement is not dropped; it is upgraded.

### The three instruments (all are pre-existing plan items, moved earlier)

| Instrument | What it measures | Why it beats an interview |
|---|---|---|
| **Eligibility-SEO guides** (§5 channel 1) — publish "Can a US company bid on Ethiopian government tenders?", "Diaspora guide to CPOs", "NCB vs ICB in Ethiopia" | Real search demand from strangers with intent, at zero acquisition cost | Nobody types a high-intent query to be polite. **SEO has a 3–6 month ranking lag — this is the load-bearing reason to start in Phase 1, not Phase 2** |
| **Priced landing page + waitlist** | Whether the $79 number survives contact with a real CTA | A click on a real price is behaviour; a nod in a call is not |
| **Telegram sector digest** (§5 channel 6) | A2 demand, measured by subscribers and retention | Free to run off the scraper the moment it works; a subscriber is a revealed preference |

### What G0 becomes

**Old G0:** ≥8/15 A1 at $79 AND ≥8/20 A2 at ETB 449 AND ≥10 facilitator LOIs AND a working payout — *before writing product code.*

**New G0 (evaluated ~Week 6–8, on data, while the spine is already built):**
- **G0-a — Global intent:** ≥300 organic sessions/mo to eligibility guides **AND** ≥25 waitlist signups **AND** ≥5 clicks on a $79 CTA. *(Falsifies the Engine-B thesis on behaviour.)*
- **G0-b — Local intent — SUPERSEDED (ADR-029, 2026-07-25):** was ≥150 Telegram digest subscribers with ≥40% week-4 retention, falsifying the Engine-A local-bidder wedge. ADR-029 retires Engine A as a demand hypothesis entirely, so this gate no longer measures anything live. The channel is proposed to be repurposed to measure facilitator/poster SUPPLY interest instead (recruitment inquiries, "list my firm" clicks) — not unilaterally decided; flagged for founder confirmation.
- **G0-c — Willingness to pay:** first paying subscriber by Week 9 (unchanged from Phase 2 DoD — this is now the real WTP gate, and it is made of money, not opinion).

**If G0-a and G0-b both fail:** the spine still has value (see below) — reposition the *demand side*, not the codebase.

## What this ADR does NOT permit

**Six of Phase 0's seven gates are not interviews and are unaffected. They stay, and three of them are urgent.**

| Gate | Status | Why it survives the directive |
|---|---|---|
| **G-PAY** | ⛔ **CANNOT be deferred. Week 1.** | Stripe-direct is *recorded impossible from Ethiopia* (ADR-016). If money cannot reach the founder, **no amount of demand matters** and every week of building is at risk. This is a $1 test, not a conversation. Skipping it is the single highest-severity error available in this project. |
| **G-NAME** | Week 1 | Domain + trademark clearance; known conflict risk with other Adera-named orgs. Cheap now, expensive after brand spend. |
| **G-LIC** | Start Week 1 (long lead) | eTrade registration is slow bureaucracy and gates the entire ETB rail. Starting it is free; needing it and not having it costs months. |
| **G-LAW** | Phase 1–2 | The law corpus **is** the differentiator (M16). Not research overhead — product input. |
| **G-TEAR** | Phase 1, opportunistic | Buying Getchereta's paid tier is competitive intel, not an interview. ~2,500 ETB. |
| **G-FAC** | Phase 3 (unchanged) | ≥10 facilitator LOIs. **Cannot be validated post-launch:** a marketplace with no facilitators cannot receive feedback about facilitators. If a diaspora bidder arrives and finds an empty marketplace, that lead is burned permanently. Recruitment is supply-building, not customer research. |

## Why building first is defensible here (the actual justification)

This ADR is only sound because of a specific property of the Phase-1 scope:

**The ingestion spine is positioning-independent.** Scraping e-GP → parsing → extraction → qualification → the eval harness has identical value under *every* surviving hypothesis — diaspora tool at $79, local SME tool at ETB 449, or data provider. **It is not a bet.** Building it before G0 resolves risks nothing, because no G0 outcome would cause you to throw it away.

The rule this generalizes to, which should govern every future phase:

> **Build what you would build under every hypothesis. Let the instruments run while you build it. Defer anything whose value depends on which hypothesis is true.**

What is therefore **still gated** and must not be pulled forward on enthusiasm: the facilitator marketplace, engagements, the fee model, escrow (already Phase-5/counsel-gated per ADR-020), and paid posting. Those *are* bets, and they resolve on G0/G-FAC.

## Consequence for the persona rule (§8)

Master Plan §8 binds: *"No product decision may cite a persona until it is cast with a named, consenting design partner interviewed in Phase 0."* With interviews dropped, no persona will be cast, so **the rule is not relaxed — it bites harder.** P1–P5 stay uncast, and therefore uncitable. Product decisions in Phase 1–2 must be justified by scraped data, measured instrument behaviour, or explicit founder judgment recorded as such — never by an imagined user's preferences. The ban on fictional stand-ins (§8) remains absolutely in force; dropping interviews makes inventing users *more* tempting, not less.

Design partners (§5 channel 5) are still recruited in Phase 2 — but from people the instruments attract, i.e. from revealed interest rather than cold outreach. This is strictly better recruiting, and it is the founder's directive working as intended.

## Honest cost of this decision

Not free. Recorded so it cannot be claimed later that it was:
- **~4 weeks of build precede any demand signal.** Interviews would have produced a (weak) answer in ~2 weeks with zero code. The trade is 4 weeks of positioning-independent work for higher-quality signal.
- **Instruments are slower than conversations.** SEO needs 3–6 months to rank; the Week 6–8 read will be *early and noisy*, not conclusive. Mitigation: the waitlist and Telegram signals arrive faster than SEO.
- **No qualitative "why."** Instruments say *whether*, never *why*. The first 5 design partners in Phase 2 must supply the "why" — that conversation is deferred, not cancelled.
- **Risk accepted:** if both G0-a and G0-b fail at Week 8, ~4 weeks were spent on a spine whose demand side needs rework. Bounded and survivable — the 20k plan (02 §2) covers it, and the spine survives repositioning.
