# Mobile brief — Flutter (adera-mobile)

*Read ONBOARDING.md first. This is your one-pager.*

## Your mission

**Audience correction (ADR-029, v2.2):** local Ethiopian SMEs are supply-side
(facilitator/poster) only, never a bidder — this brief previously said the app
is how a local SME lives with ADERA daily; that premise is retired. The mobile
bidder audience is a **diaspora bidder abroad**: check matches over coffee in
Seattle or Dubai, open a tender, decide bid/skip in under a minute. Whether the
aggressive offline/low-bandwidth posture below still deserves the same priority
for that audience is an open question for the founder, not decided here —
diaspora users are more likely on decent connections than the original A2
premise assumed, but design for the low end anyway until that's confirmed:
fast cold start, small payloads, graceful offline (cache last feed).

## The screens you own (hackathon scope, in order)

1. **Matches feed** — list of tender cards: urgency chip (🔴 ≤7d / 🟠 ≤14d / 🟢 >14d),
   serif title, buyer, match-score line, eligibility chips. Pull-to-refresh.
2. **Tender detail** — full extracted fields (each carries a confidence indicator),
   deadline block, "why this fits you" paragraph (API-provided; render as text),
   link-out to the official source.
3. **Save / dismiss** — dismissed tenders never resurface (product law, FR-7.3).

Reference visuals: `design-reference/screenshots/` + the component contract below.

## Design law (not suggestions — `docs/DESIGN.md` in your repo, mirrored from adera-api)

- **Tokens only** — every color/radius/shadow comes from the token sheet
  (Paper & Clay light / Bridge at Dusk dark). A hardcoded hex is a review reject.
- **EligibilityChips has exactly 4 variants**: `✅ eligible` · `⚠️ conditional` ·
  `⛔ blocked` · `❓ unknown → Ask Counsel`. Nobody invents a fifth.
- **Every deadline shows two clocks**: user-local **and** EAT ("Closes in 2d 14h —
  10:00 your time / 20:00 EAT"). API sends UTC; you localize.
- Typography: Noto Serif (titles) · IBM Plex Sans (UI) · IBM Plex Mono (dates/money)
  · Noto Sans Ethiopic must render (test with "ጨረታ").
- Voice: plain language. "Why this fits you", never tech jargon. `unknown` is said
  plainly, never guessed.

## How you get the API

You **generate** your client — never hand-write models:

```bash
# contract lives at contracts/openapi.json (copied from adera-api; CI keeps it honest)
dart run openapi_generator ...   # or swagger_dart_code_generator — your call, document it
```

First real endpoints: `GET /api/v1/tenders` (keyset-paginated) and
`GET /api/v1/tenders/{id}` — public read-only, no auth yet. Auth + per-user
matches come after; build screens against the public feed first.

## Prepare before repo access

Flutter stable + emulator working · pick your OpenAPI→Dart generator · skim the
screenshots · sketch the feed card (it's the product's soul — worth care).

## Definition of done (any screen)

Tokens only · both themes render · Ethiopic renders · deadlines dual-TZ ·
dismissed never reappears · works on a cheap Android profile.
