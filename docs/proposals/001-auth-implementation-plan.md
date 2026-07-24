# Proposal: Auth implementation plan (sessions + CSRF, web; JWT, bot)

**Author:** Claude (session 2026-07-23) · **Date:** 2026-07-23 · **Status:** Proposed

> Written per AGENTS.md rule 14 — auth is tech-lead-review-mandatory. This is a
> proposal for review, not implemented code. Nothing here is merged or built
> until the tech lead approves it.

## Problem / opportunity

Auth is the single hardest blocker in `docs/PROGRESS.md`'s build queue — it
gates per-org matches, saved/dismissed state, and everything in
`docs/11_API_REFERENCE.md` marked auth level `user`/`org`/`fac`/`admin` (AUTH-1
through AUTH-6 alone). The `identity` module has schema (`User`, `Org`,
`OrgMember`) and nothing else — no `app/core/security.py`, no `current_user`/
`current_org` dependencies, no session table, no tests. The architecture is
already decided (`docs/05_BACKEND_GUIDE.md` §3, referencing master plan §12):
**web = httpOnly signed session cookie + CSRF token on unsafe methods; Telegram
bot = short-lived JWT service account.** This proposal is the concrete
implementation plan for that decision, not a new architecture choice.

## Proposal

1. **`app/core/security.py`** (new) — owns all crypto, per the guide's existing
   note that nothing else should touch it:
   - `hash_password` / `verify_password` — argon2 (`argon2-cffi`, not yet in
     `pyproject.toml` — new dependency).
   - `create_session` / `verify_session` — signed, httpOnly, `Secure`,
     `SameSite=Lax` cookie. Signed with `itsdangerous` or a stdlib HMAC — either
     is fine; `itsdangerous` is the smaller diff.
   - `issue_csrf_token` / `verify_csrf_token` — double-submit pattern (cookie +
     header), checked on POST/PUT/PATCH/DELETE only.
   - `create_bot_jwt` / `verify_bot_jwt` — short-lived, `python-jose` or
     `pyjwt` (new dependency; pick one, not both).
2. **A `sessions` table** (new model in `identity/models.py`, new migration) —
   session id, user id, issued/expires timestamps, revoked flag. Needed for
   server-side logout/revocation; a purely stateless signed cookie can't be
   revoked before expiry, and AUTH-3 (`POST /auth/logout`) needs that to be real.
3. **Dependencies in `app/core/deps.py`** (new file — nothing in `app/core/`
   currently owns request-scoped dependencies):
   ```python
   async def current_user(...) -> User: ...   # 401 if missing/invalid/revoked
   async def current_org(user=Depends(current_user)) -> Org: ...  # 04 §2 anchor
   ```
   Every tenant route declares `org = Depends(current_org)` — this is the one
   thing the whole tenant-isolation model (`docs/04_ARCHITECTURE_SYSTEM_DESIGN.md`
   §2) hinges on.
4. **`identity/router.py` + `identity/service.py`** (new) — AUTH-1 through
   AUTH-6 from `docs/11_API_REFERENCE.md`, in that order:
   register → login → logout → me → verify-email → password-reset. Register
   and login are the two that unblock everything downstream; verify-email and
   password-reset can follow.
5. **RFC-7807 error handling** — `docs/11_API_REFERENCE.md` §0 already specifies
   the exact catalog (`401 unauthenticated`, `403 forbidden/csrf_failed`, etc.).
   No new decision needed, just implementation against the existing spec.
6. **The two-org leak test, written with AUTH-4 (`/auth/me`) as the first
   tenant-scoped route** — create two orgs, confirm org A's token can never
   read org B's data. AGENTS.md rule 9 requires this ship with every tenant
   feature, not follow it.

## Alternatives considered

- **JWT for the web client too** (instead of session cookie) — rejected by the
  master plan already (§12); noting it here only so a future reviewer sees it
  was considered, not re-litigate it. Session cookies avoid client-side token
  storage (XSS exposure) for the browser surface; the bot has no browser to
  protect, hence JWT there specifically.
- **Third-party auth (Clerk, Auth0, Supabase Auth)** — would remove the need
  for `security.py` and the sessions table entirely. Rejected for now: adds an
  external dependency + cost for a pre-revenue product, and the architecture
  doc's rationale (§12) already assumes rolling this in-house. Worth
  reconsidering only if implementation time becomes the actual bottleneck.
- **Skip revocable sessions, use pure stateless JWT for web too** — simpler (no
  `sessions` table), but AUTH-3 logout would be theater (the cookie clears
  client-side, the token stays valid until expiry if replayed). Rejected: a
  fake logout is worse than a real one.

## Tradeoffs & risks

- **Two new dependencies** (argon2-cffi + a JWT library) — small, well-audited
  libraries, but worth naming since `pyproject.toml`'s dependency surface is
  currently minimal by design.
- **This is genuinely the highest-risk code in the repo so far** — a tenant
  isolation bug here is the "fatal bug class" AGENTS.md rule 9 names directly.
  The two-org leak test is not optional polish; it's the actual safety net.
- **Register/login should ship together** — a login endpoint with no register
  endpoint is untestable end-to-end, and vice versa. Recommend treating AUTH-1
  + AUTH-2 as one unit of work, not split across two PRs.
- **Sequencing:** this blocks the per-org matches endpoint
  (`docs/PROGRESS.md`'s next-but-one item) and nothing else currently in the
  build queue strictly depends on it, so it can land whenever reviewed —
  there's no forcing deadline from other in-flight work.

## Affected docs / code

New: `app/core/security.py`, `app/core/deps.py`, `app/modules/identity/router.py`,
`app/modules/identity/service.py`, `app/modules/identity/schemas.py`, a new
migration for the `sessions` table, `tests/test_auth_tenant_isolation.py` (the
two-org leak test). Modified: `app/main.py` (mount the identity router),
`pyproject.toml` (two new deps), `docs/PROGRESS.md` (this moves from `[ ]` to
`[~]`/`[x]` as pieces land).

## Open questions

- **Session lifetime + refresh strategy** — how long before a session expires,
  and does it silently refresh on activity or require re-login? Not specified
  in the master plan; the tech lead's call.
- **Password reset delivery** — AUTH-6 needs an email (or Telegram?) send path
  that doesn't exist yet. Worth deciding before AUTH-6 specifically, not before
  AUTH-1/2.
- **Does the security engineer's first-task review (`docs/proposals/FIRST_TASK.md`,
  Prompt B mentions "review the auth design before it's built") happen against
  this proposal, or separately?** Recommend: against this one, so his review
  and this plan converge into one implementation rather than two competing ones.

## Answers to the open questions
- Session lifetime: keep access tokens short-lived (e.g., 5–20 minutes). Use refresh tokens stored in an HttpOnly cookie; if using cookies, include CSRF mitigations (e.g., SameSite + CSRF token).
- Password reset delivery: use a transactional email provider (e.g., Resend) to send time-limited password reset links.
