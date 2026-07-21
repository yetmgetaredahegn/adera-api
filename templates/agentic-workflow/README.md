# Agentic Workflow Template — context engineering for any project

Copy this folder into a new repo, fill the placeholders, delete what you don't need.
It sets up the same system ADERA uses: enough truth, guardrails, and recipes *inside
the repo* that any model — including small/cheap ones — can work without hallucinating.

## The model of why this works

An agent hallucinates when the truth it needs is (a) not in context, (b) buried in
too much context, or (c) contradicted by stale context. The whole system attacks
those three failure modes:

```
Layer 1  STABLE CONTRACT   AGENTS.md            committed, changes rarely
Layer 2  VOLATILE STATE    HANDOFF.md           gitignored, updated every session
Layer 3  DEEP DIVES        SKILLS.md, DESIGN.md,
                           your existing docs    loaded on demand, per task
```

- Layer 1 is small (≤ ~300 lines) and **always** loaded. It carries rules and traps.
- Layer 2 carries *what is true right now* — so a fresh session never re-derives or
  guesses project state, and never trusts stale claims (it re-verifies).
- Layer 3 is loaded **by task type** via a Context Loading table — this is the piece
  most setups miss: telling the model what NOT to read matters as much as what to read.

## The nine principles (bake these into every file you write)

1. **Entry point ≤ 300 lines.** If AGENTS.md grows past that, push detail into Layer 3
   and leave a link + one-line "when to read".
2. **Rules as MUST/NEVER + a one-line WHY + a citable id.** Models (and humans) follow
   rules far better when the reason travels with the rule, and ids (FR-x, ADR-n)
   let intent survive into code comments and reports.
3. **Recipes, not vibes.** Every recurring task gets a recipe in SKILLS.md: exact
   commands, file skeletons, a Verify step, a Definition of Done. Small models execute
   recipes reliably; they improvise poorly. Rule for them: *no recipe → plan and stop.*
4. **Verification is two-level and evidence-based.** Level 1: the static gate
   (`make check` equivalent). Level 2: behavior proof — run the actual thing and paste
   output. Norm: **a claim without command output is not a claim.** This single norm
   kills most hallucinated "done"s.
5. **State handoff.** End every session by updating HANDOFF.md: verified state (with
   evidence commands), *built-but-unexercised* list (the honesty section), next step,
   open human-only decisions. Start every session by reading it — and re-verifying.
6. **Traps ledger.** Every bug that cost >15 minutes becomes a named trap in
   AGENTS.md with its fix. Past pain is the cheapest hallucination-killer.
7. **Honesty protocol.** Three statuses, always distinguished: *built-and-proven* /
   *built-but-unexercised* / *assumed*. Unknown → say unknown + how to find out.
   Never simulate output the environment can't produce (e.g. no API key → say so).
8. **Escalation list.** Name the decisions only the human may make (money, auth,
   architecture, anything touching the source-of-truth plan). The agent proposes
   (ADR files, plans); the human merges.
9. **Model-strength ladder.** Big models may design + add recipes; small models
   execute recipes only. Write this into AGENTS.md so the model self-limits.

## Files in this template

| File | Becomes | Notes |
|---|---|---|
| `AGENTS.template.md` | `/AGENTS.md` | the universal contract (works with Claude Code, Cursor, Codex, Copilot — they all read AGENTS.md or can be pointed at it) |
| `HANDOFF.template.md` | `/HANDOFF.md` | **add to .gitignore**; volatile state |
| `SKILLS.template.md` | `/docs/agents/SKILLS.md` | start with 2–3 recipes max; grow as tasks recur |
| `DESIGN.template.md` | `/docs/agents/DESIGN.md` | only if the project has UI; tokens are truth |

Plus two one-liners you write directly:

- `/CLAUDE.md` → first line `@AGENTS.md`, then only Claude-specific standing
  instructions (commit policy, review-mandatory list).
- `.gitignore` → add `HANDOFF.md`.

## Instantiation checklist (15 minutes)

1. Copy templates to the paths above; fill every `{{PLACEHOLDER}}`.
2. Write the 5–10 hard rules that are *actually load-bearing* for this project —
   not generic advice. Good test: each rule should reference a real constraint
   (a regulation, an invariant, a past bug). Delete any rule you can't justify.
3. Fill the Context Loading table: task type → files to read → files to NOT read.
4. Write ONE recipe for the project's most common task, with a real verify command.
5. Create HANDOFF.md with today's true state. Gitignore it.
6. Add the "session start ritual" habit: read HANDOFF → verify claims → restate task.
7. As you work: every new bug → traps ledger; every 3rd repetition of a task → recipe.

## Anti-patterns (things that feel helpful but aren't)

- **One giant CONTEXT.md** — everything loaded always = key rules drowned. Layer it.
- **Aspirational docs** — describing the system you *want* as if it exists. The
  honesty sections exist precisely to prevent this; agents build on false floors.
- **Rules without whys** — get pattern-matched away under pressure.
- **Stale HANDOFF** — worse than none. That's why readers re-verify and writers
  date-stamp it.
- **Recipes that skip Verify** — a recipe ending at "write the code" teaches the
  model that done = written. Done = proven.
