# 06 — RAG & AI Pipeline Guide (from foundations to production)
*Teaches the concepts once, then builds ADERA's two RAG systems and the token-economy discipline around them. This is the one doc where models are discussed, because here they're the machinery.*

> **Built vs planned:** this guide describes *how* to build; what is actually implemented right now lives in `PROGRESS.md` (this repo). A section here describing a feature does not imply it exists yet.

## 1. Foundations in five paragraphs (skip if you know RAG)
**Embedding:** a model turns text into a vector (list of ~1024 numbers) where *similar meaning → nearby vectors*. "web development tender" and "website design bid" land close together even sharing few words — this is why semantic search beats keywords for A2's problem.
**Vector search:** store vectors in Postgres via **pgvector**; `ORDER BY embedding <=> :query_vec` returns nearest neighbors (`<=>` = cosine distance). An **HNSW index** makes this fast at scale (a graph structure that hops toward the neighborhood instead of scanning everything).
**RAG (Retrieval-Augmented Generation):** instead of asking an LLM from memory (it will guess), you (1) retrieve the most relevant chunks of *your* documents, (2) paste them into the prompt as context, (3) instruct: answer **only** from this context, cite it, and say "not found" when it isn't there. RAG = search + constrained generation. It exists to kill hallucination and to keep knowledge updatable without retraining.
**Chunking:** documents are too big for prompts, so you split them into retrievable pieces. Bad chunking (blind 1000-char cuts) severs tables from headers and articles from their numbers; good chunking follows document structure.
**Why not fine-tune instead?** Fine-tuning changes a model's *style/skill*, not its *knowledge recall*, and it can't cite. ADERA's problems (find the clause, quote the requirement) are retrieval problems. Fine-tuning is a Phase-∞ tool, only if evals prove a gap RAG can't close (master plan stance).

## 2. Where RAG appears as product features (so you build with purpose)
| Feature | Corpus | FR |
|---|---|---|
| Tender-document Q&A ("what are the financial eligibility criteria?") | That tender's parsed documents | FR-9.3 |
| Eligibility verdicts with legal citations | Versioned law corpus (Proclamation 1333/2024, directives) | FR-16.2 |
| Compliance-matrix extraction | Tender docs (retrieval-guided shredding) | FR-16.4 |
| "Can we win this?" brief (Phase 5 agent) | Both corpora + org profile | §14 master plan |
Matching (FR-7.1) uses embeddings but is **not** RAG — it's pure vector similarity + a re-rank; no generation over retrieved text. Keep the distinction; it saves tokens (§10).

## 3. The kernel is the only door
Every embedding and completion goes through `app/kernel/` (ADR-014): `kernel.embed(texts)`, `kernel.complete(task, schema|None, context)`. The kernel owns model routing (LiteLLM), prompt-registry loading, Redis response cache, budget/circuit-breaker, and trace logging. **Never call a provider SDK from a module.** This one rule is what makes cost control, evals, and provider swaps possible later.

## 4. Stage 1 — Chunking (both corpora)
Tender docs: Docling gives a section tree (headings, paragraphs, tables). Walk it: a chunk = one section's text, split further only if > ~900 tokens, with 80-token overlap between splits; **tables stay atomic** (never split a table row from its header); each chunk records `{doc_id, section_path, page, text}`. Law corpus: chunk = **one article/sub-article** (the citation unit), recording `article_ref` — this is what makes FR-16.2 citations exact. Token counting: `tiktoken`-style counter in the kernel; you care about budgets, not exactness.
Test: fixture PDFs → assert no chunk > limit, tables intact, every law chunk has an `article_ref`.

## 5. Stage 2 — Embedding & storage
BGE-M3 via sentence-transformers, loaded once per worker process (module-level singleton — reloading per task would murder throughput), CPU is fine at our volume. Batch 32–64 texts per call. Write to `law_chunks.embedding` / tender-chunk table / `profile_embedding` (vector(1024)). Index after bulk-load, not before:
```sql
CREATE INDEX ON law_chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
```
Cost: **$0 marginal** — this is why unlimited eligibility verdicts on the $79 tier is economically safe (02 §6).

## 6. Stage 3 — Retrieval (filter first, then order by distance)
```sql
SELECT c.text, c.article_ref, 1-(c.embedding <=> :q) AS score
FROM law_chunks c JOIN law_docs d ON d.id=c.law_doc_id
WHERE d.effective_date <= now() AND d.superseded_at IS NULL      -- metadata filter FIRST
ORDER BY c.embedding <=> :q LIMIT 8;
```
Two habits: (1) SQL filters (tender_id for Q&A, effective law version for eligibility) *before* vector ordering — smaller candidate set, better precision, faster; (2) a **floor**: if the best score < ~0.45 (tune on your eval set), treat as "not found" and refuse — this single check implements most of NFR-LEGAL-1's honesty.

## 7. Stage 4 — Generation with citations (the two prompts)
Q&A (B4) context block format the model must echo in citations:
```
[1] (page 4, §2.3) "...bid security of 2% of contract value..."
[2] (page 9, §5.1) "..."
Question: {q}
Rules: answer only from the excerpts; cite [n] per claim; if not answered by them, say so and name the closest section.
```
Eligibility (B6): same shape over law chunks; output is the Pydantic verdict schema `{verdict, conditions[], citations[{doc, article_ref}], confidence}`; the kernel validates; uncited claims fail eval C6 and block deploy. Streaming: Q&A generates via SSE (05 §3) so first tokens appear <3s (NFR-PERF-1) while the full answer forms.

## 8. Not wasting tokens — the economy, mechanized
1. **Don't call the model** — the biggest saving: prefilter rejects ~50–60% of tenders before any LLM (FR-5.1); matching is embeddings-only; deterministic parsers beat extraction prompts on structured sources.
2. **Tier the models** (LiteLLM route table): extraction/qualification/re-rank → cheapest capable tier; explanations/Q&A/eligibility → mid tier; nothing defaults to a frontier model. Changing a tier is config, measured by evals, not vibes.
3. **Cache by content hash:** Redis key `sha256(task+prompt_ver+model+input)`; tender analyzed once is free for every subsequent viewer. Popular tenders make this your highest-ROI line.
4. **Trim the input, not the answer:** send retrieved chunks, never whole documents; cap k; strip boilerplate pre-embedding.
5. **Cap the output:** `max_tokens` per task class; JSON-schema outputs stop models from writing essays.
6. **Budget + breaker:** per-tender, per-org, per-day counters in the kernel; breaker pauses the pipeline and alerts instead of overspending (NFR-COST-1). The spend dashboard (FR-11.5) shows cost/task/day — read it weekly like a bill, because it is one.
Worked math: 40 new tenders/day → ~16 reach the LLM → extraction+qualification ≈ $0.004 avg → **≈ $2/mo**; 500 cached-miss Q&A answers ≈ $10–25/mo. The card is safe.

## 9. Evals — how AI quality is tested like code
Golden sets are JSONL in `evals/golden/` (grown by every admin correction — the review queue is a labeling machine). Scorers per Appendix C: extraction field-F1, qualification P/R, grounding (C3/C6: every claimed fact must appear in context — rule check + judge pass), Q&A faithfulness + refusal-correctness on the unanswerable subset, eligibility accuracy with **zero confident-wrong on `unknown`-labeled items**. Wiring: `make eval-smoke` (20 samples) on every PR; nightly full run reports deltas; a prompt-version bump that regresses its bound eval **fails CI**. This is the difference between "the AI seems fine" and an AI product.

## 10. LlamaIndex (and friends) — the framework decision, stated
You know LlamaIndex; here's the honest call: **not in ADERA's core.** Reasons specific to this product: (a) the pipeline above is ~300 lines you fully understand — a framework's abstractions (Indices, Retrievers, QueryEngines) add a dependency surface and version churn without removing real work here; (b) evals and the budget/citation rules need bare-metal control of prompts and retrieval SQL — fighting a framework's internals to enforce C6 is worse than owning the code; (c) chunking, our hardest part, is Docling's job either way. Where LlamaIndex *is* fine: throwaway prototyping of a retrieval idea before porting it into the kernel. If a future need appears (complex multi-hop retrieval, graph RAG), adopt it *behind* the kernel interface so nothing else changes. Same verdict for LangChain, same reasoning.

## Further reading & credible sources
- **pgvector** — github.com/pgvector/pgvector — the single most important reference here: operators, HNSW vs IVFFlat, index parameters, and filtering guidance.
- **BGE-M3 model card** — huggingface.co/BAAI/bge-m3 — multilingual coverage, dimensions, and usage snippets for the embedding layer.
- **sentence-transformers docs** — sbert.net — batching, pooling, and CPU-inference patterns for §5.
- **LiteLLM docs** — docs.litellm.ai — router config, fallbacks, cost tracking; the kernel's model-routing layer.
- **Docling** — github.com/docling-project/docling — layout-aware parsing that powers §4's chunking *(repo org verified as of writing; if moved, search "Docling document parser")*.
- **Tesseract + Amharic traineddata** — github.com/tesseract-ocr/tesseract and github.com/tesseract-ocr/tessdata (amh.traineddata) — the OCR baseline of the bake-off.
- **Anthropic: Contextual Retrieval** — anthropic.com/news/contextual-retrieval — a practical, well-evidenced upgrade to plain chunk retrieval; worth testing behind the kernel once basics are green.
- **Hamel Husain: "Your AI product needs evals"** — hamel.dev/blog/posts/evals — the philosophy §9 implements; the best single essay on eval-driven AI development.
- **Eugene Yan's applied-LLM patterns** — eugeneyan.com — grounded write-ups on RAG failure modes, reranking, and evaluation metrics.
- **OpenAI Cookbook** — cookbook.openai.com — provider-agnostic despite the name for RAG/chunking recipes; translate snippets to the kernel interface rather than importing patterns wholesale.
- **OWASP Top 10 for LLM Applications** — owasp.org/www-project-top-10-for-large-language-model-applications — prompt injection and insecure-output handling: the threat model behind NFR-SEC-2.
