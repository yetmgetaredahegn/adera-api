# ADR-026 — CI/CD and delivery posture: guarded GitHub Actions, no Kubernetes

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-07-22 |
| **Decision** | GitHub Actions per repo, **guarded** to no-op cleanly on the two client repos until their frameworks are initialized; Docker Compose on one VPS remains the deploy substrate (ADR-012 unchanged); **Kubernetes rejected, explicitly, on the record.** |

## Context

The team just grew to 5 people across 3 repos with one founder-reviewer. The
question: what CI/CD and delivery tooling actually helps a solo reviewer manage
that, without adopting infrastructure sized for a team or scale this product
doesn't have.

## Decision

**CI's job here is narrow and specific: reject broken work before it reaches the
founder's review.** That is what makes solo review of 3 repos sustainable — not
more pipeline, more tooling, or more infrastructure.

1. **`adera-api`** already has CI (lint → mypy → migrations-from-scratch → tests →
   contract-drift). A `deploy.yml` scaffold is added (build → GHCR → SSH to the VPS,
   per doc 09) but **guarded/inert** until a server and secrets exist — committed
   so the path is documented, not run before it's real.
2. **`adera-web` / `adera-mobile`**: CI is **guarded** — it detects whether the
   framework project exists (`package.json` / `pubspec.yaml`) and no-ops cleanly
   if not, running the real checks (lint/typecheck/build, analyze/test) once it
   does. This solves a real GitHub ordering problem: branch protection can only
   require a status check that has run at least once, so an empty scaffold repo
   needs a check that passes trivially now and does real work later — not a
   missing check the founder can't yet require.
3. **Dependabot** per repo (weekly) for dependencies and Actions versions — closes
   a gap the security brief flagged, at zero ongoing cost.

## Kubernetes — rejected, explicitly

Not implicitly skipped; rejected on the record, so it is not re-proposed by a
future contributor or re-litigated from scratch:

- **ADR-012 already made this call** for the backend (Docker Compose, one VPS,
  Kubernetes rejected at this scale). This ADR extends the same reasoning across
  the now-multi-repo product: nothing about adding a web and mobile client changes
  the backend's deployment shape — they deploy to a web host and app stores
  respectively, not to any orchestrator.
- **The actual justification, stated once:** k8s solves problems of scale
  (many replicas, complex service mesh, multi-node scheduling) and problems of
  *team* (many engineers needing self-service deploys). This product is
  pre-revenue with one VPS worth of load and one person doing every deploy
  approval. Adopting an orchestrator here would be solving a problem the team
  doesn't have, at the cost of an operational tax the team can't yet absorb —
  the same trend-driven-overhead mistake already corrected once this session
  (rejecting `apps/`+`packages/` monorepo tooling for the same underlying reason:
  match tooling to actual scale, not to what looks professional).
- **Reversal condition (so this isn't dogma):** revisit if the product outgrows
  one VPS's capacity, or a second backend service needs independent scaling from
  the api/worker/beat trio — neither is close. Track via ADR-012's own thresholds.

## Consequences

**Gained:** CI that works today on empty scaffolds and grows into real checks
without edits; a deploy path that's documented before it's dangerous to run;
dependency hygiene without a dashboard tool.
**Accepted:** the deploy workflow is unexercised until a VPS + secrets exist —
recorded honestly rather than hidden; CI is not yet enforced by branch protection
on web/mobile until `docs/GO_LIVE.md`'s ordering step is followed (protect now,
require the check after its first run).

## Rejected alternatives

- **Kubernetes** — see above.
- **A CI/CD SaaS (CircleCI, Travis, etc.)** — GitHub Actions is already free at
  this usage and needs no new account/secret surface.
- **Monorepo build tooling (Nx/Turborepo) for cross-repo CI orchestration** — moot;
  ADR-025 already rejected the monorepo layout these tools assume.
