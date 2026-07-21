# Handoff: ADERA — AI-Native Bridge to Ethiopian Tenders

## Overview
ADERA (አደራ, "entrusted") matches diaspora/foreign/local businesses to Ethiopian public and donor tenders using AI extraction and matching, explains eligibility in plain language, and connects bidders with vetted local facilitators via a marketplace. This bundle is the full design package: design system, wireframes, user/data flow diagrams, hi-fi visual explorations, and a clickable prototype.

> ### ⚠️ Read before implementing: these designs are ahead of the plan
> Several screens in this bundle depict **Phase-5 vision as if it were launch scope** — most importantly **custodial escrow ("ADERA holds funds")**, which the master plan forbids at launch on *regulatory* grounds, not stylistic ones. **The master plan is the source of truth** (`../docs/00_MASTER_PLAN.md`); where it and these designs disagree, **the plan wins** and a change requires a new ADR.
> **Do not implement the escrow flow from these mocks.** See **[Design ↔ Plan deltas](#design--plan-deltas)** below for the full, itemized list before building anything in the marketplace/engagement area.

## About the design files
The files in this bundle are **design references built in HTML** (Claude "Design Components" — self-contained `.dc.html` files that run in any browser). They are prototypes showing intended look, content, and behavior — **not production code to copy directly**. The task is to **recreate these designs in the target codebase's real environment** (Next.js is not an assumption but a decision — ADR-010, master plan §12–13; see also `../docs/07_FRONTEND_GUIDE.md` and `../docs/08_DESIGN_SYSTEM_GUIDE.md` for the artifact→code workflow) using that environment's component patterns, state management, and existing libraries. If no frontend exists yet, Next.js + Tailwind (or CSS-in-JS) is a reasonable default consistent with the inline-styled structure of these files.

Open any `.dc.html` file directly in a browser to view/interact with it — no build step required.

## Fidelity
Mixed, by file:
- **`ADERA Hi-Fi Designs.dc.html`** and **`ADERA Prototype.dc.html`** — **high-fidelity**. Final color values, typography, spacing, copy, and (in the prototype) working click-through interaction. Recreate pixel-close using the codebase's real components.
- **`ADERA Wireframes.dc.html`** — **low/mid-fidelity**. Structure, hierarchy, and real copy, but grayscale/no visual design. Use for layout and content only — apply the design system's visual styling on top.
- **`ADERA Design System.dc.html`** — the source of truth for all design tokens (colors, type, chips, buttons, badges) — pull exact values from here.
- **`ADERA User Flows.dc.html`** / **`ADERA Data Flow.dc.html`** — process/architecture diagrams, not UI to recreate visually; use them to understand system and screen sequencing.

## Design ↔ Plan deltas

These designs were produced against the product **vision**; the master plan sequences that vision behind commercial, legal, and evidence gates. Every conflict found between this bundle and `../docs/00_MASTER_PLAN.md` is listed below. **In all cases the plan wins** — §12.3: *"Any change contradicting this file requires a new ADR."* If you want a delta resolved the other way, write the ADR; do not resolve it in a mock.

| # | Designs show | Plan says | Verdict |
|---|---|---|---|
| **1** | **Custodial escrow.** "Accept & pay into escrow", "**Funds held by ADERA**", "ADERA holds funds", escrow balance sidebar, "$165 in escrow", per-milestone release *(Wireframes, Hi-Fi 2a·5, Prototype, User Flows)* | **ADERA never holds client funds** (§6). Launch = subscriptions on the USD rail + **engagement fees invoiced**; platform holds no client funds (FR-15.2, ADR-020). Sequencing: invoiced lead-gen → provider-held milestones → **escrow only post-counsel**; "Escrow legal opinion" is a **pre-Phase-5 gate** (§19) | ⛔ **Do not build.** This is a *regulatory* boundary, not a UX preference — holding client funds implicates NBE licensing and the G-LIC path. Treat these screens as **Phase-5 vision** |
| **2** | **15–20% platform fee** *(Data Flow: "Facilitator payout (ETB) · 15–20% platform fee"; User Flows: "Payout on approval (ETB, minus 15–20%)")* | **10%** per engagement, floor $15 / ETB 1,000 (§4.2, Stream 2) | ❌ Designs wrong. **10%** |
| **3** | **"Feature on top for 7 days + $19"**, "Publish (free tier / featured $)" *(Hi-Fi 2a·6, User Flows)* | Posting **free in beta → ~ETB 2,500+VAT** per post with AI-matched distribution (§4.2 Stream 3, FR-17.3; config-driven) | ❌ Different mechanism *and* currency. Plan wins |
| **4** | **ETB payouts to facilitators at launch** | ETB rail is **[S] and post-G-LIC** (FR-15.5); launch revenue is **USD via Merchant-of-Record** (ADR-016). Live ETB rails require merchant KYC — trade license + commercial registration + TIN | ❌ No ETB payout exists pre-G-LIC |
| **5** | Proof = **"photo + GPS + receipt"** *(User Flows)* | Proof-of-submission = **stamped receipt photo/scan + metadata**, immutable in R2 (FR-15.6). GPS is not specified | ⚠️ Unratified addition. GPS is location PII → PRIV-1 / Proclamation 1321/2024 exposure. Needs an ADR before it ships |
| **6** | Screens say **"escrow"** throughout | The bundle's **own** Design System file states the voice rule: *"'Held until you approve the proof,' never 'escrow milestone capture'"* — matching master plan §15 | ⚠️ **The bundle contradicts itself.** The Design System is right; the screens violate it |
| **7** | README claimed **"all 11 hi-fi screens"** | Direction A enumerates **10** numbered screens (+ Direction B dark companions + 2 style explorations) | ✏️ Corrected below to 10 |

**Net effect on the marketplace/engagement build:** the *trust primitive* the designs are built around — "money is held until you approve the proof" — is real and stays. **What changes is who holds it.** At launch ADERA is an introducer that invoices a 10% fee; the bidder pays the facilitator through a rail ADERA does not custody. The engagement timeline, milestones, proof-of-submission artifact, and approve/dispute actions are all still in scope (Phase 3) — only *fund custody* is deferred. Build the timeline; do not build the vault.

## Screen inventory
Two parallel visual directions were explored on the same underlying screens — pick one (or blend) as the shipped direction.

### Direction A — "Paper & Clay" (light mode)
Warm paper background (#FAF6F0), clay/terracotta primary, ochre accents, coffee-brown ink text.

1. **Landing** — nav, hero (headline + CTA + product shot card stack), 3-step "how it works", dark trust strip with stats.
2. **Onboarding wizard** (3 steps) — org location (diaspora vs. local toggle cards) → sector multi-select chips → capacity freeform text, with a live "matching in the background" preview panel.
3. **Tender feed ("My matches")** — top nav w/ segmented tabs (My matches / All tenders / Saved / Engagements), filter rail (sector, eligibility, deadline, budget), match cards with urgency chip + eligibility chips + "why this fits you" callout + closing time in user's TZ and EAT.
4. **Tender detail** — title + chips + source/confidence line, plain-language summary, "Can you bid?" eligibility breakdown (org-specific, cited), Q&A thread, right rail: key dates timeline, requirements checklist, "Need local hands?" CTA card.
5. **"Can we win this?" brief (Pro)** — dark header band with circular fit-score gauge, 3-column: Working for you / Gaps to close / Suggested plan (dated), export-PDF affordance.
6. **Facilitator marketplace** — grid of facilitator cards (avatar, name, vetted/trial badge, rating, response time, languages, service tags, price, CTA), "how escrow works" step strip.
7. **Engagement timeline** — vertical milestone timeline (done/current/future dot states), proof thumbnails (receipt/photo/GPS), escrow balance sidebar, message thread, "አደራ Promise" trust callout.
8. **Poster KYB + tender composer** — verified-business badge, guided form (title, category, closing date/time in EAT, bid security, who can bid, spec upload), AI pre-publish lint callout, right rail: verification checklist + reach-preview stats + "feature" upsell.
9. **Admin/ops dashboard** — dark top bar, 5 KPI tiles (tenders today, extraction F1, pipeline latency, token spend, needs-review count), review queue list (KYB/extraction/report items with inline actions), source health list.
10. **Pricing** — 3-tier card layout (Free / Global Pro "most popular" / Global Business), dark middle tier.

### Direction B — "Bridge at Dusk" (dark mode)
Deep coffee-black (#1C1410) background, gold (#E8B54D) accent, same content — dark companions built for: tender feed, tender detail, engagement timeline, win brief. Use as the dark-mode / alternate-brand-mood equivalents of the same screens.

## Interactions & behavior (from the clickable prototype)
`ADERA Prototype.dc.html` implements the P1 diaspora journey end-to-end with real state transitions — treat this as the interaction spec:
- **Signup → Profile wizard**: 3-step wizard with a progress bar; step 1 is a binary org-location choice (styles toggle actively on selection); step 2 is multi-select sector chips (toggle on/off, count shown); step 3 is a static capacity statement. "Continue" advances state; "Back" retreats or returns to signup.
- **Feed → Detail**: clicking a match card (hover raises shadow + border color) navigates to detail.
- **Detail Q&A**: a dashed placeholder button ("Try: ...") reveals a canned Q&A exchange on click — model this as an async question-submit that returns a cited answer.
- **Detail → Marketplace**: "Request quotes" CTA.
- **Marketplace → Engagement**: "Accept & pay into escrow" CTA. ⛔ **Delta 1 — do not implement as drawn.** At launch this is `requested → quoted → accepted` on the engagement state machine (FR-15.1) with the 10% fee **invoiced**; ADERA does not take custody of the bidder's funds (FR-15.2, ADR-020).
- **Engagement milestone approval**: the in-progress milestone (dot outlined, not filled) shows two buttons — Approve (dot fills green, banner confirms) and Request changes. **The trust primitive is real and in scope** — proof-of-submission acceptance/dispute (FR-15.6/15.7) ships in Phase 3. ⛔ **Delta 1:** what Approve must *not* do at launch is release platform-held funds — there are none. Model it as **proof acceptance**, not escrow capture; the plain-language rule ("Held until you approve the proof") is the *goal state* the invoiced model still has to earn honestly. Copy must not imply custody ADERA does not have.
- **Top-of-screen step rail**: lets a reviewer jump directly to any screen — a prototype affordance only, not part of the shipped product.

## State needed (maps to prototype's logic class)
- `screen`: current view enum (signup, profile, feed, detail, marketplace, engagement)
- `wizardStep` (1–3), `orgType` (diaspora | local), `sectors` (map of label → boolean)
- `qaAsked` (boolean — has the user submitted a question)
- `m3Approved` (boolean — has the current milestone been approved); in production this generalizes to a milestone list with per-milestone status (pending/awaiting_approval/approved) — see Data Flow diagram, Level 2, Stage D/E. ⛔ **Delta 1:** the mock's **escrow ledger (held/released amounts) is not launch state** — no platform-held balance exists (FR-15.2). The real tables are `engagements` + `engagement_events` + `proof_artifacts` (Master Plan, Appendix A). `ledger_entries` is double-entry accounting for platform-mediated balances (ADR-017), **not** an escrow float — and money is **integer minor units, never float** (NFR-INTL-2).

## Design tokens (from ADERA Design System.dc.html)

> **For implementers (human or AI):** these values are extracted into a
> machine-readable contract at **`../docs/agents/DESIGN.md`** — tokens as paste-ready
> CSS variables, component inventory, voice rules, and the do-not-build deltas.
> Build from that file; use this bundle for visual reference only.
**Color**
- Clay (primary): `#B05A38` / hover `#8C4225`
- Ochre (accent): `#D9A441`
- Verified green (trust): `#2F7A55`
- Coffee ink (text): `#2B211A`
- Warm paper (surface): `#FAF6F0`; card surface `#FFFDFA`
- Umber (secondary text): `#5C4F43`; tertiary `#8C7A66`
- Border/hairline: `#EADDCB` / `#D9C9B8`
- Dark mode: background `#1C1410`, card `#251B14`, border `#3B2C1F`, gold accent `#E8B54D`, text `#F2E8D8`, secondary text `#B8A88F`/`#A08F73`, success green `#5AB280`
- Urgency: red `#9A2E1B`/bg `#F8E3DC` (≤7d), ochre `#9A6A12`/bg `#FBF0DC` (≤14d), green `#2F7A55`/bg `#E5F0E9` (>14d)

**Typography**
- Display/heading: `Noto Serif` (weights 500/600/700/800)
- Body/UI: `IBM Plex Sans` (400/500/600/700)
- Data/mono (dates, deadlines, code-like values): `IBM Plex Mono` (400/500/600)
- Amharic/Ethiopic accents: `Noto Sans Ethiopic` (400/600/700) — used for the wordmark አደራ and language-toggle affordance, not for body copy
- Scale used: 54px display hero, 38px section, 26–28px screen title, 19px card title, 15–16px body, 13–14px meta/secondary, 11–12px mono labels/eyebrows

**Shape & elevation**
- Radius: 8–10px controls, 12–14px cards, 999px pills/chips/avatars
- Card shadow (light): `0 2px 8px rgba(43,33,26,0.07)` resting, `0 6px 18–28px rgba(43,33,26,0.14–0.18)` hero/raised
- Chips: 1–1.5px border, pill radius, colored per category (see eligibility/urgency above)

**Voice/content principles**
- Plain language always ("why this fits you," not "RAG"; "held until you approve the proof," not "escrow milestone capture")
- Every deadline shows user's local time + EAT alongside, as a countdown chip plus explicit datetime
- Every AI claim is cited (source link, confidence dot, "what we checked" expander, one-tap error report)

## Assets
No external image/icon assets — all "photos" in the mocks are gradient placeholder blocks with descriptive labels (e.g., "[stamped receipt]"); avatars are gradient-fill circles with initials. Real product photography/document scans and a proper icon set (vetted badge, checkmarks, etc.) should replace these. Emoji glyphs (✓ ⚠ 🏦 📄 📸 📍) are used as lightweight icons throughout the mocks — swap for a real icon system if the brand prefers.

## Files in this bundle
- `ADERA Design System.dc.html` — tokens & components (source of truth for values above)
- `ADERA Wireframes.dc.html` — mid-fi structural layouts, 5 core screens
- `ADERA User Flows.dc.html` — swimlane end-to-end flow + 3 detailed flows (diaspora, facilitator, poster)
- `ADERA Data Flow.dc.html` — Level 0 pipeline, Level 1 system architecture, Level 2 end-to-end data journey
- `ADERA Hi-Fi Designs.dc.html` — the 10 hi-fi screens of Direction A, plus Direction B dark companions and 2 style explorations (open in browser, scroll/pan — canvas mode)
- `ADERA Prototype.dc.html` — clickable P1 diaspora journey (open in browser and click through)
- `ai_tender_platform_master_plan.md` (in this folder) — the product/business/architecture spec these designs implement. **Note:** this file is byte-identical to `../docs/00_MASTER_PLAN.md`. Two copies of a "source of truth" is a drift hazard — prefer **`../docs/00_MASTER_PLAN.md`** as canonical and treat this copy as a convenience mirror to be deleted once the bundle is merged into the repo proper.
- `support.js`, `screenshots/` — runtime support for the `.dc.html` canvases and PNG exports of the flow/system diagrams.
