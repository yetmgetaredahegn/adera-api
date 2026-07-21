# 02 — Finance & Operations Guide
*Your actual numbers, a spend plan tied to gates, and the habits that keep you fundable.*

## 1. Current position (stated plainly)
Liquid now: **~20,000 ETB (~$150)**. A further **50,000 ETB exists but is committed elsewhere** — this plan treats it as **locked**. Unlock conditions (all three, no exceptions): G0 passed (WTP proven) **and** G-PAY passed (working payout) **and** ≥3 paying customers. Until then the 50k does not exist for ADERA. Writing this down now prevents the classic founder failure of bleeding personal reserves into an unvalidated build.

## 2. The 20k ETB plan (validation-first: spend on proof, not infrastructure)
| Item | When | ETB |
|---|---|---|
| Domain (.com or .bid, 1 yr) | Phase 0 | ~2,000 |
| VPS — **pay monthly, not yearly** (~€9/mo ≈ 1,350) | From Phase 1 only | 1,350/mo |
| LLM/OCR starter credit (hard-capped in code, NFR-COST-1) | Phase 1 | ~2,700 ($20) |
| Getchereta paid tier + one competitor agent-service purchase (G-TEAR) | Phase 0 | ~2,500 |
| eTrade business registration + trade license (G-LIC) | When local rail needed, not before | ~2,000–5,000 (verify fees) |
| Buffer (things break) | — | ~3,000 |
**Total through ~Month 3 ≈ 15–17k ETB.** Phase 0 costs ≈ 4.5k only — you can *prove or kill the idea for under 5k ETB before renting a single server.* That is the discipline: interviews and teardowns first, VPS second.

## 3. Bookkeeping from day zero (boring, decisive)
One spreadsheet, three tabs, 15 minutes weekly:
- **Ledger:** date · what · category (infra/tools/legal/marketing/research) · ETB · USD-equiv · receipt link (photo → Drive folder).
- **Runway:** cash ÷ average monthly burn = months left. Update monthly; if runway < 3 months, cut before you borrow.
- **Revenue:** per customer: plan, start date, amount, rail, status. This tab *is* your MRR/churn evidence for investors (01 §2).
Rules: **never mix personal and business money** — before the license exists, use one dedicated personal sub-account/telebirr wallet used for nothing else; after G-LIC, open a business account and move everything. Keep every receipt: needed for tax later and for investor due diligence always.

## 4. Pricing/VAT mechanics you'll hit
Local prices are quoted VAT-inclusive in this market (2merkato/iChereta do); registering for VAT has a turnover threshold — confirm with the eTrade/tax office at G-LIC and don't charge "VAT" before you're registered for it. USD subscriptions via a Merchant-of-Record: the MoR is the seller of record and handles buyer-side tax; your side is simply payout income — keep MoR statements in the receipts folder.

## 5. If investment lands (from 01): managing other people's money
- Open/finish the business account first; investment goes there, nowhere else.
- Re-budget as **milestone envelopes** (e.g., "reach 50 paying subs: marketing X, stipend Y, ops Z"), not a lump.
- Founder stipend becomes a normal budget line — agreed with the investor, paid monthly, recorded. Underpaying yourself to look frugal causes worse failure (burnout) than the stipend costs.
- Monthly investor update email (5 lines: MRR, users, burn, runway, blockers). Calendar-blocked; investors forgive bad months, not silence.
- Never commit >1 month of runway to any single irreversible spend without sleeping on it.

## 6. Cost-control mechanics already designed into the product (know them so you defend them)
Prefilter before any model call · cheap-tier routing + caching in the AI Kernel · **hard daily spend cap with automatic pipeline pause** (NFR-COST-1) · local embeddings = $0 marginal · per-user quotas on Q&A. Finance rule: the cap value lives in config; only you change it, and only after looking at the spend dashboard (FR-11.5).

## Further reading & credible sources
- **eTrade Ethiopia** — etrade.gov.et *(verify current portal + fees)* — the online business-registration/trade-license path referenced by Gate G-LIC.
- **National Bank of Ethiopia** — nbe.gov.et — directives on payment systems/FX; the primary source behind "NBE-regulated rails require merchant KYC."
- **Chapa developer docs** — chapa.co → developer documentation — ETB rail integration + settlement rules *(verify fees at G-PAY)*.
- **Merchant-of-Record options** — paddle.com and lemonsqueezy.com — how MoR pricing/fees/payouts work; confirm payout path to Ethiopia (Payoneer/wire) before committing (ADR-016).
- **Stripe Atlas** — stripe.com/atlas — the Delaware-LLC investor path: what $500 buys, ongoing obligations.
- **"Default Alive or Default Dead?"** — paulgraham.com/aord.html — the runway mindset behind §1–2 of this doc.
- **Bench guide to simple bookkeeping** (bench.co/blog) or any single-entry template — you need the three-tab sheet, not accounting software, until revenue says otherwise.
