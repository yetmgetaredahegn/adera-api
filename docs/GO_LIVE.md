# GO-LIVE — the founder's one-time setup runbook

Do this once, in order, to open the three repos to the team with the governance
that keeps `main` safe. Everything here is **founder actions on GitHub** — an AI
agent can't toggle these settings; this is the handoff.

## ① Create the two missing repos + push
`adera-api` is already on GitHub. For `adera-mobile` and `adera-web`:
1. github.com/new → name `adera-mobile` (then `adera-web`) → **create empty**
   (no README/.gitignore/license — the local repos already have commits).
2. Push (remotes are already configured):
   ```bash
   cd ~/projects/Adera/adera-mobile && git push -u origin main
   cd ~/projects/Adera/adera-web    && git push -u origin main
   ```

## ② Invite the team — Collaborators
Per repo: Settings → Collaborators → Add people.
- These are **personal repos, not a GitHub Organization** — there is no
  Read/Triage/Write/Maintain/Admin tier picker here (that's an org-only feature).
  Adding someone as a collaborator is the only option; they get repo access, can
  push branches and open PRs, but cannot touch repo Settings — CODEOWNERS + the
  Ruleset (below) are what actually stop them from merging past you, not the
  invite step itself.
- Access map: backend + security → `adera-api`; web dev → `adera-web`; mobile dev →
  `adera-mobile`. (Add security as a collaborator on all three if you want
  cross-repo review.)

## ③ Protect `main` on each repo — Rulesets
Settings → Rules → Rulesets → New branch ruleset → target `main` (or `default`):
- **Restrict deletions**, **Block force pushes**
- **Require a pull request before merging** → Required approvals: **1**
- **Require review from Code Owners** ← this is what makes *you* the only approver
  (CODEOWNERS = `* @yetmgetaredahegn`)
- **Require status checks to pass** — see the ordering trap below
- **Bypass list:** Repository admin role only (that's you) — leave it at just
  that; no other bypass entries.

**Ordering trap — required status checks:** a check can only be added to the
Ruleset **after it has run at least once** on the repo. On the fresh web/mobile
repos there are none yet. So: turn on the Ruleset now with everything above
*except* the status-check requirement; after the first PR triggers CI, come back
and add the `check` job as required. (`adera-api` already has CI runs, so you can
require its `check` job immediately.)

**Admin bypass:** the bypass list above is scoped to the Repository admin role,
which is only you. Teammates are never on it and can never merge past the
Ruleset regardless of what else changes. That's the actual enforcement
mechanism — verified live: a push to `adera-api`'s protected `main` logs GitHub's
own bypass-eligibility check and still requires the PR path for everyone else.

## ④ Cross-repo oversight (see docs/MANAGING.md)
Create one GitHub **Project** (board) spanning all three repos so every task/PR is
in one view. Details + review rhythm: `docs/MANAGING.md`.

## ⑤ Kick off the team
- Send each person the ZIP (`adera-team-pack.zip`) or point them at their repo.
- Their first task is `docs/proposals/FIRST_TASK.md` in their repo — **research +
  a proposal PR, no code.** That first PR also verifies your branch protection works
  (they can't merge it — only you can).

## Result
Teammates push `feat/…` branches and open PRs; CI runs; you review a consistent PR
(template + CODEOWNERS auto-requests you); **nothing reaches `main` without your
approval.** One reviewer, three repos, fully in control.
