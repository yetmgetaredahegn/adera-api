# 07 — Frontend Development Guide (Next.js 14, App Router)
*Structure, concepts-per-feature, SEO, i18n, performance — enough that a junior ships screens that match the design system (08).*

> **Repo note (ADR-025):** the web app lives in the separate **`adera-web`** repository — paths below (`web/src/...`) are relative to that repo. The API contract it consumes is generated from `adera-api/contracts/openapi.json`.


## 1. Why these tools (one line each)
Next.js App Router → server rendering for the SEO channel (FR-9.1) + streaming UI; TypeScript → contract safety with the generated API client; Tailwind + shadcn/ui → the design tokens from 08 become utility classes and accessible components; next-intl → en/am locales (ADR-018); TanStack Query → client-side caching/mutations for the interactive app surfaces; openapi-typescript → the backend's /openapi.json becomes typed functions, so a schema change breaks the build, not production.

## 2. Directory structure
```
web/src/
├── app/
│   ├── (marketing)/            # public, SSR, SEO-critical
│   │   ├── page.tsx            # landing
│   │   ├── tenders/[slug]/page.tsx      # programmatic tender pages (FR-9.1)
│   │   └── guides/[slug]/page.tsx       # eligibility guides (03 §2)
│   ├── (app)/                  # authenticated product
│   │   ├── layout.tsx          # shell: nav, org switcher, locale toggle
│   │   ├── feed/page.tsx  tenders/[id]/page.tsx  onboarding/  marketplace/
│   │   ├── engagements/[id]/page.tsx    # timeline UI (15 §UX)
│   │   └── settings/ billing/
│   ├── (admin)/admin/...       # review queues, run ledger, sources, KYB
│   └── api/                    # none — the FastAPI backend is the API; no route handlers here
├── components/ (ui/ = shadcn primitives; product/ = TenderCard, EligibilityChips, FitPanel,
│                QAChat, EngagementTimeline, ProofViewer, KybBadge)
├── lib/ (api.ts generated client + fetch wrapper w/ credentials; seo.ts; i18n.ts)
└── messages/en.json am.json    # next-intl dictionaries
```

## 3. The two data-fetching modes (know which you're in)
**Server Components (default):** `page.tsx` runs on the server; fetch directly and render — zero client JS for content. All (marketing) pages and first paint of feed/detail work this way:
```tsx
export default async function TenderPage({ params }) {
  const t = await api.tenders.get(params.id, { cache: "no-store", headers: authHeaders() });
  return <TenderDetail tender={t} />;
}
```
**Client Components (`"use client"`)** only where there's interactivity: save/dismiss buttons, Q&A chat, onboarding wizard, admin queues. There, TanStack Query owns state: `useMutation(api.matches.dismiss)` with optimistic update (flip the card instantly, roll back on error) — this is what makes dismiss feel native on 3G.

## 4. Feature → concept map (build in this order)
| Screen (08 inventory) | Next concepts you'll use | Notes |
|---|---|---|
| Landing + guides | Server Components, `generateMetadata`, static rendering | Ship first; zero auth |
| Tender public page | `generateStaticParams` off recent tenders + ISR (`revalidate: 3600`) | Long tail renders on demand, then caches |
| Onboarding wizard (FR-6.1) | Client component, multi-step local state, one final mutation | Chips = editable tags; median <3 min is a test |
| Feed | Server first page + client infinite scroll (keyset cursor from API) | EligibilityChips per card (org_type aware) |
| Tender detail + Q&A | Server shell + client QAChat over SSE | See §6 |
| Marketplace + engagement timeline | Server lists + client request-intro form (Idempotency-Key header) | Timeline = ordered engagement_events render |
| Admin | Client-heavy tables, TanStack Query, keyboard shortcuts | Correct/approve actions post to review endpoints |

## 5. Auth from the frontend
Session cookie is httpOnly — JS never reads it; every fetch sends `credentials: "include"`. Server Components forward the cookie header to FastAPI. 401 → middleware redirects to /login with `next=` param. CSRF token arrives in a meta tag; the fetch wrapper attaches it on POST/PATCH/DELETE automatically — one wrapper, zero per-call ceremony.

## 6. SSE Q&A client (the one tricky component)
```tsx
const es = new EventSource(`/api/v1/tenders/${id}/qa?msg=${encodeURIComponent(q)}`,{withCredentials:true});
es.onmessage = (e) => { const c = JSON.parse(e.data);
  c.type === "token" ? append(c.text) : c.type === "citation" ? addChip(c) : es.close(); };
es.onerror = () => { es.close(); showRetry(); };
```
Render citations as chips (page/§ from 06 §7); the "not answered by the documents" state gets the kind copy from the design system, never a red error.

## 7. SEO implementation checklist (this is a growth feature, treat as such)
`generateMetadata` per page (title ≤60 chars, description with buyer+deadline) · canonical URLs · `app/sitemap.ts` streaming all public tender+guide URLs · JSON-LD: `Organization` sitewide, `BreadcrumbList` on tender pages, `FAQPage` on guides (rich-result eligible); note honestly there is no perfect schema.org type for tenders — breadcrumbs + solid meta is the play, don't force a wrong type · OG image per tender (template with title/deadline chip) · hreflang en/am pairs via next-intl routing.

## 8. Performance budget & how it's enforced
Public pages < 100 KB first-load JS (NFR/UX §7 master plan): Server Components by default, `next/dynamic` for QAChat/admin, `next/font` self-hosted IBM Plex Sans (+ Plex Mono) + Noto Sans Ethiopic (subset!) — per the design bundle, not Inter (see 08 §3 correction), no hero images (design is typographic — 08), Tailwind purges itself. Enforce: `next build` bundle output eyeballed per PR + Lighthouse CI budget (perf ≥ 90 on /, /tenders/[slug]) in the pipeline — a regression fails the build, same as a test.

## 9. i18n mechanics
next-intl with `[locale]` segment; `useTranslations("feed")` in components; dictionaries in `messages/`. Rules: no hardcoded strings in product components (lint via eslint-plugin no-literal-string on components/product); dates/countdowns through one `formatDeadline(dt, locale, tz)` util (NFR-INTL-1 lives here on the client); Amharic reviewed by a human before release — machine-translated UI copy is a trust-killer for A2.

## 10. Testing the frontend
Playwright e2e: signup → onboarding → feed shows a match → open detail → ask Q&A (mock SSE) → save (three specs, the money paths). Component tests (vitest + testing-library) only for logic-bearing components (EligibilityChips variants, wizard validation). Visual: Playwright screenshot of TenderCard in en+am, light+dark, diffed in CI — catches Ethiopic and token regressions at once (08 §6).

## Further reading & credible sources
- **Next.js docs** — nextjs.org/docs — App Router fundamentals: the pages on Server/Client Components, caching/revalidation (ISR), `generateMetadata`, and `sitemap.ts` cover 90% of this doc's machinery.
- **React docs** — react.dev — especially "Thinking in React" and the hooks reference; the mental model under everything.
- **TanStack Query docs** — tanstack.com/query — mutations + optimistic updates exactly as §3 uses them.
- **next-intl docs** — next-intl.dev — locale routing, dictionaries, and formatting for the en/am setup *(domain verified as of writing)*.
- **Tailwind CSS docs** — tailwindcss.com/docs — utility reference + the theming section that binds 08's tokens.
- **shadcn/ui** — ui.shadcn.com — component sources and the theming doc used in 08 §2.
- **openapi-typescript** — github.com/openapi-ts/openapi-typescript — generating the typed client from FastAPI's schema.
- **MDN: Server-Sent Events / EventSource** — developer.mozilla.org/en-US/docs/Web/API/EventSource — the browser half of §6.
- **web.dev** — web.dev — Core Web Vitals and performance-budget guidance behind §8; pair with Lighthouse CI (github.com/GoogleChrome/lighthouse-ci).
- **Google Search Central for developers** — developers.google.com/search — canonical, sitemap, hreflang, and structured-data implementation details for §7.
