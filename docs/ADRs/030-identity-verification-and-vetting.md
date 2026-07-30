# ADR-030 — Identity verification & vetting mechanism: bidder self-declaration, facilitator vetting, poster KYB

| | |
|---|---|
| **Status** | Proposed (tracking — no mechanism decided yet) |
| **Date** | 2026-07-29 |
| **Decision** | No verification mechanism exists yet for any of ADERA's three org-facing actor types. This ADR does not decide one — it records the gap precisely, ties it to what the master plan already committed to, and lists the open questions that must close before Phase 3 (M14/M17) can ship. Founder-review-mandatory per `AGENTS.md` rule 14 / master plan Appendix E rule 7 — no agent designs or implements the actual verification logic from this ADR alone. |

## Context

Raised directly by the founder (2026-07-29): three distinct actor types eventually need
their identity or business standing checked, and there was a concern this wasn't written
down anywhere. It is — at the product-decision level — but not at the mechanism level,
and that distinction is the point of this ADR.

**Already decided, in the master plan, before this ADR:**
- The three-sided model itself (§2.2): **bidders** (diaspora/foreign, demand-side,
  `org_type` self-declared at registration, FR-1.6) · **facilitators** (local,
  supply-side, vetted before being listed, M14) · **posters** (local, supply-side,
  KYB-verified before any tender they post is visible, M17).
- SLAs: **NFR-TRUST-1** — facilitator vetting decision ≤5 business days, evidence
  retained, suspension effective ≤1h. **NFR-TRUST-2** — no tender post visible without
  completed poster KYB; KYB + moderation audit trail retained ≥2 years. **NFR-SEC-3** —
  facilitator KYC-lite before `active`; sanctions/PEP screening on payout recipients.
- A draft schema shape (Appendix A, not yet migrated into `adera-api`):
  `facilitators.vetting_status ∈ {applied, docs_submitted, interviewed, trial_verified,
  active, suspended}`, `vetting_records(step, evidence_key, decided_by, decided_at,
  notes)`, `kyb_records(doc_kind ∈ {trade_license, commercial_reg, tin}, status ∈
  {submitted, approved, rejected}, reviewed_by, reviewed_at, expires_at)`.
- Admin review queues for both are named (FR-11.2: "poster KYB, facilitator vetting").
- `ADR-029` already flagged one piece of this as an **accepted, unsolved Phase-2 risk**:
  nothing today stops a local company self-registering as `org_type=diaspora` to get
  bidder features it shouldn't have — recorded there as a soft gate, explicitly deferred
  to "whoever owns Phase 3 KYB work."

**Current code state, verified directly (not assumed):** `identity/service.py::register`
persists whatever `org_type` the client sends, with no check against it whatsoever.
`facilitators`, `vetting_records`, and `kyb_records` do not exist in
`migrations/versions/` — this is 0% built, not partially built. `adera-web`'s
`/profile-setup` is a local-only mock wizard with no verification step of any kind.

## The three actors, restated plainly

| Actor | Direction | What needs checking | Plan reference |
|---|---|---|---|
| **Bidder org** (diaspora/foreign) | Demand | Is this company real, and is its self-declared `org_type` true? | FR-1.6, ADR-029 |
| **Facilitator** (local) | Supply | Is this person/firm licensed and competent enough to represent a remote client physically in Ethiopia? | M14, NFR-TRUST-1, NFR-SEC-3 |
| **Poster** (local) | Supply | Is this a real, licensed business, entitled to publish a tender others will bid real money against? | M17, NFR-TRUST-2 |

## What is genuinely undecided (the actual gap)

1. **Bidder side:** does ADERA ever go beyond self-declared `org_type`, or is the soft
   gate permanent? If harder verification is wanted — a business-registry lookup, a
   verified work-email domain, a card-country cross-check at billing time — nobody has
   picked one.
2. **Facilitator vetting:** what documents/credentials are actually collected (a
   professional license? business registration? references? an interview — the schema
   already has an `interviewed` status)? Who reviews them — the founder alone, at this
   scale? What does `trial_verified` mean operationally before `active`?
3. **Poster KYB:** which of `trade_license` / `commercial_reg` / `tin` are required vs.
   optional, and validated against what — is there an authoritative Ethiopian business
   registry to check against, or is this manual document review? What's the
   rejection/appeal path?
4. **Tooling:** manual founder review (a queue, a spreadsheet) vs. a third-party
   identity/business-verification API/vendor — not evaluated either way yet.
5. **Document handling & retention:** uploaded ID/business documents are sensitive.
   NFR-TRUST-2 already sets a ≥2-year retention floor for KYB audit trail, but nothing
   yet connects this to Ethiopia's data-protection Proclamation 1321/2024 (named in the
   glossary, Appendix D, not otherwise referenced in this context).

## Consequences

Phase 3's own Definition of Done depends on this being resolved, not assumed away when
Phase 3 work starts: "10 active facilitators," "first KYB-verified posted tender matched
& delivered" (§16) are unreachable without a real vetting/KYB mechanism behind them. This
ADR exists so that dependency stays visible in `docs/ADRs/` and `docs/PROGRESS.md`
instead of being quietly discovered mid-Phase-3.

## Rejected alternatives

Not applicable yet — no mechanism has been proposed to reject. This ADR is the parking
lot, not the design; picking (and rejecting) actual mechanisms is follow-up work, likely
three narrower ADRs (one per actor) once the founder is ready to design them, per rule 14
("escalate, don't implement silently").

## Reversal condition

Superseded once the founder decides a concrete mechanism for each of the three actors —
recorded either as three follow-up ADRs or an expanded revision of this one. Until then,
nothing here should be implemented (rule 14); this is a tracking record, not a spec.
