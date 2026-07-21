# 04 — Architecture & System Design Companion
*Practical expansion of the master plan SAD (§12) — the concepts a developer must hold while building, each with the ADERA-specific decision and its tradeoffs.*

## 1. Architecture style (what and why, one paragraph deep)
**Style: modular monolith + asynchronous workers.** One Python codebase, deployed as three processes from one image: `api` (FastAPI, stateless, user-facing), `worker` (Celery, runs the pipeline), `scheduler` (Celery Beat, fires crons). They share one Postgres and one Redis. "Modular" is enforced, not aspirational: modules expose service functions; importing another module's models for a write is a lint failure (NFR-MAINT-1). This gives monolith simplicity (one deploy, one DB transaction across engagement+payment+ledger) with microservice-grade seams documented for later extraction (ADR-001, §12.1). Alternatives and why not: microservices (operational tax lands on one founder; no independent-scaling need at ≤500 tenders/day), serverless (cold starts + long-running Playwright/OCR jobs fit badly), polyglot (splits the AI-ecosystem work — ADR-002).

## 2. Multi-tenancy — the decision and its tradeoffs
ADERA is multi-tenant (many orgs, one deployment). Three standard models:
| Model | How | Pros | Cons |
|---|---|---|---|
| **Shared schema, org_id column (CHOSEN)** | Every tenant-owned row carries `org_id`; every query filters by it | One DB, cheap, simple migrations, cross-tenant analytics trivial | A missing filter = data leak; discipline required |
| Schema-per-tenant | One Postgres schema per org | Stronger isolation | Migration fan-out, connection complexity — pain at 100+ orgs |
| DB-per-tenant | One database per org | Max isolation | Operational absurdity for a solo founder |
**Enforcement of the chosen model:** (1) a required `current_org` FastAPI dependency that every tenant route uses; (2) repository/service helpers that take `org_id` as a mandatory first argument — raw queries on tenant tables outside these helpers fail review; (3) tests that create two orgs and assert cross-visibility is impossible for every tenant endpoint (write these as you write the endpoint, not later); (4) optional Phase-4 hardening: Postgres Row-Level Security policies as a second net. Note the nuance: `tenders` are **global** (shared corpus, no org_id); `matches`, `profiles`, `engagements`, `qa_messages` are **tenant-owned**. Knowing which table is which is half of tenancy.

## 3. Idempotency (why the pipeline can be re-run fearlessly)
Definition for juniors: an operation is idempotent if running it twice produces the same state as once. Where ADERA needs it and the mechanism used:
- **Ingestion:** `UPSERT ... ON CONFLICT (source, source_tender_id)` — re-scraping never duplicates (FR-2.3).
- **Notifications:** unique index on `(user_id, tender_id, channel, event_type)`; insert-before-send; a crash after insert but before send is recovered by a sweep job, never by double-sending (FR-8.4).
- **Payment webhooks:** unique `provider_ref`; handler does `INSERT ... ON CONFLICT DO NOTHING` first and exits quietly on replay (NFR-MONEY-2). Providers *will* replay events; this is not theoretical.
- **Client mutations (Phase 3+):** accept an `Idempotency-Key` header on POST /engagements; store key→response for 24h; identical key returns the stored response.
Test pattern for all four: run the operation twice in a test; assert row counts and state are identical to once.

## 4. Soft delete — policy, not reflex
Mechanism: `deleted_at timestamptz NULL`; "delete" sets it; all reads filter `WHERE deleted_at IS NULL`; unique constraints become partial (`UNIQUE ... WHERE deleted_at IS NULL`) so a re-created org slug doesn't collide with a deleted one. **Where it applies:** orgs, users, profiles, facilitator listings, saved searches — things people delete and regret. **Where it must NOT apply:** `engagements`, `payments`, `ledger_entries`, `proof_artifacts`, `kyb_records`, `run_ledger` — these are audit history; they get terminal *states* (cancelled, refunded), never deletion. **Hard delete** exists only as the privacy-erasure job (NFR-PRIV-1): a scheduled task that irreversibly scrubs PII for verified requests, logging what was scrubbed (not the values).

## 5. System-design principles applied (name → where you'll meet it)
Single source of truth (Postgres; Redis is always rebuildable cache/queue) · queues decouple (a dead OCR task can't take down the API) · backpressure (Celery rate limits per source; LLM budgeter pauses the pipeline rather than melting the card) · fail loud, degrade gracefully (digest still sends without the one tender whose extraction failed; admin gets the alert) · make invalid states unrepresentable (DB CHECK constraints on every state machine; transitions validated in one service function per machine) · idempotency everywhere (§3) · observability as a feature (run_ledger is product, not plumbing).

## 6. Bottleneck & scalability playbook (symptom → diagnosis → fix, in order of likely appearance)
| Symptom | Likely cause | First fix (cheap) | Later fix |
|---|---|---|---|
| Pipeline > 60 min (NFR-PERF-2) | OCR/Playwright CPU-bound in shared worker | Split queues: `io` (many concurrent) vs `cpu` (concurrency=cores); Beat stays tiny | Second worker container; then dedicated parse worker (seam §12.1) |
| Feed/search P95 > 300 ms | Missing index or N+1 queries | `EXPLAIN ANALYZE` the query; add index; `selectinload` relationships (05 §12) | Redis cache on hot feeds (60s TTL) |
| Match query slow at scale | HNSW recall/params vs table size | Filter candidates first (is_open, sector) *then* vector-order; tune `hnsw.ef_search` | Move vectors to dedicated store past ~2M (ADR-006 trigger) |
| Digest fan-out slow at 08:00 | Per-user serial sends | Batch: one query for all due users, chunked Celery group | Provider bulk-send APIs |
| LLM latency spikes | Provider variance | Streaming UX (SSE) hides it; queue non-interactive calls | LiteLLM fallback routing to second provider |
| Disk fills | Raw HTML/PDF hoarding | R2 lifecycle rules (18-mo), DB keeps pointers | — |

## 7. Load testing with k6 (how to actually use it)
k6 = scriptable load generator; free CLI. Install once on your laptop (not the VPS). Minimal script `evals/load/feed.js`:
```js
import http from 'k6/http'; import { check, sleep } from 'k6';
export const options = { stages: [ { duration: '1m', target: 20 }, { duration: '3m', target: 50 }, { duration: '1m', target: 0 } ],
  thresholds: { http_req_duration: ['p(95)<300'], http_req_failed: ['rate<0.01'] } };
export default function () {
  const r = http.get(`${__ENV.BASE}/api/v1/tenders?limit=20`, { headers: { Cookie: __ENV.SESSION } });
  check(r, { 'status 200': (x) => x.status === 200 }); sleep(1);
}
```
Run: `k6 run -e BASE=https://staging.adera.bid -e SESSION="sid=..." evals/load/feed.js`. Read the output: `http_req_duration p(95)` is your NFR-PERF-1 number; a failing threshold exits non-zero (CI-able). Ritual: run against **staging** before each phase exit, after any index change, and never against prod during business hours. When p95 fails: reproduce the slow endpoint locally → `EXPLAIN ANALYZE` → fix → re-run k6 → record the before/after in the PR.

## 8. Usability bottlenecks (yes, they're architecture too)
Slow first paint on 3G kills A2 adoption → SSR + <100 KB public pages is an architectural budget, enforced in CI by Lighthouse (07 §8). Timezone bugs destroy A1 trust faster than downtime → UTC-in-storage rule + the DST test matrix (NFR-INTL-1) are non-negotiable. Ethiopic mojibake anywhere = instant credibility loss → UTF-8 assertions live in the extraction tests, and a render screenshot test covers the UI (08 §6).

## Further reading & credible sources
- **Martin Fowler — MonolithFirst & microservice prerequisites** — martinfowler.com/bliki/MonolithFirst.html (and /articles/microservice-trade-offs.html) — the reasoning behind ADR-001, from the source.
- **The Twelve-Factor App** — 12factor.net — config, processes, logs: the discipline the compose setup follows.
- **System Design Primer** — github.com/donnemartin/system-design-primer — free, broad reference when a §5 principle needs depth.
- **Designing Data-Intensive Applications (Kleppmann)** — the book for when you outgrow the primer; chapters on encoding, replication, and transactions age well.
- **Stripe on idempotent requests** — docs.stripe.com/api/idempotent_requests — the pattern §3's Idempotency-Key design copies; also brandur.org/idempotency-keys for the deep treatment.
- **Postgres docs: indexes & EXPLAIN** — postgresql.org/docs/current/indexes.html and /using-explain.html — read once, then keep open while doing §6/§7 work.
- **pgvector README** — github.com/pgvector/pgvector — HNSW parameters, operators, and index-build guidance straight from the maintainer.
- **k6 documentation** — grafana.com/docs/k6 — thresholds, stages, and result interpretation beyond the §7 starter script.
- **AWS Multi-tenant SaaS lens (whitepaper)** — search "AWS SaaS Lens multi-tenant" — vendor-flavored but the clearest articulation of the tenancy models compared in §2.
