# 05 — Backend Development Guide (FastAPI monolith)
*Read top-to-bottom once, then use as a reference while building. Assumes Python basics; explains every framework concept the first time it's used.*

## 1. Environment setup (once)
```bash
git clone <repo> && cd adera
uv sync                        # uv = fast pip/venv manager; deps pinned in pyproject.toml
cp .env.example .env           # fill: DATABASE_URL, REDIS_URL, LITELLM keys, FETCHER secrets
docker compose up -d db redis  # local Postgres 16 (with pgvector) + Redis
uv run alembic upgrade head    # apply migrations
uv run uvicorn app.main:app --reload      # API on :8000, docs at /docs
uv run celery -A app.workers.celery_app worker -Q io,cpu -l info   # second terminal
uv run celery -A app.workers.celery_app beat -l info               # third (schedules)
```
Sanity check: `curl localhost:8000/healthz` → `{"ok":true}`; `/docs` shows the auto-generated OpenAPI UI (every router you add appears there — that page is also your manual-testing console).

## 2. Repository layout (what lives where and why)
```
app/
├── main.py                # FastAPI app factory: mounts routers, middleware, exception handlers
├── core/
│   ├── config.py          # pydantic-settings: typed env vars (Settings class). Never os.getenv elsewhere.
│   ├── db.py              # async engine + session factory + get_session dependency
│   ├── security.py        # password hashing (argon2), session cookie sign/verify, CSRF
│   └── storage.py         # R2 adapter (put/get/presign) behind an interface (ADR-013)
├── modules/<name>/        # one folder per master-plan module
│   ├── models.py          # SQLAlchemy tables owned by this module ONLY
│   ├── schemas.py         # Pydantic request/response models (the API contract)
│   ├── service.py         # business logic; the only public surface other modules may import
│   ├── router.py          # HTTP endpoints; thin: parse → call service → return schema
│   └── tasks.py           # Celery tasks (if the module has pipeline work)
├── kernel/                # AI Kernel: router.py (LiteLLM), prompts.py (registry loader),
│                          # tools.py (tool registry), budget.py, cache.py, traces.py
└── workers/celery_app.py  # Celery config: two queues (io, cpu), beat schedule dict
prompts/  evals/  infra/  web/  docs/
```
The one law: **cross-module imports go through `service.py` only** (NFR-MAINT-1). `matching/service.py` may call `profiles.service.get_profile(org_id)`; it may never `from app.modules.profiles.models import CompanyProfile` to query directly.

## 3. FastAPI concepts → where each implements a feature
- **Router:** groups endpoints (`APIRouter(prefix="/api/v1/tenders")`); mounted in `main.py`. One per module.
- **Dependency injection (`Depends`)** — the concept that makes everything testable: a dependency is a function FastAPI calls per-request and injects. Core three:
```python
async def get_session() -> AsyncIterator[AsyncSession]: ...        # db session per request
async def current_user(sid: str = Cookie(None), s=Depends(get_session)) -> User: ...  # 401 if invalid
async def current_org(user=Depends(current_user)) -> Org: ...      # tenancy anchor (04 §2)
```
Every tenant endpoint declares `org = Depends(current_org)` — forgetting it is the leak class we test against.
- **Pydantic schemas:** request bodies validate themselves (`TenderQuery(BaseModel)` with constrained fields → automatic 422 on bad input); responses declare `response_model=` so you never leak extra columns.
- **Async:** handlers are `async def`; every DB/HTTP call inside is `await`ed. Rule of thumb: if a library call blocks (CPU work, sync SDK), it belongs in a Celery task, not a handler.
- **Middleware & handlers:** request-ID middleware (logs correlate), RFC-7807 exception handler (all errors share one JSON shape), rate limiting on auth/search/Q&A via Redis token bucket.
- **SSE (Q&A streaming):** `StreamingResponse` yielding `f"data: {json.dumps(chunk)}\n\n"` with `media_type="text/event-stream"` — pairs with 07 §6.
- **Auth model (ADR in master plan §12):** web = httpOnly signed session cookie + CSRF token on unsafe methods; Telegram bot = short-lived JWT service account. `security.py` owns both; nothing else touches crypto.

## 4. Module: sources + ingestion (M2) — the pipeline's front door
Key functions and what they do:
- `sources.service.list_due(now)` → sources whose cron says "fetch now" (croniter).
- `ingestion.tasks.fetch_source(source_id)` (queue=io): dispatch by `source.type` → `fetch_static` (httpx+selectolax; 90% of sources) or `fetch_dynamic` (Playwright, headless, only where JS-rendered); writes raw HTML to R2; emits normalized dicts.
- `ingestion.service.upsert_tender(data)` → the idempotent UPSERT (04 §3); returns `(tender, created|updated|unchanged)`; on deadline change writes `tender_revisions` and enqueues re-qualify (FR-2.6).
- Per-source adapter = one file in `ingestion/adapters/` exposing `parse(html) -> list[RawTender]`; adding a source is: adapter file + registry row + golden fixtures. Nothing else changes.
**How to test:** automated — adapter unit tests against saved HTML fixtures (`tests/fixtures/egp_list_page.html`); integration — testcontainers Postgres, run `fetch_source` twice, assert idempotency. Manual — admin "dry-run" button (FR-11.3) calls the adapter and shows parsed rows without writing; or `uv run python -m app.modules.ingestion.cli dry-run egp`.

## 5. Module: documents (M3)
`fetch_document(tender_id, url)` (io) → size-capped download → R2 → `parse_document(doc_id)` (cpu): pypdfium2 text-layer first; if <100 chars/page average → OCR path (Tesseract eng+amh via subprocess) → Docling section tree for chunking (06 §4) → store text + per-page confidence + detected language (FR-3.4). **Test:** fixtures of a text PDF, a scanned Amharic PDF, a table-heavy PDF; assert method chosen, confidence recorded, Ethiopic survives (`assert "ጨረታ" in text`). Manual: drop a PDF into the admin upload probe, eyeball the parse report.

## 6. Modules: extraction + qualification (M4, M5)
- `extraction.service.extract(tender)` → builds prompt B1 from the registry, calls `kernel.complete(task="extract", schema=TenderExtraction)`; kernel enforces Pydantic validation with one repair retry, then routes to review (FR-4.4). Deterministic parsers short-circuit the LLM where the source is already structured (e-GP fields) — free and exact.
- `qualification.service.qualify(tender)` → `prefilter(text) -> Reject|Continue` (pure function, keyword rules — unit-test it exhaustively, it's your money gate) → LLM B2 → persist status/urgency/reasons/model response (FR-5.2).
**Test:** the eval harness *is* the test (Appendix C; 06 §9): `make eval extraction` must pass F1 ≥ 0.90 before a source flag flips to prod. Manual: review queue shows raw-vs-extracted side by side; correcting there writes `golden_labels` — testing that improves the tests.

## 7. Modules: profiles + matching (M6, M7)
- `profiles.service.draft_from_text(text)` → LLM-drafted chips (FR-6.1); `save_profile` re-embeds (BGE-M3, worker task) into `profile_embedding`.
- `matching.tasks.match_tender(tender_id)`: eligibility pre-filter (FR-7.6) → SQL candidate query — filter first, vector-order second:
```sql
SELECT org_id, 1 - (p.profile_embedding <=> :t_emb) AS score
FROM company_profiles p JOIN orgs o USING (org_id)
WHERE o.deleted_at IS NULL AND p.sectors && :tender_sectors
ORDER BY p.profile_embedding <=> :t_emb LIMIT 50;
```
→ threshold → cheap-LLM re-rank + grounded explanation (B3) → insert `matches` (unique tender+org) → enqueue notify.
**Test:** two-org tenancy test (org B never sees org A's match); grounding eval C3 (zero unsupported claims); k6 on the feed after HNSW index exists. Manual: seed script `make seed-demo` creates 3 fake orgs + 20 real tenders; check /feed as each.

## 8. Module: notifications (M8)
`notify.tasks.send_digest(user_id)` — Beat fires an hourly sweep: users whose local time == their digest hour (store `tz` per user; compute with `zoneinfo`, test across DST — NFR-INTL-1). Insert-then-send against the idempotency tuple (04 §3). Channel adapters: `email.py` (Brevo/Resend HTTP), `telegram.py` (aiogram), `calendar.py` (Google, per-user OAuth, idempotent per tender+user). **Test:** freeze time (`freezegun`) at a DST boundary, assert exactly-once per tuple; manual — a `/dev/send-test-digest` admin endpoint mailing yourself.

## 9. Modules: marketplace, engagements, posting (M14, M15, M17)
State machines live in one place each: `engagements/service.py::transition(engagement, event, actor)` validates against an explicit table `ALLOWED = {("requested","quote"):"quoted", ...}` — invalid transitions raise, DB CHECK backs it up (04 §5). KYB (`posting/service.py`): docs → R2 → admin review queue → approve flips `kyb_records.status` and unlocks composer (FR-17.0). Payments launch shape: `payments/rails/base.py` interface (`create_checkout`, `verify_webhook`, `parse_event`) + one MoR implementation; webhook endpoint does the idempotent insert first (NFR-MONEY-2). Money is `amount_minor: int` + `currency` — a lint rule bans `float` in this package (NFR-INTL-2).
**Test:** property test — random valid event sequences never reach an illegal state; webhook replay test (same payload twice → one payment row); manual — MoR sandbox checkout end-to-end on staging (Gate G-PAY dry run).

## 10. Module: billing quotas (M10)
`billing.service.check_quota(org, "qa_messages")` — a `Depends` on quota-gated routes; counts usage rows this period vs plan limits; raises 402-style problem+json with an upgrade hint (FR-10.2). Test: unit (limits math), integration (61st Q&A call on Pro returns the quota error).

## 11. Module: admin + run ledger (M11)
Every pipeline task wraps in `runledger.service.run(kind, source_id)` context manager: opens a row, yields, records counts/cost/latency/error taxonomy on exit — success *or* crash. The admin dashboard is just SELECTs over this table; the daily ops summary (FR-8.5) is a Beat task formatting yesterday's rows. This generalizes the n8n `workflow_runs` pattern you already proved.

## 12. Query optimization habits (the four that matter here)
1. **N+1:** listing 20 tenders then querying qualification per row = 21 queries. Fix: `selectinload(Tender.qualification)` (one extra query total). Detect: log SQL in dev (`echo=True`) and *look* at it once per new endpoint.
2. **Keyset pagination, not OFFSET:** `WHERE (closing_at, id) > (:last_closing, :last_id) ORDER BY closing_at, id LIMIT 20` — stable and O(1) deep-page cost; OFFSET 5000 re-reads 5000 rows.
3. **Indexes follow queries:** every WHERE/ORDER BY combo in a hot path gets a matching (partial) index; verify with `EXPLAIN ANALYZE` — you want Index Scan, not Seq Scan, on big tables. The migration adding the query adds the index.
4. **HNSW knobs:** create with `(m=16, ef_construction=64)`; if recall feels low raise `SET hnsw.ef_search = 100` per session and measure — recall vs latency is a dial, not a mystery.

## 13. Testing map (what kind, where, run how)
| Layer | Tool | Command | Gate |
|---|---|---|---|
| Pure logic (prefilter, state machines, money math) | pytest + hypothesis (property tests) | `make test-unit` | PR |
| DB behavior (upserts, tenancy, quotas) | pytest + testcontainers (real Postgres+Redis in Docker) | `make test-int` | PR |
| API contract | schemathesis against /openapi.json (fuzzes every route from the schema) | `make test-api` | PR |
| AI quality | eval harness (06 §9) | `make eval-smoke` / nightly full | PR smoke; deploy gate |
| E2E happy path | Playwright (signup→profile→match visible) | `make test-e2e` | pre-release |
| Load | k6 (04 §7) | manual vs staging | phase exit |
Manual testing tools you'll live in: `/docs` (Swagger UI — every endpoint, auth-aware, "try it out"), `httpie` (`http :8000/api/v1/tenders limit==5 Cookie:sid=...`), the admin dry-run/probe endpoints, and `make seed-demo`.

## Further reading & credible sources
- **FastAPI docs** — fastapi.tiangolo.com — the tutorial is genuinely the best on dependency injection, Pydantic integration, and async; the "Bigger Applications" page mirrors our router-per-module layout.
- **Pydantic v2 docs** — docs.pydantic.dev — validation, settings management (core/config.py), and JSON-schema behavior the kernel relies on.
- **SQLAlchemy 2.0 ORM docs** — docs.sqlalchemy.org — read the "ORM Querying Guide" section on relationship loading (fixes every N+1) and the async session patterns.
- **Alembic docs** — alembic.sqlalchemy.org — autogenerate caveats and branching; pair with §12's additive-migration rule (09 §4).
- **Celery docs** — docs.celeryq.dev — routing (our io/cpu queues), retries/acks_late, and Beat schedules.
- **Playwright for Python** — playwright.dev/python — selectors, waiting semantics, and headless deployment notes for the dynamic adapters.
- **httpx** — python-httpx.org — async client patterns + timeouts/retries for static fetching.
- **aiogram** — docs.aiogram.dev — the Telegram layer's official reference.
- **Schemathesis** — schemathesis.readthedocs.io — the API-fuzzing tool in the test map, driven by your own OpenAPI schema.
- **testcontainers-python** — testcontainers-python.readthedocs.io — real-Postgres integration tests exactly as §13 wires them.
- **OWASP ASVS** — owasp.org/www-project-application-security-verification-standard — the L1 checklist NFR-SEC-1 points at.
