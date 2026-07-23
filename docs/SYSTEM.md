# SYSTEM — how the three repos become one product

*The integration map. Read this to understand how `adera-api`, `adera-web`, and
`adera-mobile` connect, how to run them together, and the path from three scaffolds
to a shipped product. Canonical here in the hub; client repos carry a short pointer.*

## 1. The whole product, one picture

```
   ┌──────────────────┐        ┌──────────────────┐
   │  adera-mobile    │        │   adera-web      │
   │  Flutter (Dart)  │        │  Next.js (TS)    │
   └────────┬─────────┘        └────────┬─────────┘
            │      HTTPS  (JSON REST)    │
            └─────────────┬──────────────┘
                          ▼
              ┌───────────────────────────┐
              │        adera-api          │   api  (FastAPI, user-facing)
              │   FastAPI + Celery        │   worker (pipeline: io/cpu queues)
              │                           │   beat (scheduler)
              └───────────┬───────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  Postgres 16        Redis (queue      Cloudflare R2
  + pgvector          + cache)          (raw pages, docs,
  (tenders,                              law corpus, proofs)
   embeddings)
```

Behind the API runs the daily **pipeline**: `fetch → parse → extract → upsert →
qualify → embed → match → notify`. Clients never see the pipeline; they see its
output through the API.

## 2. The one coupling point: the contract

The three repos share **zero code** (Python / Dart / TypeScript). The *only* thing
that crosses repo boundaries is the **API contract**:

```
adera-api  ──(make openapi)──▶  contracts/openapi.json  ──(copied into)──▶  adera-web/contracts/
                                        │                                    adera-mobile/contracts/
                                        ▼
                          each client GENERATES its own typed client
                          (TS via openapi-typescript · Dart via openapi_generator)
```

This is why a client dev never needs access to the backend code — they need the
contract, which lives in their own repo. It's also why **CI blocks a backend PR
that changes the API without regenerating the contract** (`git diff --exit-code
contracts/`): the contract can never silently drift from the code.

## 3. One field, end to end (the feed feature traced across all 3 repos)

1. **Ingest** — the World Bank adapter (`adera-api`) writes a tender row; the
   `title` column is populated.
2. **Serve** — `GET /api/v1/tenders` returns `TenderOut` (a Pydantic model in
   `app/modules/ingestion/schemas.py`) with `title` as an explicit field.
3. **Publish** — `make openapi` writes `title: string` into
   `contracts/openapi.json`.
4. **Generate** — the client repo generates a `TenderOut` model (Dart/TS) with a
   `title` field from that contract.
5. **Render** — the client draws the tender card's serif title from
   `tender.title`. No hand-written model anywhere in the chain.

Change `title` on the backend → regenerate the contract → clients regenerate → the
type flows through. That's the whole integration model.

## 4. Run all three together, locally

```bash
# 1. Backend (this repo)
make up && make migrate                                    # Postgres+Redis, schema applied
uv run python -m app.cli seed                              # register the World Bank source
uv run python -m app.cli ingest worldbank                  # fetch + upsert → real tenders
make api                                                    # :8000, /docs is the live API console

# 2. Find your machine's LAN IP (clients can't reach the backend via "localhost")
ip addr | grep 'inet 192'                 # e.g. 192.168.1.20

# 3. Web (adera-web): point NEXT_PUBLIC_API_BASE at http://<lan-ip>:8000, then pnpm dev
# 4. Mobile (adera-mobile): set the API base to http://<lan-ip>:8000, generate the
#    client from contracts/openapi.json, run on emulator/device.
```

**The #1 gotcha:** a phone/emulator's `localhost` is *itself*, not your laptop.
Always use the laptop's LAN IP (or a tunnel like `cloudflared`/`ngrok` for a remote
teammate). The public read endpoints need no auth, so a client can hit them
immediately.

## 5. Working across repos (the change protocol)

- **The API leads the contract.** Any change to a request/response shape happens in
  `adera-api` first: edit the schema → `make openapi` → commit the regenerated
  `contracts/openapi.json` → CI verifies it matches.
- **Clients follow.** When the contract changes, the client repos pull the updated
  `contracts/openapi.json`, regenerate their client, and adapt. The founder
  coordinates the sequence (backend PR merges first).
- **Breaking changes are never silent.** Backward-compatible additions live under
  `/api/v1`. A breaking change means `/api/v2` — old clients keep working until they
  migrate.
- **Who owns what:** backend dev owns endpoints + the contract; client devs own
  their generated client + UI; the founder owns the merge and the sequencing.

## 6. Deployment — three targets, never one release

| App | Runs on | Ships via |
|---|---|---|
| `adera-api` | one VPS, Docker Compose (ADR-012) | GitHub Actions → GHCR image → SSH deploy (doc 09) |
| `adera-web` | a web host (Vercel / Node server) | host's git integration or Actions |
| `adera-mobile` | app stores (.apk / .ipa) | Flutter build → store review |

They never share a release artifact or cadence — that independence is exactly why
this is three repos (see `docs/ADRs/025-repo-strategy-polyrepo.md`). CI/CD posture:
`docs/ADRs/026-cicd-delivery-posture.md`.

## 7. From three scaffolds → one shipped product (the integration milestones)

Track live status in each repo's `PROGRESS.md`; this is the cross-repo sequence:

1. ✅ **Backend serves a public contract** — `GET /api/v1/tenders` live, contract published.
2. 🚧 **Each client generates its client + renders the live feed** — no auth needed; real tenders on screen. *(This is the first integration proof — do this early.)*
3. ⏳ **Auth lands** (backend) → per-user profiles + saved matches → clients wire login.
4. ⏳ **Explanations + eligibility** (backend, needs LLM key) → clients render "why this fits you" + real chips.
5. ⏳ **Notifications** (TZ-aware digests) and each app **deployed** to its target.

The moment step 2 works — a real Ethiopian tender fetched by the backend showing up
as a card in the Flutter app — the product is *connected*. Everything after is
adding surfaces to a proven spine.
