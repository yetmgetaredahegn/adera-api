# Contributing to adera-api

Welcome. This repo is the ADERA backend (FastAPI + pipeline) and the hub for
product-wide docs. Read `docs/team/ONBOARDING.md` first if you haven't.

## The work loop (every task, same shape in every ADERA repo)

1. **Research** — read your domain: `docs/05_BACKEND_GUIDE.md` (Django→FastAPI map
   in §3), `docs/agents/SKILLS.md` (recipes), `docs/PROGRESS.md` (what's built vs
   next), the relevant FRs in `docs/00_MASTER_PLAN.md`.
2. **Propose** — for anything non-trivial, open a **proposal PR** first
   (`docs/proposals/`, use `TEMPLATE.md`). Cheap to change a plan, expensive to
   change built code. The tech lead reviews the plan before you build.
3. **Implement** — branch `feat/<area>-<short>` (or `fix/…`, `docs/…`). Follow the
   recipe in SKILLS.md if one exists. Keep the diff small and scoped to one
   problem.
4. **Verify + PR** — `make check` green (format, lint, mypy, tests) **and** a
   behavior proof (run the thing; paste output) — see `.claude/skills/verify`.
   Open a PR with the template; **update `docs/PROGRESS.md` in the same PR**.
5. **Tech lead reviews & merges** — you never merge your own PR. Only the tech
   lead (Code Owner) approves and merges to `main`.

## Rules that will fail your PR if broken
- `make check` must be green. CI runs it too; a red PR won't be reviewed.
- **Conventional commits** (`feat(scope): …`, `fix(scope): …`, `docs: …`).
- **No AI co-author trailers** — enforced by a commit-msg hook
  (`make install-hooks`, run once). Describe an AI's help in the body, commit as
  yourself.
- **PROGRESS.md updated** in the same PR as the change it describes.
- Tech-lead-review-mandatory areas (auth, billing, migrations that alter existing
  tables, prompt versions, kernel budgets, KYB) — flag these loudly in the PR.

## First task (before any code)
`docs/proposals/FIRST_TASK.md` — research your domain and open a proposal PR with
insights. It's how you get productive *and* safely test the branch→PR→review flow.

## Ideas & corrections welcome
Found something wrong or have a better idea? That's contribution, not noise. Open a
GitHub Issue (use a template) or a proposal PR. Strong architectural proposals get
promoted to a real ADR (`docs/ADRs/`).

## Setup
```bash
make install     # uv sync + .env + git hooks
make up          # Postgres + Redis
make migrate
make check       # the gate
make demo        # see matching on real data
```
Ports are 5435/6380 on purpose (AGENTS.md §5).
