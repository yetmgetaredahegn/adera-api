# MANAGING — running the team across three repos (founder's console)

Right-sized for a 5-person hackathon team with one reviewer. The tools are already
in place; this is how to use them without heavyweight PM overhead.

## Your three instruments
1. **Per-repo `PROGRESS.md`** — the status board for each domain. Glance to see what's
   done / in progress / next, per repo. Teammates update it in each PR.
2. **PRs (with template + CODEOWNERS)** — every change arrives in one shape,
   auto-requests you, and can't merge without you. Your review queue is
   github.com/pulls (shows PRs across all your repos assigned to you).
3. **A cross-repo Project board** (optional but recommended) — one view of every
   task/PR across all three repos.

## Set up the board (once)
github.com/yetmgetaredahegn → Projects → New project → **Board**. Add all three
repos as sources. Columns: **Inbox / proposals** → **Approved (todo)** →
**In progress** → **In review (PR open)** → **Done**. Enable the built-in workflows
so new issues land in Inbox and merged PRs move to Done.

## The weekly rhythm (light)
- **Triage proposals** — teammates' `FIRST_TASK` / proposal PRs land first. Review
  them: merge the plan (a decision of record) or promote a strong architectural one
  to an ADR (`docs/ADRs/`). This is where you steer direction before code exists.
- **Assign from PROGRESS** — the "next" items in each repo's `PROGRESS.md` become
  Issues (use the task template) → drop on the board → assign.
- **Review PRs** — your queue is github.com/pulls. The PR template's checklist +
  green CI mean most of your review is judgment, not mechanics. Approve → merge (or
  request changes). You're the only one who can.
- **Read the boards** — three `PROGRESS.md` files + the project board tell you where
  everything stands in 2 minutes.

## What keeps this sustainable
- **CI rejects broken work before you see it** — you never spend review on a PR that
  fails lint/type/test.
- **The contract gate** protects cross-repo integrity automatically.
- **Proposals-first** means you approve *direction* cheaply (a doc PR) before anyone
  spends days on code.

Don't add Jira/Linear/etc. yet — three PROGRESS files + a GitHub board + the PR
queue is enough for five people. Revisit only if coordination genuinely outgrows it.
