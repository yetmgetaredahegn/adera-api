# Web brief — Next.js (adera-web)

*Read ONBOARDING.md first. This is your one-pager. Web track starts after mobile —
use the lead time to absorb the design system.*

## Your mission

The web app serves two very different users on one codebase:
1. **Public SEO pages** — every tender gets a public, server-rendered page
   (facts + link-out). This is a *growth channel*, not decoration: eligibility
   guides + tender pages are how diaspora bidders find us on Google. <100 KB
   first-load JS on public pages is a hard budget.
2. **The authenticated app** — feed, tender detail with Q&A, saved searches
   (mirrors mobile's screens, richer interactions).

## Stack (decided — ADR-010, don't relitigate)

Next.js 14 App Router · TypeScript · Tailwind + shadcn/ui · TanStack Query ·
next-intl (English default, Amharic toggle — Ethiopic fonts must render) ·
API client **generated** from `contracts/openapi.json` via `openapi-typescript`.

Server Components by default; `"use client"` only where there's interactivity.
Full guide: `docs/07_FRONTEND_GUIDE.md` in adera-api (you'll have access).

## Design law (same contract as mobile — `docs/agents/DESIGN.md`)

Tokens only (Paper & Clay / Bridge at Dusk) · EligibilityChips = exactly 4
variants · dual-timezone deadlines · one serif moment per screen · urgency red is
the loudest color on any screen and is reserved for urgency · plain-language
voice · WCAG AA at the token level.

## Prepare before the track starts

Node 20 + pnpm · skim App Router docs (Server vs Client Components, `generateMetadata`,
ISR) · read `docs/07` §2 (directory shape) and §7 (the SEO checklist) · look at
`design-reference/screenshots/`.

## Definition of done (any page)

Tokens only · light+dark · en + am strings via next-intl (no hardcoded copy) ·
public pages within the JS budget · Lighthouse ≥90 on public routes · generated
client only (no hand-written fetch types).
