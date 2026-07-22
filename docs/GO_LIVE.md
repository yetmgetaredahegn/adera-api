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

## ② Invite the team — **Write** permission only (not Admin/Maintain)
Per repo: Settings → Collaborators → Add people. Give each teammate **Write**.
- **Write** = push branches, open PRs. **Cannot** change settings or bypass branch
  protection or merge a blocked PR. Exactly what you want.
- Admin/Maintain would let them change protections — don't.
- Access map: backend + security → `adera-api`; web dev → `adera-web`; mobile dev →
  `adera-mobile`. (Give security read on all three if you want cross-repo review.)

## ③ Protect `main` on each repo
Settings → Branches → Add branch protection rule → branch name `main`:
- ☑ **Require a pull request before merging** → Require approvals: **1**
- ☑ **Require review from Code Owners** ← this is what makes *you* the only approver
  (CODEOWNERS = `* @yetmgetaredahegn`)
- ☑ **Do not allow force pushes** · ☑ Do not allow deletions
- ☑ Require conversation resolution before merging (optional, tidy)

**Ordering trap — required status checks:** the "Require status checks to pass" box
only lists checks that have **already run once** on the repo. On the fresh
web/mobile repos there are none yet. So: enable the PR + Code-Owner rules now; after
the first PR triggers CI, come back and tick the CI check as required. (`adera-api`
already has CI runs, so you can require its `check` job immediately.)

**Admin bypass:** by default you (admin) can still merge past protection. Keeping
that for yourself early is a legitimate velocity choice — you're the reviewer
anyway. Teammates can never bypass regardless. If you later want *no one*
(including you) to bypass, tick "Do not allow bypassing the above settings."

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
