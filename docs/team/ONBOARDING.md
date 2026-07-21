# Welcome to ADERA (አደራ) — team onboarding

*Self-contained: readable without repo access. Paths like `docs/...` refer to the
`adera-api` repository once you have it.*

---

## 1. What we are building

**ADERA is AI-native tender intelligence for Ethiopian public procurement.**
~$9B/year flows through Ethiopia's e-GP system (74+ federal agencies), plus donor
portals (World Bank, AfDB) and org sites. Today, an Ethiopian SME finds tenders by
scanning category dumps and Telegram channels; a diaspora-owned company abroad
mostly can't participate at all — not because it's illegal, but because nobody
tells them *what fits them, whether they're eligible, and how to physically submit*.

ADERA's pipeline scrapes tenders from every source, extracts structured fields,
**matches them to a company's profile using embeddings** (meaning-based, not
keywords), and explains *why this fits you* in plain language. Later phases add an
eligibility engine that cites Ethiopian procurement law (Proclamation 1333/2024)
and a vetted marketplace of local facilitators who execute the physical steps —
document purchase, bid securities, sealed submission — for remote bidders.

**The unit of value is one card** (real data from our pipeline; the explanation
line shows the target format — that feature ships next):

```
🟠 Closes in 3d — 09:00 your time / 19:00 EAT
Selection of Individual Consultant for Monitoring, Customizing,
and Deployment of Service Taxonomy
World Bank–funded · Ethiopia
WHY THIS FITS YOU: matches your "service taxonomy design" and
digital-government consulting capabilities.        [match score 0.67]
✅ Diaspora eligible · [Save] [Dismiss] [Ask about this tender]
```

## 2. What exists today (honest status — verified, not aspirational)

| Piece | Status |
|---|---|
| Ingestion pipeline (World Bank donor portal) | ✅ **live** — 69 real Ethiopian tenders in DB; re-runs proven duplicate-free; every run cost/latency-logged |
| Background workers (Celery + Redis) | ✅ proven end-to-end |
| Semantic matching (BGE-M3 embeddings, local, $0/query) | ✅ **built & judged** — 3 test company profiles each got correct, non-overlapping tender lists |
| "Why this fits you" explanations | 🔑 built, needs LLM API key — next up |
| e-GP scraper (the primary source) | ⏳ registered, disabled — needs authenticated Playwright session |
| Qualification filter (drop already-awarded/noise) | ⏳ next build week |
| Public API for clients | ⏳ landing now (`GET /api/v1/tenders`) — this is what web/mobile consume |
| Web app · Mobile app · Auth · Billing | 🚧 that's where **you** come in |

## 3. How we work (hackathon mode)

**Three repositories** (each language keeps its native toolchain and CI):

| Repo | Contents | Owner |
|---|---|---|
| `adera-api` | FastAPI backend + pipeline + canonical docs | Yetmgeta + backend |
| `adera-mobile` | Flutter app | mobile dev |
| `adera-web` | Next.js web app (starts after mobile) | web dev |

**Contract-first:** the API publishes a versioned OpenAPI spec at
`adera-api/contracts/openapi.json` (CI guarantees it matches the code). Mobile
generates its **Dart** client from it; web generates its **TypeScript** client.
You never hand-write API models — regenerate when the contract changes.

**Ground rules (all of us, including AI assistants):**
1. Branch + PR — never commit to `main` directly.
2. Backend PRs: `make check` must be green (format, lint, strict typing, tests) +
   paste proof the change actually runs. Client repos: analyzer/tests equivalent.
3. **Founder-review-mandatory** (never merge alone): auth, billing/payments,
   prompt changes, DB migrations, anything touching money or law.
4. Working with an AI assistant? It must read the repo's `AGENTS.md` first —
   each repo has one; it carries the rules and known traps.
5. Deadlines are sacred in this product: all times stored UTC, always displayed
   in the user's timezone **and** EAT. Money is integer minor units, never floats.

## 4. Who does what + your day-1 reading

| Role | Repo | Read first (in order) |
|---|---|---|
| Backend | `adera-api` | `README.md` → `AGENTS.md` → `docs/05_BACKEND_GUIDE.md` (has a Django→FastAPI map) → `docs/agents/SKILLS.md` |
| Mobile (Flutter) | `adera-mobile` | your `BRIEF_MOBILE.md` → repo `README.md` → `docs/DESIGN.md` (tokens & components — this is law) |
| Web (Next.js) | `adera-web` | your `BRIEF_WEB.md` → `docs/07_FRONTEND_GUIDE.md` → `docs/agents/DESIGN.md` |
| Security | `adera-api` | your `BRIEF_SECURITY.md` → `AGENTS.md` §4 → the prompts in `prompts/` |

## 5. Prepare today (before repo access)

- **Everyone:** Git + GitHub account (send Yetmgeta your handle), Docker Desktop/Engine.
- **Mobile:** Flutter SDK (stable) + Android Studio/Xcode; skim an OpenAPI→Dart
  client generator (`openapi_generator` or `swagger_dart_code_generator`).
- **Web:** Node 20+ + pnpm; skim Next.js 14 App Router if rusty.
- **Backend:** Python 3.12 + `uv` (`pipx install uv`); skim FastAPI's DI docs.
- **Security:** skim OWASP ASVS L1 + OWASP Top-10 for LLM applications (prompt
  injection is a first-class threat here — we ingest untrusted scraped documents).

## 6. Mini-glossary

**Tender** — a public purchase announcement companies bid on. **e-GP** — Ethiopia's
official electronic procurement portal (egp.gov.et). **NCB / ICB** — National /
International Competitive Bidding; NCB effectively favors domestic bidders, ICB is
open to foreign firms — this distinction drives our eligibility engine.
**Eligibility chips** — the ✅/⚠️/⛔/❓ verdict badges on every tender card (exactly
four variants exist; `❓ unknown` is a legitimate answer, never guessed).
**Facilitator** — a vetted local professional who executes physical bid steps for
remote bidders. **CPO** — a bank-issued payment instrument used as bid security.
**Bid bond / security** — refundable deposit required to bid.

---

*Questions → Yetmgeta. This doc lives at `adera-api/docs/team/ONBOARDING.md`;
role briefs live beside it.*
