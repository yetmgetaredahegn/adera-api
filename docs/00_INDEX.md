# ADERA Documentation Suite — Index & Reading Order

These documents are the working-level companions to the **master plan** (`00_MASTER_PLAN.md`), which remains the source of truth for requirements (SRS), architecture decisions (ADRs), and gates. The master plan says *what and why*; these docs say *how, step by step*. Written so a junior developer — or any new contributor — can pick up a domain cold.

| # | File | Domain | Read when |
|---|---|---|---|
| 01 | BUSINESS_FUNDRAISING.md | Investors, incubators, pitching, equity mechanics, terminology | Before any investor contact; Phase 0 |
| 02 | FINANCE_OPERATIONS.md | Real budget (20k ETB plan), bookkeeping, managing invested funds | Now; monthly ritual |
| 03 | MARKETING_GROWTH.md | Digital strategy per audience (bidders, facilitators, posters, gov) | Phase 0–2 onward |
| 04 | ARCHITECTURE_SYSTEM_DESIGN.md | Architecture style, multi-tenancy, idempotency, soft delete, scalability/bottleneck playbook, load testing | Before writing backend code |
| 05 | BACKEND_GUIDE.md | Repo layout, FastAPI concepts→features, module/function map, DB schema & query optimization, testing | Phase 1 daily companion |
| 06 | RAG_AI_PIPELINE_GUIDE.md | Embeddings→RAG from zero, both corpora, token economy, evals | Phase 1–2 |
| 07 | FRONTEND_GUIDE.md | **Moved → `adera-web/docs/07_FRONTEND_GUIDE.md`** (docs live with the code they describe — ADR-025) | Phase 2–3 |
| 08 | DESIGN_SYSTEM_GUIDE.md | **Moved → `adera-web/docs/08_DESIGN_SYSTEM_GUIDE.md`** (canonical design tokens stay here in `agents/DESIGN.md`) | Phase 2–3 |
| 09 | DEVOPS_DEPLOYMENT.md | Git workflow, CI/CD (GitHub Actions), Docker, deploy strategy, backups, monitoring | Phase 1 setup, then ongoing |
| 10 | SOLO_EXECUTION_TIMELINE.md | Exactly what one person builds first, week by week | Now; revisit weekly |
| 11 | API_REFERENCE.md | Endpoint catalog (`/api/v1`), and the conventions every route obeys: auth, tenant isolation, idempotency, keyset pagination, RFC-7807 errors | Phase 1 onward; whenever wiring frontend to backend |
| — | `ADRs/` | Expanded architecture-decision records. The master plan §12.3 carries the one-line index; a full ADR file is written when a decision needs its reasoning recorded or revised (see `ADRs/001-modular-monolith.md`) | Before proposing any architecture change |
| — | `SECURITY.md` | The canonical threat model: 4 risk pillars, enforced controls, honestly-ranked gaps | Before any security review; before presenting the product externally |
| — | `team/` | Sendable onboarding package: `ONBOARDING.md` + per-role briefs (`BRIEF_MOBILE/WEB/BACKEND/SECURITY.md`) | When someone joins the team |
| — | `agents/SKILLS.md` | Step-by-step recipes for recurring tasks (add a source, change schema, endpoints, prompts, tests, ADRs, UI) — follow exactly; small models work from these only | Before any recurring task type |
| — | `agents/DESIGN.md` | The implementable design contract: tokens (exact hex), typography, component inventory, voice rules, do-not-build deltas | Before any UI work |
| — | `/AGENTS.md` (repo root) | The working contract for any AI agent or contributor: hard rules, environment, traps, the task loop. `/CLAUDE.md` is a thin Claude shim over it; `/HANDOFF.md` (gitignored) is the living session state | First file any agent reads |

## Feature → Module → Doc map
| Feature | Module (master plan §10) | Build docs |
|---|---|---|
| Scraping & ingestion | M2, M3 | 05 §4–5, 09 |
| Extraction & qualification | M4, M5 | 05 §6, 06 §5 |
| Profiles & matching | M6, M7 | 05 §7, 06 §6 |
| Eligibility & law citations | M16 | 06 §7 (law-corpus RAG) |
| Tender-doc Q&A | M9 (FR-9.3) | 06 §8, 07 §6 |
| Notifications (TZ-aware) | M8 | 05 §8 |
| Portal & SEO pages | M9 | 07, 08 |
| Marketplace & engagements | M14, M15 | 05 §9, 04 §6 |
| Verified posting (KYB) | M17 | 05 §9 |
| Billing (dual rail) | M10 | 05 §10, 01 §7 (pricing/investor view) |
| Admin & run ledger | M11 | 05 §11 |

## Conventions used in all docs
- Requirement IDs (`FR-x.y`, `NFR-*`) and ADR numbers refer to the master plan. Where an ADR has an expanded file under `ADRs/`, that file carries the reasoning and the master plan's one-liner is the index entry.
- **Architecture changes are proposed, not implemented** (master plan §12.3 + CLAUDE.md seed rule 3): write an ADR in `ADRs/` and let the founder merge it into the plan — do not edit §12 in place.
- Code blocks are minimal working sketches, not full listings — the surrounding text explains every part so you can extend them.
- "Verify" flags mark facts that must be confirmed at the named Gate before being relied on.
- Every module section ends with **How to test it** (automated + manual).

## Further reading & credible sources
Each doc now ends with a **Further reading** section: curated, annotated links to reach for when stuck or going deeper. Rules used to pick them: official documentation first, then widely-trusted practitioner resources; Ethiopia-specific links verified during research where possible (marked *(verify)* where they should be re-checked before relying on details). URLs valid as of Jul 2026 — if one moves, search its title.
Cross-domain staples worth bookmarking now: the master plan itself · FastAPI docs (fastapi.tiangolo.com) · Next.js docs (nextjs.org/docs) · YC Startup Library (ycombinator.com/library) · e-GP portal (egp.gov.et).
