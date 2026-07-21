# 09 — DevOps & Deployment Guide
*Git discipline, CI/CD, containers, the deploy strategy decision, backups, monitoring — sized for one VPS and one human.*

## 1. Git workflow (GitHub Flow, PR-based — even solo)
`main` is protected and always deployable. Every change: branch → PR → CI green → **squash-merge** → auto-deploy. Branch names: `feat/m7-matching-threshold`, `fix/ingestion-egp-pagination`, `chore/deps-bump`. Commits: Conventional Commits (`feat(matching): add eligibility pre-filter (FR-7.6)`) — the FR/ADR reference in parentheses is the traceability habit that makes the repo self-documenting. Why PRs alone with no reviewer? The PR is where CI, eval-smoke, and your own diff-read happen; future contributors inherit a repo with history that explains itself. Tag releases `v0.4.0` at each phase exit.

## 2. Dockerfile (one image, three roles)
```dockerfile
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-amh tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev            # cached layer: deps only rebuild when lock changes
COPY app/ app/  prompts/ prompts/  alembic/ alembic/  alembic.ini .
RUN useradd -m runner && chown -R runner /app
USER runner
# role picked at runtime: api | worker | beat  (compose sets command)
CMD ["uv","run","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
```
Playwright browsers add ~400 MB — install them in a second stage used **only** by the worker service (`uv run playwright install --with-deps chromium`), keeping the api image lean. The frontend gets its own small Node build image (Next standalone output).

## 3. Compose (prod shape) & the deploy strategy decision
Services: `caddy` (TLS, reverse proxy) · `web` (Next) · `api` · `worker` (2 replicas: queues io,cpu) · `beat` · `db` (Postgres 16 + pgvector, volume) · `redis` · `uptime-kuma`. Healthchecks on api (`/healthz`) and web; `restart: unless-stopped` everywhere.
**Strategy decision, stated:** **health-checked rolling restart via Compose** — `docker compose pull && docker compose up -d` replaces containers one service at a time; Caddy retries during the seconds of overlap; with `start_period` set, a container that fails health never receives traffic. Seconds-level blips at worst — correct for this stage. **Blue-green** (run new stack beside old, flip the proxy atomically, instant rollback) — know it, don't build it: it doubles resources and adds proxy orchestration to solve a zero-downtime requirement ADERA doesn't have pre-revenue-scale; adopt when deploys during peak digest hours become risky. **Kubernetes: not required** (ADR-012) — it purchases multi-node orchestration with etcd/RBAC/YAML overhead; revisit triggers: >1 node needed, >3 engineers, or a managed-K8s offer at cost parity. Write the trigger check into the quarterly review, then stop thinking about it.

## 4. GitHub Actions — the two workflows
`ci.yml` (every PR): checkout → uv sync → `ruff check` + `mypy` → unit+integration tests (Postgres/Redis via service containers) → `make eval-smoke` → build both images (no push). 
`deploy.yml` (push to main): build+push `ghcr.io/<you>/adera-{api,web}:sha` → SSH step:
```yaml
- uses: appleboy/ssh-action@v1
  with: { host: ${{secrets.VPS_HOST}}, username: deploy, key: ${{secrets.SSH_KEY}},
    script: |
      cd /srv/adera && docker compose pull
      docker compose run --rm api uv run alembic upgrade head   # migrate BEFORE new code serves
      docker compose up -d && docker compose ps }
```
Secrets live in GitHub Environments (`VPS_HOST`, `SSH_KEY`, plus app env synced via SOPS-encrypted file in the repo, decrypted on the server). Rollback = `git revert` the merge (redeploys prior sha) — practice it once on staging so it's boring. Migration discipline: only **additive** migrations deploy automatically (add column/table/index); destructive ones (drop/rename) are two-step (deploy code that stops using it → next release drops it) — this is what makes rolling restarts safe.

## 5. VPS setup runbook (once, ~1 hour)
Hetzner Ubuntu 24.04 → create `deploy` user, SSH keys only, disable root+password login → `ufw allow 80,443,22` → install Docker → `mkdir /srv/adera` (compose file + .env) → DNS A records → Caddy issues TLS automatically on first boot → install fail2ban → done. Staging = same box, second compose project (`adera-staging`, own DB, subdomain) until revenue funds a second box.

## 6. Backups & restore (NFR-DR-1 — the part everyone skips until the day)
Nightly cron on the VPS: `pg_dump -Fc adera | age -r <pubkey> | rclone rcat r2:adera-backups/$(date +%F).dump.age` (compressed, encrypted, offsite) + 30-day lifecycle rule on the bucket. **Quarterly restore drill:** pull latest dump → restore into the staging DB → run the smoke e2e → log "restored in N minutes" in `docs/runbooks/dr-log.md`. RTO ≤ 4h means: fresh VPS + this runbook + last night's dump gets you live — rehearse exactly that once.

## 7. Monitoring & incident basics
Sentry (free tier) on api+web — release-tagged so a bad deploy is obvious in one glance. Uptime Kuma self-hosted probing `/healthz` + the public landing page, alerting to your Telegram. Structured JSON logs with request/run IDs (`docker compose logs api | jq 'select(.level=="error")'` is your grep). The run-ledger dashboard (FR-11.1) is pipeline monitoring — product and observability in one table. Incident habit: SEV1 (pipeline down >12h / data issue) → stop feature work, fix, then write five lines in `docs/runbooks/postmortems.md` (what broke, why, the guard added). One guard per incident is how solo systems harden.

## Further reading & credible sources
- **GitHub Flow** — docs.github.com/en/get-started/using-github/github-flow — the branching model §1 adopts, from the source.
- **Conventional Commits** — conventionalcommits.org — the commit grammar incl. scopes; pairs with the FR-reference habit.
- **GitHub Actions docs** — docs.github.com/actions — service containers for tests, environments/secrets, and SSH-deploy patterns behind §4.
- **Docker docs** — docs.docker.com — multi-stage builds, Compose healthchecks, and `start_period` semantics used in §2–3.
- **Caddy docs** — caddyserver.com/docs — automatic TLS + reverse-proxy config; the reason there is no certbot in this stack.
- **Hetzner community tutorials** — community.hetzner.com/tutorials — server-hardening and Docker-on-Ubuntu walkthroughs matching §5's runbook.
- **PostgreSQL backup docs** — postgresql.org/docs/current/backup-dump.html — `pg_dump -Fc` and restore mechanics for §6; pair with rclone.org (R2 sync) and age (github.com/FiloSottile/age) for encryption.
- **Grafana k6** — grafana.com/docs/k6 — CI-mode thresholds when load tests join the pipeline.
- **Sentry docs** — docs.sentry.io — release tagging so bad deploys surface instantly (§7).
- **Uptime Kuma** — github.com/louislam/uptime-kuma — self-hosted probe setup + Telegram alerting.
- **Google SRE workbook (free)** — sre.google/workbook — read only the incident-response and postmortem chapters; §7's one-guard-per-incident habit comes from there.
