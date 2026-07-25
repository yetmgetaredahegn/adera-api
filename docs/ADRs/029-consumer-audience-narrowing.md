# ADR-029 — Narrow the consumer audience to diaspora + foreign; local becomes supply-side only

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-25 |
| **Decision** | ADERA's paying bidder audience is **diaspora and foreign companies only**. Ethiopian-owned local companies are never AI-bidder customers; they participate only as **vetted facilitators** (M14/M15) and **verified tender posters** (M17). Amends master plan §1, §2.2, §4.1, §8 (P5), §10 (M7/M8/M16 audience scope). §12 is not edited in place; this ADR is the record. |

## Context

The master plan (v2.1) runs two demand engines: **Engine A — Local** (Ethiopian SMEs,
"retained v1 wedge", ETB-priced) and **Engine B — Global** (diaspora + foreign, USD-priced,
"primary monetization", §1). This ADR retires Engine A as a *demand* engine. Local
companies remain fully in the product — as the two supply sides the plan already
specifies (facilitators, posters) — but never as a consumer of AI matching, eligibility
verdicts, digests, or tender Q&A.

## Decision

> ADERA's paying consumer is a **diaspora or foreign** company. Ethiopian-owned local
> companies are **supply side**: vetted facilitators and KYB-verified tender posters.
> They do not receive AI matching, fit explanations, eligibility verdicts, digests, or
> tender Q&A.

### The gate uses the existing schema — no new column

`orgs.org_type ∈ {local, diaspora, foreign}` and `orgs.country`
(`app/modules/identity/models.py:43-53`) already mean different things: **`country` is
where the company is registered; `org_type` is its relationship to Ethiopia** (FR-1.6).
The gate is `org_type == LOCAL` → no bidder features, full stop. This has one immediate,
worth-stating-explicitly consequence: **a diaspora-owned company registered inside
Ethiopia stays `org_type = diaspora`.** It remains a full paying customer, and it
additionally has domestic NCB standing that a purely foreign bidder lacks — a genuine
selling point (§2.1's "diaspora... explicit policy push for participation"), not an edge
case to special-case away.

### Capability matrix

| Capability | `local` | `diaspora` / `foreign` |
|---|---|---|
| Register, log in, manage org | ✅ | ✅ |
| Browse public tender pages (public data, FR-9.1) | ✅ | ✅ |
| AI matching + "why this fits you" (M7) | ⛔ | ✅ |
| Eligibility verdicts + checklists (M16) | ⛔ | ✅ |
| TZ-aware digests / instant alerts (M8) | ⛔ | ✅ |
| Tender Q&A | ⛔ | ✅ |
| Apply as facilitator (M14) | ✅ (Phase 3) | ⛔ |
| Post a tender, after KYB (M17) | ✅ (Phase 3) | — |

Because M14/M17 are Phase 3, a local org registering **today** gets an account and public
browsing and nothing else. The registration response must say this plainly
(`docs/11_API_REFERENCE.md` AUTH-1) — a local org signing up to a silent empty feed is
indistinguishable from a bug, and that failure mode is worse than an honest "not yet."

### Enforcement is a service-layer guard, not a query filter

`match_org()`, the eligibility service, the notification digest sweep, and the Q&A
endpoint each check `org.org_type` **before** doing any work and raise/return
**`403 audience_restricted`** (new RFC-7807 code, `docs/11_API_REFERENCE.md` §0) for a
local org — never an empty list. An empty list is silent and looks like "no matches
today"; a 403 with a named reason is the only version a client can render correctly and
the only version that can't rot into a silent, undetected feature gap.

### Accepted risk: self-selection

Nothing today stops a local company registering with `org_type=diaspora` — this is a
soft gate until KYB (M17, Phase 3) exists as the harder verification path for the
*supply* side, and there is no equivalent hard check for the *demand* side because the
plan never anticipated needing one. **Recorded as an accepted Phase-2 risk, not solved
here.** If it proves material before Phase 3, the mitigation is either a lightweight
company-registry cross-check at registration or restricting the self-declared `org_type`
by verified domain/country signals — a decision for whoever owns Phase 3 KYB work, not
pre-empted by this ADR.

## Consequences

### Pricing (§4.1)

Local Free / Local Pro (ETB 449) / Local Business (ETB 1,499) are removed as **consumer**
tiers. Consumer billing needs only the USD rail (Global Free / Global Pro $79 / Global
Business $249). **This materially de-risks ADR-016** (Stripe-direct impossible from
Ethiopia; MoR or intl-card PSP for USD) by removing the need to stand up a second rail
for consumers on day one.

**This does NOT retire G-LIC.** G-LIC (eTrade business registration, unlocking any live
NBE-regulated local rail) is still required for **facilitator ETB payouts** (M15,
FR-15.5) and **ETB tender-posting fees** (M17, FR-17.3) — both supply-side money flows
that are untouched by this ADR. Anyone reading "no more ETB consumer pricing" must not
conclude the ETB rail itself is now optional.

### Unit economics (§4.3)

The "ten Global Pro + five Local Pro ≈ $760+/mo" line loses its Local Pro component.
Break-even is unchanged: **one Global Pro subscriber** ($79 → ~$72 net) — it never
depended on Local Pro.

### Validation gates (ADR-023, §19)

**G0-b** ("≥150 Telegram digest subscribers with ≥40% week-4 retention") was built to
falsify the Engine-A local-bidder wedge. That wedge no longer exists as a demand
hypothesis, so G0-b as written measures a hypothesis this ADR has already resolved.
**Recorded here as repurposed, not retired**, pending the founder's confirmation: the
Telegram channel and its instrumentation are cheap to keep running and can instead
measure **facilitator/poster supply interest** (recruitment inquiries, "list my firm"
clicks) — a real Phase-3 input. This ADR does not unilaterally decide the repurposing;
it flags the inconsistency G0-b now has with §2.2 and leaves the decision open.

### Personas (§8)

**P5 — Local SME bid manager (A2)** retires as a bidder persona. P3 (facilitator) and P4
(poster) become the local-side personas going forward. The binding casting rule is
unchanged and unrelaxed: no product decision may cite P1–P4 until cast with a real,
consenting, interviewed person (§8) — this ADR does not cite any of them; it is argued
from the schema and the existing plan text alone.

### Eligibility (M16) is unaffected in kind, only in audience

FR-7.6 ("a tender an org's type cannot bid on is down-ranked and labeled, never silently
hidden") is unchanged and remains fully in force **for the diaspora/foreign audience it
now exclusively serves**. Many NCB tenders will correctly verdict `conditional` for a
foreign bidder ("local JV likely required") — that is precisely the signal that should
route a bidder to the facilitator marketplace, and is now the primary intended path
through the product, not a side case.

### `adera-mobile`'s stated premise

`docs/PRODUCT.md`, `MOBILE_GUIDE.md`, `OFFLINE.md`, and `docs/team/BRIEF_MOBILE.md` in
that repo all state the app exists so a **local Ethiopian SME** can use ADERA on
mid-range Android over patchy data (A2). Under this ADR the mobile *bidder* audience
becomes diaspora users abroad — a different device and network reality that weakens, but
does not eliminate, the case for the current offline/low-bandwidth investment (local
users remain the app's facilitator/poster audience once M14/M17 ship). Those docs are
rewritten alongside this ADR to state the corrected audience; **whether mobile investment
priorities change as a result is an open question for the founder**, raised in
`docs/PROGRESS.md`, not decided by this ADR.

## Rejected alternatives

- **Keep local as a bidder segment at a lower priority** — rejected: a half-served
  segment with live AI cost (matching, explanations, eligibility calls) but no product
  investment is worse than no segment at all; it burns AI budget (COST-1) against a
  KPI-negative audience and produces a confusing mixed message in every piece of GTM copy.
- **Gate by `country` instead of `org_type`** — rejected: it would incorrectly exclude a
  diaspora-owned, ET-registered company (a *better* customer, per §2.1) from bidder
  features, and incorrectly include a foreign-registered shell with no real Ethiopia
  relationship. `org_type` is the field the plan already built for exactly this
  distinction (FR-1.6); reusing it is not a new decision, only its first real
  enforcement.
- **Hard-block local registration entirely** — rejected: local companies are a real
  supply-side audience (facilitators, posters) that the plan depends on recruiting;
  blocking their accounts outright would contradict M14/M17 and remove the account
  local firms need in order to later apply as a facilitator or poster.

## Reversal condition

If Phase 3 KYB and facilitator vetting mature enough that a *verified* local company
could safely be re-admitted as a paying bidder (e.g., a local SME wanting eligibility
checks for its own NCB bids) — that is a new ADR, not a reversal of this one; nothing
here forecloses it, it is simply out of scope until proposed on its own terms.
