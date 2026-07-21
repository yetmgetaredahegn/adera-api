# ADR-025 — Repository strategy: polyrepo, contract-first

| | |
|---|---|
| **Status** | Proposed — supersedes the in-repo `web/` layout implied by 05 §2 / master plan §12.2 system sketch (plan §12 untouched per §12.3 propose-don't-implement) |
| **Date** | 2026-07-19 |
| **Decision** | Three repositories — **`adera-api`** (this repo: FastAPI backend + pipeline + canonical docs) · **`adera-mobile`** (Flutter) · **`adera-web`** (Next.js) — coordinated **contract-first** through a versioned, CI-verified `contracts/openapi.json`. |
| **What changes** | Nothing physically moves: this repo is already backend-only and simply *is* `adera-api`. `web/` will never appear here; client repos are scaffolded as siblings. |

## Context

The team grows from solo to multi-person (Flutter mobile dev first; web and
security after), with a native mobile client added to the product scope. The
question — one repo or several — was decided by factor analysis, not preference;
the founder's independent research converged on the same answer (corroboration,
not basis).

## Decision matrix (the analysis)

| Factor | Fact of this project | Points to |
|---|---|---|
| Code sharing across apps | **Zero.** Python / TypeScript / Dart share no code — Flutter forecloses a shared TS client, the one artifact that could have crossed app boundaries. Only the API *contract* crosses | **Poly** — monorepo's core benefit is void here |
| Release lifecycles | Server = continuous deploy · web = host deploy · mobile = app-store review cycles; never one release artifact | **Poly** — independent trains |
| Toolchains | uv · pnpm · pub — three native ecosystems; no build tool spans Python+Dart (Nx/Turborepo are JS-native) | **Poly** — no root-tool contortions |
| CI economics | A Flutter UI change must not trigger backend suites/Docker builds, and vice-versa | **Poly** — scoped pipelines by default |
| Access control | Git permissions are repo-level; externals/contractors may join later; the backend embodies the moat logic | **Poly** — least-privilege by default |
| **Atomic API+client changes** | the genuine monorepo advantage | **Mono** — the one real cost of poly |
| Team workflow familiarity | conventional clone-branch-PR; no monorepo-tooling experience | Poly (secondary; listed for completeness) |

**Resolving the one Mono point:** atomicity matters where clients share *typed
code* with the server. Here they cannot (three languages) — clients regenerate
from the OpenAPI spec in either layout. Contract-first publishing recovers ~all of
the benefit at ~none of the cost:

1. `make openapi` regenerates `contracts/openapi.json` (committed, sorted keys).
2. CI regenerates and `git diff --exit-code contracts/` — the committed contract
   can never drift from code.
3. Clients generate their language's client from the contract (Dart:
   `openapi_generator`-class tools; TS: `openapi-typescript`) — hand-written API
   models are banned in client repos.
4. Backward-compatible evolution within `/api/v1`; breaking changes = `/api/v2`,
   never silent (ADR-004's REST+OpenAPI discipline).

## Consequences

**Gained:** per-repo access for future externals · native toolchains and scoped CI
per stack · independent release cadence · the conventional workflow every incoming
dev already knows.
**Accepted:** contract changes propagate by regeneration, not atomically — the CI
drift-gate plus versioning discipline is the mitigation · canonical product docs
live in `adera-api`; client repos carry self-sufficient onboarding kits (DESIGN.md
mirror, PRODUCT.md, contract copy) so client-only contributors never need api
access — mirrors are labeled non-canonical to prevent edit drift.

## Reversal conditions (so this never becomes dogma)

Revisit via a new ADR if any of these become true:
1. A genuinely shared package emerges (e.g. mobile moves to React Native → a
   shared TS client becomes possible and valuable).
2. The team consolidates onto one language stack.
3. Cross-repo coordination overhead measurably exceeds the cost of monorepo
   tooling (tracked in practice, not predicted).

## Rejected alternatives

- **Monorepo with `apps/` + `packages/`** — the Turbo/Nx convention without Turbo/Nx
  is shape without machinery; no tool spans Python+Dart, and the shared package that
  justifies the layout cannot exist with Flutter.
- **Monorepo with `backend/` + `frontend/`** — viable while web was the only client;
  the mobile decision (Dart) plus incoming per-repo access needs voided its remaining
  advantages.
