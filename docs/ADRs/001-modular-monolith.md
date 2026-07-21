# ADR-001 — Modular monolith + workers (not microservices)

| | |
|---|---|
| **Status** | Proposed — supersedes the rationale (not the decision) recorded in Master Plan §12.1 / ADR log 001 |
| **Date** | 2026-07-15 |
| **Decision** | **Unchanged: modular monolith.** One Python codebase deployed as `api` + `worker` + `scheduler` processes over one Postgres 16 (+pgvector) and one Redis, on one VPS via Docker Compose (ADR-012). |
| **What changes** | The *justification*. The v2.1 rationale rejected microservices on headcount. This ADR rebuilds it on structural grounds and defines evidence-based extraction triggers. |

## Context — why this ADR exists

Master Plan §12.1 currently rejects microservices with:

> *"Microservices remain rejected (team of one; the operational tax lands on the founder, not on Claude Code)"*

That is a **staffing accommodation, not an architecture decision**, and it has a defect: it is *contingent on a fact that can change tomorrow*. The moment a second engineer joins, the stated rationale evaporates and the decision is reopened — not because the engineering changed, but because the org chart did. A decision that inverts on headcount was never load-bearing.

The decision itself is correct. The reasoning needed to be replaced with grounds that survive the team growing.

## Decision — four structural grounds, none of which is team size

**1. The money path is a single-transaction invariant.**
`engagement ↔ payment ↔ ledger` is governed by NFR-MONEY-1: double-entry, sum-zero per transaction, no negative available balance, enforced in code + property tests, violation = SEV1. In one Postgres this is **one transaction** — the invariant is enforced by the database. Splitting `engagements`, `payments`, and the ledger across services converts it into a saga/outbox distributed-transaction problem requiring compensating actions **over money**. That is strictly harder to get right, and it is harder *at any headcount*. Three engineers do not make eventual consistency over a double-entry ledger easier; they make it easier to *staff the incident*.

**2. The read paths are cross-domain joins.**
The feed joins `tenders × matches × orgs × eligibility_verdicts`. Retrieval filters metadata **before** vector ordering (`WHERE effective_date <= now() AND superseded_at IS NULL ORDER BY embedding <=> :q` — 06 §6), which is what makes it both fast and correct. Eligibility joins `law_chunks` against tender extractions. A service split turns each of these into N+1 network calls or a CDC/data-duplication pipeline, and costs the query planner the single thing that makes them cheap. **This system is join-heavy across domain boundaries** — a genuine anti-indicator for service extraction.

**3. The one real forcing function is already solved — without microservices.**
ADERA *does* have heterogeneous workloads: an IO-light `api` versus CPU-heavy OCR/embedding. That is the legitimate case for splitting things apart, and it is **already handled** by the `api` / `worker` / `scheduler` process split with separate `io` / `cpu` queues, built from one image. That split already buys:
- independent scaling (`worker` replicas scale without touching `api`),
- independent restart and deploy of each role,
- crash isolation — a runaway Playwright scrape cannot take down the API.

Microservices would **re-buy what we already own, at the price of a network hop**. Note the shape of the current architecture: three processes, one codebase. It is not "a monolith" in the naive single-process sense — the operational benefits people reach for microservices to get are already present.

**4. No other trigger fires.**
- **Polyglot:** none. The differentiating OCR / extraction / embedding / eval work is Python-ecosystem (ADR-002).
- **Deploy cadence:** no independent-release pressure; the web tier is already a separate Next.js deploy.
- **Scale:** ~40 new tenders/day against a 12-month target of 150–300 subscribers is a single-Postgres workload with orders of magnitude of headroom. There is no data-volume or QPS forcing function within the planning horizon.

## On team size — recorded once, so it is never re-litigated

Adding engineers changes **who can absorb** the operational tax of a distributed system. It does not change **whether paying that tax buys anything**.

At 2–4 engineers, a shared codebase with lint-enforced module boundaries (NFR-MAINT-1) is an **asset, not a liability**: everyone can read and fix everything, and context is shared by default. Eight services would hand each engineer services they never touch and cannot safely change. Microservices begin to earn their keep when the *coordination cost of one codebase* exceeds the *operational cost of a network* — and that crossover is a function of **team count** (multiple independent teams with divergent release cadences), not team size. ADERA is not close to it, and a second or third engineer does not move it closer.

**Binding rule: if this decision is revisited, it must be revisited on the four grounds above. Headcount is not admissible evidence — in either direction.**

## What actually preserves optionality

The bet is not "monolith forever." It is **keep the seams real and defer the split until evidence demands it**. What makes that bet safe is NFR-MAINT-1: modules (`identity · sources · ingestion · documents · extraction · qualification · profiles · matching · notifications · portal_api · billing · admin · runledger · marketplace · engagements · payments · eligibility · posting`) talk through **service interfaces only, lint-enforced — no cross-module table writes**.

That rule is doing the load-bearing work here, and it becomes *more* important as the team grows, not less. A module boundary that is enforced by a linter is a service boundary that has not yet paid for a network. If the boundaries stay honest, extraction is a refactor. If they rot, no architecture saves us.

## Extraction triggers — evidence, not intuition

Consistent with the project's gate doctrine, each seam fires on a **measured** condition:

| Seam | Fires when |
|---|---|
| **`payments`** (first out) | Custodial fund-holding actually goes live **AND** an audit/compliance boundary demands isolated blast radius. Gated by ADR-020 sequencing (invoiced lead-gen → provider-held milestones → escrow only post-counsel). |
| **`ingestion`** | Untrusted-content sandboxing or resource contention outgrows what queue separation and process isolation already provide (NFR-SEC-2). |
| **Realtime gateway** | A validated live feature appears (ADR-011 — sealed-bid reality currently makes this moot). |
| **Vectors → Qdrant** | Past ~2M embeddings **or** measured pgvector latency pain (ADR-006). |
| **Any module** | Two engineers are **measurably** blocked on each other's deploys — measured over a real period, not predicted. |

## Consequences

**Accepted:** one Postgres is a single failure domain (mitigated by DR-1: RPO 24h / RTO 4h, rehearsed); the whole `api` deploys together; a module boundary violated in review is not caught by the network, so the lint rule must stay green and enforced.

**Gained:** money correctness by database transaction rather than by distributed-systems engineering; cross-domain joins stay joins; one `docker compose up` local environment; shared context across whatever the team becomes; extraction remains available at the seams when evidence arrives.

## Rejected alternatives

- **Microservices now** — rejected on the four grounds above.
- **Extract `payments` preemptively** — rejected: no custodial funds exist at launch (FR-15.2: platform holds no client funds), so it would isolate a blast radius that is currently empty. Revisit at the ADR-020 escrow gate.
- **Kubernetes** — rejected (ADR-012): orchestration for a scale problem we do not have.
- **Polyglot services** — rejected (ADR-002).
