# AGENTS.md — working contract for {{PROJECT_NAME}}

**Audience: any AI agent or human contributor.** Read once (~4 min), then load only
what your task needs (§3). Keep this file ≤ 300 lines — push detail to Layer 3 docs.

## 1. What this project is

{{2–4 sentences: what it does, for whom, the architecture in one line.}}
**Source of truth:** {{path to spec/plan}}. Requirements cited as {{id scheme, e.g.
FR-x.y / ADR-nnn}} — cite these ids in code comments and reports.

## 2. Session start ritual (always)

1. Read `HANDOFF.md` (root, gitignored). Missing? Run
   {{`git log --oneline -15`, the check command}}, then recreate it from §9.
2. Treat HANDOFF claims as hints — re-verify load-bearing ones with commands.
3. Restate your task: one sentence + requirement ids + Definition of Done.
   No matching requirement and not explicitly asked? **Stop and ask.**

## 3. Context loading table

| Task type | Load (in order) | Do NOT load |
|---|---|---|
| Any task | `HANDOFF.md` → this file | {{lockfiles, generated dirs, huge design exports}} |
| {{backend feature}} | {{SKILLS recipe → backend guide → named requirement}} | the whole spec |
| {{UI work}} | {{DESIGN.md → frontend guide}} | raw design files |
| {{…}} | {{…}} | |

## 4. Hard rules (MUST/NEVER — each with its why and an id)

1. {{RULE}}. *Why:* {{one line}} ({{id}}).
2. {{RULE}}. *Why:* {{one line}} ({{id}}).
3. **Verify, don't trust:** every "done" claim needs command output as evidence.
4. **Git: never commit/push unless the human explicitly asks.** {{adjust to taste}}
5. **Escalate, don't implement silently:** {{list the human-only decision areas}}.
{{5–10 total. Each must trace to a real constraint or a real past bug — delete
generic advice.}}

## 5. Environment facts

| Fact | Value |
|---|---|
| Services / ports | {{…}} |
| Bring stack up | {{command}} |
| Full static check | {{command — the CI-equivalent gate}} |
| Run the app / pipeline by hand | {{commands}} |
| Inspect ground truth (DB/API) | {{command}} |
| Secrets present / absent | {{e.g. "no LLM key — paths needing one are built-but-unexercised"}} |

## 6. Known traps (every bug that cost >15 min gets a line)

- {{trap}} → {{fix / where it's pinned by a test}}

## 7. The loop (every task)

1. Restate (task + ids + DoD). 2. Plan the file list (>~6 files → decompose).
3. Recipe first (`docs/agents/SKILLS.md`); freehand only without one — then add one.
4. Implement the smallest complete slice; match surrounding style.
5. Verify: static gate AND behavior proof (run it; paste output).
6. Update `HANDOFF.md`. 7. Report: proven / unexercised / assumed — never
   unverified "done".

### If you are a smaller model
Recipes only. No new architecture, schemas, or prompts. No recipe → write a plan
and stop for review.

## 8. Documentation map

| File | What it is |
|---|---|
| {{spec}} | source of truth |
| `docs/agents/SKILLS.md` | recipes |
| `docs/agents/DESIGN.md` | design contract {{if UI}} |
| `HANDOFF.md` | living state (gitignored) |

## 9. HANDOFF.md template

```markdown
# HANDOFF — {{PROJECT_NAME}} working state
Updated: <date> by <who>

## Verified state (with evidence commands)
- <claim> — proven by `<command>` → <one-line output>

## Built but UNEXERCISED
- <thing> — why it hasn't run yet

## Current task & next step
- Now: … / Next: …

## Open human decisions (do not decide these yourself)
- …

## New traps discovered this session
- … (→ promote durable ones to AGENTS.md §6)
```
