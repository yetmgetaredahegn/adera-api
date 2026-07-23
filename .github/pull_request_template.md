## What & why
<!-- One or two sentences. Link the proposal/issue this implements. -->
Closes #

## How to verify
<!-- The exact commands/steps a reviewer runs to see it work. -->

## Checklist
- [ ] Quality gate green (see below) and proof pasted/linked
- [ ] `docs/PROGRESS.md` updated in this PR
- [ ] Conventional commit messages; **no AI `Co-Authored-By` trailer**
- [ ] If the API contract changed: regenerated & committed (`contracts/`)
- [ ] Docs updated if behavior/notes changed
- [ ] I did **not** merge my own PR (tech lead approves & merges)

<!-- Quality gate: api → `make check` · web → `pnpm lint && pnpm build` · mobile → `flutter analyze && flutter test` -->
