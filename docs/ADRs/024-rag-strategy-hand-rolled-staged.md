# ADR-024 — RAG strategy: hand-rolled over frameworks, staged traditional → agentic

| | |
|---|---|
| **Status** | Proposed — codifies decisions already recorded in docs/06 §10 and master plan §14 into one citable record, with reversal conditions |
| **Date** | 2026-07-17 |
| **Decision** | (1) ADERA's RAG is **hand-rolled** on pgvector + the AI Kernel — no LlamaIndex/LangChain/vendor RAG stack in the shipped path. (2) RAG capability arrives **staged**: traditional RAG first (Phase 2–3), agentic RAG only in Phase 5 behind the §14 evidence gates. (3) New tooling/articles are evaluated against the checklist in §5 before they may reopen this decision. |
| **What changes** | Nothing in the plan. This ADR exists because the question kept being re-asked with no single home; now it has one. |

## 1. Context

The RAG-framework question has been raised three times in one week (LlamaIndex
generally; a "are you sure" follow-up; an NVIDIA agentic-RAG article). Each time
the answer was re-derived from scratch. The decision needed a durable, citable
record — that is exactly what the ADR mechanism is for (§12.3).

## 2. Why hand-rolled (the five grounds, condensed)

1. **Frameworks solve the easy part.** ADERA's whole RAG orchestration is
   ~150–200 lines (chunks are already in the DB via Docling; retrieval is one
   filter-first SQL query; generation is one `kernel.complete` call; citation
   validation is our own rules). The hard parts — Amharic OCR, structure-aware
   chunking, `article_ref` preservation, law versioning by effective date,
   refusal thresholds, the eval harness — no framework provides.
2. **Storage conflict.** Framework vector stores want to own table layout
   (metadata as JSONB blobs). `law_chunks.article_ref` is a first-class column
   with FKs and effective-date versioning because eligibility verdicts must make
   legal-grade citations. Keeping our schema means writing a custom store
   adapter — i.e. writing the code anyway, plus maintaining framework glue.
3. **The prompt is a compliance surface.** Evals C4/C6 (every citation contains
   its supporting text; failures block deploys) and NFR-LEGAL-1 (refuse below
   confidence) require holding exact chunks, prompts, and citation ids in our
   own hands. Framework prompt-assembly internals sit between us and that, and
   churn across versions.
4. **Kernel bypass.** ADR-014 routes every model call through `app/kernel/`
   (budget breaker, content-hash cache, traces, prompt versioning). Frameworks
   make their own calls: either write a custom LLM adapter (more glue) or lose
   the kernel guarantees. Both are worse than not having the problem.
5. **Dependency weight** on a strict-mypy, solo-maintained codebase, for ~200
   lines of benefit.

**Sanctioned use:** throwaway prototyping of retrieval ideas, ported by hand
into the kernel if they win their eval. Never in the shipped path.

## 3. The staged RAG architecture (what ships when)

| Stage | What | When | Why this order |
|---|---|---|---|
| **L0 — retrieval only (no generation)** | Matching: profile↔tender vector similarity + floor. NOT RAG — no generation step | **Built & judged (Week 3)** | Cheapest proof of the semantic thesis |
| **L1 — traditional RAG** | Tender-doc Q&A (FR-9.3) and eligibility verdicts (FR-16.2): filter-first SQL → context block → one grounded, cited, refusal-capable completion | Phase 2–3 | Interactive features need fast + cheap; the article class itself concedes traditional RAG is "faster and less expensive" |
| **L2 — agentic RAG** | The §14 agent slate — Tender Analyst "Can we win this?" brief, Eligibility Counsel L2: multi-step retrieval, query refinement, RAG-as-tool, over both corpora + profile | Phase 5, behind §14 evidence gates | Async research tasks are where iteration pays for its cost; autonomy advances only through gates, never enthusiasm |

One approved L1 refinement (from the NVIDIA article, the single adoptable
nugget): a **query-rewrite-then-retry** step — when retrieval scores below the
confidence floor, reformulate the query once before refusing. Belongs in doc
06's existing "eval-gated retrieval upgrades" slot alongside contextual
retrieval. Decided by evals when Q&A exists; not before.

## 4. Scale thresholds — when this decision must be revisited (numbers, not vibes)

| Trigger | Current reality | Revisit when |
|---|---|---|
| Vector count | 69 tenders + 3 profiles; law corpus will be thousands of chunks | **>~2M embeddings** or measured latency pain → dedicated vector DB (ADR-006, unchanged) |
| Retrieval QPS | trivial (150–300 users is the 12-month *goal*) | sustained load where P95 <300ms fails **with** HNSW in place |
| Retrieval complexity | single-corpus, filter-first lookups | genuine multi-hop needs across heterogeneous sources that hand-built iteration can't serve |
| Team | solo + AI agents | multiple engineers who need standard framework patterns more than control |
| GPU-accelerated retrieval (NVIDIA-class stacks) | solves problems starting ~tens of millions of vectors / high concurrency | we are 3–5 orders of magnitude away; also infra is a €9 CPU VPS by design (ADR-012) |

## 5. Checklist for evaluating the next article/tool (use this before reopening)

1. **Separate concepts from products.** Vendor posts bundle sound ideas with a
   catalog. Score the *concepts* against the plan; score the *products* against
   our scale (§4) and budget (NFR-COST-1).
2. **Does the plan already contain the concept?** (It usually does: dynamic
   knowledge = the ingestion spine; feedback loops = golden labels + dismiss
   signals; reranking = FR-7.1; agentic = §14.) Cite the FR/§ instead of adding.
3. **Does it solve a problem we measurably have?** Name the metric that hurts.
   No metric → no adoption.
4. **Does it preserve the kernel contract** (budget, cache, traces, prompt
   versions) **and the eval gates?** If it weakens either, it costs more than it
   saves regardless of its benefits.
5. If it survives all four: prototype it behind the kernel, run it against the
   relevant eval, and adopt on a green delta — the same rule as any prompt change.

## 6. Consequences

**Accepted:** we forgo framework conveniences (pre-built loaders, quick
retrieval experiments in prod code) and own ~200 lines of orchestration.
**Gained:** legal-grade citation control, kernel guarantees intact, strict
typing, no version-churn tax, and RAG mechanics the founder can read and learn
from — a stated project goal.

**Rejected alternatives:** LlamaIndex/LangChain in the shipped path (§2);
NVIDIA-class GPU retrieval stacks (§4 — wrong scale by orders of magnitude);
jumping straight to agentic RAG (violates §14's gate doctrine; the interactive
features would pay agentic latency/cost for no benefit).
