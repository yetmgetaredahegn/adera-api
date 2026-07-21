# CLAUDE.md — ADERA

@AGENTS.md

The file above is the full working contract (rules, environment, traps, the loop).
Claude-specific additions only, below.

## Standing founder instructions (this repo)
- **Never `git commit` or `git push` unless the founder explicitly asks in the current
  conversation.** Leave work staged and report it. (Founder instruction, 2026-07-16.)
- **Never add a `Co-Authored-By` trailer for Claude (or any AI agent) to a commit.**
  Commit as the founder; the "why" belongs in the commit body, not the author
  field. (Founder instruction, 2026-07-21 — see AGENTS.md rule 16.)
- Founder-review-mandatory (propose, never merge silently): auth, billing,
  payments/ledger/payouts, kernel permissions & budgets, migrations altering existing
  tables, prompt versions, KYB/vetting logic (master plan Appendix E).
- Architecture changes = ADR proposal in `docs/ADRs/` — propose, don't implement
  (master plan §12.3). Never edit `docs/00_MASTER_PLAN.md` §12 in place.
- The founder comes from Django: when explaining backend concepts, map them to their
  Django equivalents (see the table style in past sessions).

## Claude Code specifics
- Project verify skill: `.claude/skills/verify/SKILL.md` — run it before claiming any
  task done (it is the §7.5 "behavior proof" step, scripted).
- Before any UI work, load `docs/agents/DESIGN.md`; before any recurring task type,
  check `docs/agents/SKILLS.md` for its recipe.
- Session end: update `HANDOFF.md` (root, gitignored) — the next session starts there.
