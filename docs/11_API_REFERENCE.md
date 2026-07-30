# 11 — API Reference (decided surface, v1)
*This is the contract. Every endpoint the platform ships through Phase 5, with method, auth, request, success shape, and error codes. IDs (AUTH-1, ENG-4…) are referenced by the build checklists (doc 12) and belong in commit messages. Anything not in this table does not get built without adding a row first.*

## 0. Conventions (apply to every endpoint)
- **Base path** `/api/v1` (webhooks live at `/webhooks/*`, health at `/healthz`). Versioning by path; v1 is additive-only after Phase 3.
- **Auth levels:** `public` · `user` (valid session cookie) · `org` (user + active org context; the `current_org` dependency — 04 §2) · `fac` (org that is an active facilitator) · `admin`. Unsafe methods (POST/PUT/PATCH/DELETE) from the browser also require `X-CSRF-Token` → missing/bad = **403** `csrf_failed`.
- **Errors:** RFC 7807 problem+json everywhere: `{"type":"…/errors/<code>","title","status","detail","instance"}`. Catalog: **401** `unauthenticated` · **403** `forbidden` / `csrf_failed` / `kyb_required` / `not_a_party` / **`audience_restricted`** (ADR-029: a `local`-type org calling a bidder-only feature — matching, eligibility, digests, Q&A; never a silent empty result) · **404** `not_found` (also used instead of 403 to avoid leaking existence across orgs) · **409** `conflict` (duplicate email, illegal state transition, expired match) · **402** `quota_exceeded` (pragmatic use of Payment Required; body includes `upgrade_hint`) · **422** `validation_error` (FastAPI/Pydantic, field-level detail) · **429** `rate_limited` (Retry-After header) · **500** `internal` (opaque; Sentry id in `instance`).
- **Pagination:** `?limit=20&cursor=<opaque>` → `{"items":[…],"next_cursor":"…"|null}`. Cursors are keyset-based (04 §12), never offsets.
- **Idempotency:** endpoints marked ⟲ accept an `Idempotency-Key` header; same key within 24h returns the stored first response (same status), never a duplicate side effect.
- **Money** in bodies: `{"amount_minor":150000,"currency":"ETB"}`. **Times:** ISO-8601 UTC in; rendering localizes (NFR-INTL-1).

## 1. Auth & account (Phase 1)
| ID | Endpoint | Auth | Request (key fields) | Success | Errors |
|---|---|---|---|---|---|
| AUTH-1 | POST /auth/register | public | email, password, org_name, org_type(local\|diaspora\|foreign), country, tz | **201** {user, org, audience_note} + session cookie — `audience_note` is non-null and states plainly what a `local` org can't do here yet (ADR-029) | 409 email exists · 422 |
| AUTH-2 | POST /auth/login | public | email, password | **200** {user} + cookie | 401 |
| AUTH-3 | POST /auth/logout | user | – | **204** | – |
| AUTH-4 | GET /auth/me | user | – | **200** {user, org, plan, quotas} | 401 |
| AUTH-5 | POST /auth/verify-email | public | token | **200** {verified:true} | 404 bad token |
| AUTH-6 | POST /auth/password-reset(/confirm) | public | email → token,new_password | **202** / **200** | 404 |

## 2. Tenders & public pages (Phase 2)
| ID | Endpoint | Auth | Request | Success | Errors |
|---|---|---|---|---|---|
| TEN-1 | GET /tenders | org | limit,cursor; filters: q(semantic),sector,track,urgency,closing_before/after,eligible_only:bool | **200** page of TenderCard objects (id,title,buyer,closing_at,urgency,fit{score,line},eligibility_chip). **Planned addition, not yet built (ADR-028):** `also_listed_on[]` — other sources carrying this tender's opportunity group, empty for a single-source group. `group_id` already exists on the `tenders` row backing this; the field just isn't exposed on the contract yet. | 401 |
| TEN-2 | GET /tenders/{id} | org | – | **200** full detail: extraction fields+confidences, qualification, eligibility verdict(for org_type), my_match(state), documents[] | 404 |
| TEN-3 | GET /public/tenders/{slug} | public | – | **200** SEO payload (facts, buyer, deadline, source link) — never full doc text | 404 |
| TEN-4 | GET /public/sitemap | public | cursor | **200** {items:[{slug,lastmod}],next_cursor} | – |
| TEN-5 | GET /tenders/sectors | public | – | **200** string[] of distinct `Qualification.sector` values actually present across QUALIFIED tenders (new, 2026-07-30). Feeds the M6 profile builder's sector chip list — a hand-picked list can silently mismatch the LLM's own sector phrasing and produce a permanently empty match feed (`qualification/service.py::get_qualified_tender_ids` filters by exact string); this endpoint is the fix. Must stay routed before TEN-2 or FastAPI parses "sectors" as a tender UUID. | – |

## 3. Profile & matching (Phase 2)
| ID | Endpoint | Auth | Request | Success | Errors |
|---|---|---|---|---|---|
| PRO-1 | POST /org/profile/draft | org | {text} or {url} | **200** draft chips {sectors[],capabilities[],certifications[],regions[],size} | 429 (rate-limited, no quota) — **NOT built**, deferred fast-follow (LLM-drafted chips) |
| PRO-2 | PUT /org/profile | org | confirmed chip sets + description | **200** profile; enqueues re-embed | 422 — **Built and proven live, 2026-07-30** (`app/modules/profiles/router.py`). Re-embed is synchronous in-request today (local CPU BGE-M3), not enqueued to a worker as this row implies — fine at current volume, a future tightening not a contract violation. |
| PRO-3 | GET /org/profile | org | – | **200** | 404 not created — **Built and proven live, 2026-07-30**, two-org isolation tested |
| MAT-1 | GET /matches | org | state=new\|saved, limit,cursor | **200** ranked matches (tender summary + score + explanation) — one per opportunity GROUP, never per source row (ADR-028) | **403 `audience_restricted`** (local org, ADR-029) |
| MAT-2 | POST /matches/{id}/save | org | – | **200** {state:"saved"} | 404 · 409 expired |
| MAT-3 | POST /matches/{id}/dismiss | org | – | **200** {state:"dismissed"} (never resurfaces, FR-7.3) | 404 |

## 4. Eligibility & compliance (Phase 2; matrix Phase 4)
| ID | Endpoint | Auth | Request | Success | Errors |
|---|---|---|---|---|---|
| ELI-1 | GET /tenders/{id}/eligibility | org | – | **200** {verdict, conditions[], citations[{doc,article_ref}], confidence, law_version, disclaimer:true} — computed on miss, cached | 404 |
| ELI-2 | GET /tenders/{id}/checklist | org (Pro+) | – | **200** checklist items[{text,category,mandatory,source_ref}] | 402 on Free |
| ELI-3 | POST /tenders/{id}/matrix | org (Business) | – | **202** {job_id} → GET /jobs/{id} → **200** matrix rows (FR-16.4) | 402 · 409 no docs |

## 5. Notifications & integrations (Phase 2)
| ID | Endpoint | Auth | Request | Success | Errors |
|---|---|---|---|---|---|
| NOT-1 | GET /me/notifications · PUT same | user | channels{email,telegram}, mode(instant\|digest), digest_hour, quiet_hours | **200** prefs | 422 |
| NOT-2 | POST /me/telegram/link | user | – | **200** {deep_link:"https://t.me/AderaBot?start=<code>", expires_at} | – |
| NOT-3 | POST /me/calendar/connect | user | – | **302** Google OAuth; callback GET /integrations/google/callback → **302** /settings?calendar=ok | 409 already linked |
| NOT-4 | POST /tenders/{id}/calendar | org | – | **200** {event_id} (idempotent per user+tender, FR-8.3) | 404 · 409 no deadline |

## 6. Billing (Phase 2 USD rail; ETB post-G-LIC)
| ID | Endpoint | Auth | Request | Success | Errors |
|---|---|---|---|---|---|
| BIL-1 | GET /billing/plans | public | – | **200** plans with prices in both currencies | – |
| BIL-2 | POST /billing/checkout | org | plan_code | **200** {checkout_url} (rail adapter) | 409 already on plan |
| BIL-3 | GET /billing/subscription | org | – | **200** {plan,status,period_end,rail,invoices[]} | – |
| BIL-4 | POST /webhooks/payments/{rail} | public+signature | provider payload | **200** always after idempotent insert (NFR-MONEY-2) | 401 bad signature |

## 7. Q&A over tender documents (Phase 3)
| ID | Endpoint | Auth | Request | Success | Errors |
|---|---|---|---|---|---|
| QA-1 | POST /tenders/{id}/qa | org | {message} | **200** `text/event-stream`; events: `token{text}` → `citation{n,page,section}` → `done{message_id,cost}` \| `error{code}` | 402 quota · 409 no parsed docs · 429 |
| QA-2 | GET /tenders/{id}/qa | org | cursor | **200** message history with citations | – |

## 8. Facilitator marketplace (Phase 3)
| ID | Endpoint | Auth | Request | Success | Errors |
|---|---|---|---|---|---|
| FAC-1 | GET /facilitators | org | service, city, cursor | **200** active facilitators (vetting badge, services, prices, response_time, rating; contacts masked) | – |
| FAC-2 | GET /facilitators/{id} | org | – | **200** profile + reviews | 404 |
| FAC-3 | POST /facilitators/apply | org | headline, services[], coverage[], credentials docs (multipart) | **201** {vetting_status:"applied"} | 409 already applied |
| FAC-4 | PUT /facilitators/me | fac | profile + service menu edits | **200** | 403 |

## 9. Engagements (Phase 3) — state machine over HTTP
Transitions map 1:1 to endpoints; illegal transition = **409** with `{"detail":"cannot quote from state=accepted"}`. All bodies validated; every success also appends an `engagement_events` row.
| ID | Endpoint | Auth | Request | Success (new state) | Errors |
|---|---|---|---|---|---|
| ENG-1 ⟲ | POST /engagements | org | facilitator_id, tender_id?, services[], note | **201** requested | 404 facilitator · 422 |
| ENG-2 | GET /engagements · /engagements/{id} | party | role=bidder\|facilitator | **200** list / detail+events+proofs | 404/403 not_a_party |
| ENG-3 | POST /engagements/{id}/quote | fac | amount_minor, currency, eta_days, scope_note | **200** quoted | 409 |
| ENG-4 | POST /engagements/{id}/accept | org | – | **200** accepted (fee snapshot recorded) | 409 |
| ENG-5 | POST /engagements/{id}/start | fac | – | **200** in_progress | 409 |
| ENG-6 | POST /engagements/{id}/proof | fac | multipart file + kind + note | **201** proof_submitted (artifact→R2, FR-15.6) | 409 · 422 file type/size |
| ENG-7 | POST /engagements/{id}/complete | org | – | **200** completed (accepts proof) | 409 |
| ENG-8 | POST /engagements/{id}/dispute | org | reason | **200** disputed (freezes; admin queue) | 409 |
| ENG-9 | POST /engagements/{id}/cancel | either | reason | **200** cancelled (only pre-accept) | 409 |
| ENG-10 | POST /engagements/{id}/messages | party | text | **201** message (thread) | 403 |
| ENG-11 | POST /engagements/{id}/review | party | rating 1-5, text | **201** (publish rule FR-14.4) | 409 not completed · 409 duplicate |

## 10. KYB & tender posting (Phase 3)
| ID | Endpoint | Auth | Request | Success | Errors |
|---|---|---|---|---|---|
| KYB-1 | POST /kyb | org | multipart: trade_license, commercial_reg, tin | **201** {status:"submitted"} | 409 pending exists |
| KYB-2 | GET /kyb | org | – | **200** {status, expires_at, rejected_reason?} | 404 none |
| PST-1 ⟲ | POST /posts | org | structured tender fields + docs | **201** {moderation_state:"pending"} | **403 kyb_required** · 422 |
| PST-2 | GET /posts | org | cursor | **200** own posts + stats{notified,views,doc_downloads} (FR-17.2) | – |
| PST-3 | POST /posts/{id}/report | org | reason | **202** (anti-scam queue, FR-17.5) | 404 |

## 11. Admin (Phase 1 core; grows with each phase)
| ID | Endpoint | Auth | Purpose | Success |
|---|---|---|---|---|
| ADM-1 | GET/POST/PATCH /admin/sources (+/{id}/dry-run) | admin | source registry CRUD + capped parse preview | 200/201 |
| ADM-2 | GET /admin/runs | admin | run-ledger dashboard data (kind, counts, cost, errors) | 200 |
| ADM-3 | GET /admin/review/extractions · POST /{id} {approve\|correct,fields} | admin | low-confidence queue; corrections write golden_labels | 200 |
| ADM-4 | GET /admin/review/qualifications · POST /{id} | admin | needs_review queue | 200 |
| ADM-5 | GET /admin/spend | admin | AI cost by day/task vs caps (FR-11.5) | 200 |
| ADM-6 | GET /admin/vetting · POST /{facilitator_id} {advance\|reject,notes} | admin | facilitator pipeline (P3) | 200 |
| ADM-7 | GET /admin/kyb · POST /{id} {approve\|reject,reason} | admin | poster verification (P3) | 200 |
| ADM-8 | GET /admin/moderation/posts · POST /{id} {approve\|reject\|takedown} | admin | posting moderation (P3) | 200 |
| ADM-9 | GET /admin/disputes · POST /{id} {resolve,outcome,note} | admin | engagement disputes (P3) | 200 |
| ADM-10 | GET/PATCH /admin/orgs · /admin/users | admin | account management, audited impersonation (P2) | 200 |

## 12. Example contracts (three, canonical)
**AUTH-1 register — 201**
```json
{"user_id":"u_9f2","org_id":"o_41c","org_type":"diaspora","verified":false}
```
**TEN-1 list — 200**
```json
{"items":[{"id":"t_88a","title":"Consultancy for MIS Upgrade","buyer":"Ministry of X",
 "closing_at":"2026-07-24T07:00:00Z","urgency":"HIGH","track":"ICB",
 "fit":{"score":0.87,"line":"Matches your Django e-government delivery history"},
 "eligibility_chip":{"verdict":"conditional","label":"Local JV likely required"}}],
 "next_cursor":"eyJjbG9zaW5nX2F0Ijoi..."}
```
**ENG-3 quote from wrong state — 409**
```json
{"type":"https://adera.bid/errors/conflict","title":"Illegal transition","status":409,
 "detail":"cannot quote from state=accepted","instance":"eng_5d1"}
```
