# COMPETITORS — the Ethiopian tender/procurement landscape

*Canonical here. Labeled mirrors: `adera-web/docs/COMPETITORS.md`,
`adera-mobile/docs/COMPETITORS.md` — same content, so nobody needs access to
this repo to know who we're competing with.*

**Written from the tech lead's own research** (chat-based, 2026-07-23) —
verify anything load-bearing yourself before relying on it for a decision.

---

## The landscape

| Platform | What it is | AI features | Mobile app | Can you post a bid? | Gov't bids | Private/NGO bids |
|---|---|---|---|---|---|---|
| **GetChereta** | Smart tender management, our closest thesis competitor | **GenAI proposal drafting + win-rate prediction** | ✅ | — (client-side tool) | via aggregation | via aggregation |
| **2Merkato** | Market leader, largest private aggregator | AI summaries of long tender PDFs (not drafting) | ✅ | ✅ | ✅ | ✅ |
| **AfroTender** | Strongest challenger to 2Merkato; deep analytics | Market intelligence — **historical win/price analytics**, trend graphs | ✅ | ✅ (vendor listing) | ✅ | ✅ |
| **EthiopianTender** | Claims largest volume, aggregates scanned newspapers (Addis Zemen etc.) | Categorization/de-junking | ✅ | ✅ | ✅ | ✅ |
| **e-GP** (`egp.gov.et`) | Official government platform, PPA-operated | None | ❌ **no mobile app** | Gov agencies only | ✅ (primary source) | ❌ |
| **GlobalTenders / TendersOnTime** | International aggregators covering Ethiopia | AI categorization/cleaning | varies | — | ✅ | weak local context |

## Per-competitor notes

**GetChereta** — the platform closest to ADERA's actual thesis: AI that does work
*for* the bidder, not just surfaces listings. Ships proposal drafting and
win-rate prediction today. This is the one to study hardest.

**2Merkato** — the incumbent by scale and trust. Multi-language (Amharic,
Oromiffa, Tigrinya, English) with a construction-materials pricing sub-app.
Their AI is *summarization*, not prediction or drafting — a narrower claim than
GetChereta's.

**AfroTender** — the sharpest analytics product in the field. "Who won, at what
price, historically" is exactly the question our own `05-win-brief.png` design
proposes to answer. **`robots.txt` explicitly disallows `/tenderslist` and
`/tendersview/`** (paywalled) — see ADR-027 for why we do not scrape this.

**EthiopianTender** — wins on raw volume via aggressive aggregation, including
manually digitizing print newspapers. Reach, not intelligence, is the pitch.

**e-GP** — the primary official source and the one thing none of the above
truly replace: it's the system of record. No mobile app is a real, current gap
in the market, not just relative to us.

**GlobalTenders/TendersOnTime** — broad but shallow on Ethiopia specifically;
useful as a check on international-donor listings, not a serious competitive
threat locally.

## The finding that matters most: the win-brief overlap

ADERA's v2 design (`05-win-brief.png`, "Can we win this?") proposes AI-assisted
win-likelihood and proposal support. **GetChereta already ships proposal
drafting + win-rate prediction. AfroTender already ships historical win/price
analytics.** Between the two of them, most of what that screen proposes already
exists somewhere in the market.

This does not mean the screen is wrong to build — it means **we are not
entering an empty category with our headline feature, and we need to be
specific about what makes ours better**: eligibility reasoning grounded in
*cited* procurement law with `unknown` as a first-class, honestly-rendered
verdict (NFR-LEGAL-1) — versus a keyword alert or a generic prediction score —
and matching driven by a real company profile rather than a saved search. That
specificity is the backend track's first research question
(`docs/proposals/FIRST_TASK.md`).

## ⚠️ Hard boundary on researching any of this

**Use every product above as a normal user or paying customer would.** Read
their public pages, install their apps, sign up for a free tier if one exists.

**Never intercept mobile app traffic, reverse-engineer their API, or attempt to
bypass authentication on any of them.** Mobile apps in this space use SSL
pinning, dynamic auth tokens, and device fingerprinting — attempting to get
around that triggers account/IP bans far faster than scraping a website would,
and sits on the same side of Ethiopia's Computer Crime Proclamation 958/2016
line that `docs/ADRs/027-source-access-legality.md` addresses for our own data
sources. The rule is the same regardless of whose system it is: **never
authenticate or automate your way past a login to extract data or behavior.**

This matters most for whoever is researching the mobile apps directly — read
their `docs/proposals/FIRST_TASK.md` for the specifics.
