# ADR-027 — Source-access legality: never authenticate to collect data

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-07-23 |
| **Decision** | ADERA never authenticates (logs in, drives a credentialed session) in order to collect data from any source, ever. Collection is limited to public, unauthenticated APIs and pages, or data obtained under an explicit agreement. |

## Context

The ingestion plan for e-GP (`egp.gov.et`), Ethiopia's primary tender source,
assumed logging in with the founder's own credentials and driving the site with
Playwright (`app/modules/sources/service.py`, the `egp` seed entry;
`docs/team/ONBOARDING.md:45`). That assumption predates this ADR and was never
checked against Ethiopian law.

Ethiopia's **Computer Crime Proclamation No. 958/2016** criminalizes accessing a
computer system "without authorization or in excess of authorization." A user
account grants a person specific, limited authorization (view your own bids,
download assigned documents, submit files). Running an automation script inside
that account to systematically extract data plausibly **exceeds** that
authorization — a different, and more serious, act than reading a page nobody
had to log in to see.

This stopped being a hypothetical the moment the product's own plan is to
present ADERA to the ministry-adjacent institution that operates e-GP (PPA).
Describing, in that room, a system that scrapes their portal using a borrowed
session is both a legal exposure and a trust failure with the one audience whose
goodwill the roadmap depends on.

**This ADR does not resolve the legal question — it proposes the engineering
posture and requests the review that determines whether it's the right one.**
The security engineer's first task (`docs/proposals/FIRST_TASK.md`, Prompt A) is
to research 958/2016 and validate or demolish this decision before it hardens.
Final confirmation, if the founder wants the assessment to carry legal weight,
routes to the counsel consult already budgeted in `docs/00_MASTER_PLAN.md:144`.

## Decision

1. **Never authenticate to collect.** No product code logs into any third-party
   platform for the purpose of automated data extraction, regardless of whether
   the founder personally holds valid credentials for that platform.
2. **Three access patterns are treated as legally distinct, not one:**
   - **Public API** (e.g. World Bank procurement API) — lowest risk, already in use.
   - **Public, unauthenticated page** — e.g. UNGM notices, institutional tender
     pages, e-GP's public bid listing if one exists without login. Requires
     conservative rate limits and identified User-Agent regardless.
   - **Credentialed session automation** — never done, full stop, independent of
     whether the target is a government portal or a commercial site.
3. **Commercial aggregators (2Merkato, AfroTender) are out of scope entirely** —
   independent of the authentication question. AfroTender's `robots.txt`
   explicitly disallows `/tenderslist` and `/tendersview/`, a clear-cut
   prohibition; 2Merkato's ToS and database-compilation rights make it hostile
   regardless of robots directives. Neither is worth the exposure for data we can
   get from primary sources instead.
4. **The gap this creates is the opening, not a cost.** The volume difference
   between "everything on e-GP" and "public World Bank + donor + institutional
   sources" is real — but it converts into a concrete, fundable ask: request
   official data access (an API, a feed, a data-sharing MoU) from PPA. That ask
   is stronger, not weaker, for being made by a company that can honestly say it
   never scraped them without permission.

## Schema consequence (deferred until accepted)

`Source.fetch_config` (JSONB) currently hides the access-basis assumption in
free-text prose — the `egp` seed literally says *"authenticated Angular SPA;
needs Playwright + login"* inside an untyped field. Proposed: add a typed
`access_basis` field to `Source` —
`public_api` / `public_page` / `agreement` / `prohibited` — so the legal basis of
every source is a queryable fact, not prose. `ToSStatus` gains a companion
distinction between *"publicly accessible"* and *"authorized by agreement."*
**No migration is written until this ADR is accepted** — this is a proposal, not
an implementation, per AGENTS.md rule 14.

## Rejected alternatives

- **Authenticated e-GP scraping via Playwright** — the exposure this ADR exists
  to avoid. Even at a polite rate, it plausibly exceeds account authorization
  under 958/2016; also fragile (Angular SPA, session/cookie churn) and a
  reputational risk with the platform's own regulator.
- **Scraping 2Merkato/AfroTender** — robots.txt prohibition (AfroTender),
  commercial ToS + database rights + direct-competitor tort exposure (both).
  Not worth it for data reachable from primary sources.
- **Wait for official access before shipping anything further** — unnecessary:
  World Bank's API, UNGM's public notices (filterable by Ethiopia, no login),
  and institutional tender pages already provide real, legally clean volume
  today. The product does not need to stall on this.

## Consequences

**Gained:** a defensible, presentable posture for the exact audience (PPA/MInT)
the founder is about to sit in front of; a sharper, cheaper counsel consult
(a narrow confirmation instead of an open-ended question); a natural opening to
request official access instead of quietly working around its absence.

**Accepted:** materially less tender volume than authenticated e-GP scraping
would provide, until either official access is granted or e-GP is confirmed to
expose a genuinely public, unauthenticated listing worth adapting to (open
question — see below).

**Open questions for the security engineer / founder to close:**
- Does e-GP expose *any* tender data without login? (Public pages needing a
  headless browser to render are still fair game under this ADR — only
  credentialed automation is excluded.)
- What does "in excess of authorization" mean in Ethiopian enforcement practice,
  concretely, for a case like this? (Prompt A's research question.)
- Is a federal procurement platform the kind of system where enforcement is
  more or less likely than for a private site? (Also Prompt A.)

## Reversal condition

An explicit written agreement with PPA (an API key, a data-sharing MoU, a
sanctioned integration) supersedes this ADR's restriction for that specific
relationship — which is the point of making the ask.
