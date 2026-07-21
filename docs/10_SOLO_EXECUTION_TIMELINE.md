# 10 — Solo Execution Timeline: what one person builds, in what order, and why
*The other docs say how; this one says when. Backend-first is the rule: every frontend screen renders data only the pipeline can create, so the pipeline earns its keep first. Weeks assume ~25–30 focused hrs; slip a week without guilt, never skip a gate.*

## Operating rhythm (every week, regardless of phase)
Two 90-min deep blocks/day on the build track · Fridays: release (merge train, deploy, update the metrics sheet) · 15 min bookkeeping (02 §3) · one marketing action/day from Phase 2 (03) · monthly: drift audit vs the master plan + spend review. When stuck >90 min on one bug: write it down, switch tracks, return tomorrow — solo momentum beats solo heroics.

## Phase 0 — Weeks −2 → 0 (validation; ~4.5k ETB; no server rented)
Interviews: 10 A1 + 10 A2 + 5 facilitators, casting sheets filled (master plan §8) · teardowns: Getchereta paid, one TendersOnTime-class agent purchase, Jorpex · label 100 golden tenders from data you already hold · assemble law corpus from primary sources (G-LAW) · buy domain · **G-PAY dry run:** create the MoR account, sell a $1 test product, verify the payout path end-to-end · start eTrade registration reading (G-LIC) · G-NAME check. **Exit gate G0:** ≥8/15 A1 at $79 AND ≥8/20 A2 at ETB 449 AND ≥10 facilitator LOIs AND a working payout. Fail → reposition before writing product code; the 20k plan (02 §2) survives either answer.

## Phase 1 — Weeks 1–4 (the ingestion spine; first VPS month starts)
W1: repo scaffold + CI (09 §1,4) + compose local + schema/Alembic + VPS runbook (09 §5). W2: e-GP adapter + upsert + run ledger + admin alert path; **eval harness live** (06 §9) — it gates everything after. W3: documents parse path (05 §5) + extraction + prefilter/qualification; golden F1 climbing toward 0.90. W4: sources #2–3 (donor portal, org site) + review queue v0 + **n8n shadow-run parity report** — your prototype becomes the regression oracle, then retires. **DoD:** unattended daily pipeline, F1 ≥ 0.90/source, idempotency proven by re-run, chaos-tested failure alert.

## Phase 2 — Weeks 5–9 (matching + first revenue; frontend begins)
W5: profiles module + embeddings + matching SQL (05 §7). W6: explanations + grounding eval green + NCB/ICB classifier + eligibility chips v1 data (M16-lite). W7: **frontend starts** — tokens extracted (08 §2), (marketing) pages + tender public pages + guides #1–4 live (SEO clock starts now, 03 §2). W8: TZ-aware digests (email+Telegram) + onboarding wizard + feed. W9: **billing on the G-PAY rail** — Global Pro purchasable; design partners (10+10) onboarded. **DoD:** first paying subscriber · digest lands at each partner's 08:00 · NFR-AI-3 + C5/C6 evals green.

## Phase 3 — Weeks 10–14 (marketplace lead-gen + verified posting)
W10: facilitator profiles + vetting queue (SOP live). W11: request-intro + engagement thread + state machine (property-tested). W12: proof-of-submission upload/viewer + reviews. W13: poster KYB pipeline + composer + anti-scam moderation (FR-17.0/17.5). W14: tender-doc Q&A over SSE (backend 05 §3 + client 07 §6) + Local ETB rail if G-LIC has landed. **DoD:** 10 active facilitators · ≥5 completed engagements with proofs · first KYB-verified posted tender matched and delivered · paid beta open.

## Phase 4 — Weeks 15–20 (deepen) & Phase 5 — Months 6–9 (agentic + managed money)
P4: compliance matrix (Business tier) → bid checklist/workspace → Amharic OCR source #1 behind its eval gate → reminders → feedback→ranking → outcome tracking → billing hardening/dunning. P5: Eligibility Counsel L2 → Tender Analyst briefs → Fulfillment Coordinator → provider-held milestones + ETB payouts **only after counsel** → JV matchmaker design. Autonomy climbs by the gates in master plan §14, never by enthusiasm.

## The "what do I do right now" answer
Today: Phase 0, item one — book the first three interviews and buy the domain. Nothing in Parts I–III of any doc matters until G0 has an answer, and G0 costs conversation, not code.

## Further reading & credible sources
- **The Mom Test** — momtestbook.com — Phase 0 is twenty interviews; this short book is the difference between validated and flattered.
- **"Do Things That Don't Scale" (Paul Graham)** — paulgraham.com/ds.html — the facilitator-recruitment and design-partner phases are exactly this essay in practice.
- **YC Library: talking to users & launching** — ycombinator.com/library — pair with the gates; their "how to launch (again and again)" framing fits the phase exits.
- **Shape Up (Basecamp, free online)** — basecamp.com/shapeup — appetite-based scoping for a tiny team; useful when a phase item balloons.
- **Deep Work (Cal Newport)** — the two-90-minute-block rhythm's origin; read once, then just do the blocks.
- Everything technical you'll hit week-by-week is linked from docs 04–09's own further-reading sections — this doc stays the map, not the library.
