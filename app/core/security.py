"""All crypto in one place (05 §3). Nothing else touches password hashing,
session signing, CSRF, or the bot JWT — that concentration is the point: one
place to audit, one place to get right.

Auth model (master plan §12, `docs/proposals/001-auth-implementation-plan.md`):
web = httpOnly signed session cookie + CSRF double-submit token on unsafe
methods; Telegram bot = short-lived JWT service account.
"""

import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

SESSION_COOKIE_NAME = "adera_session"
CSRF_COOKIE_NAME = "adera_csrf"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days — open question in the
# auth proposal (001), not a considered decision; revisit with the tech lead.

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def _serializer() -> URLSafeTimedSerializer:
    # Cached per-call rather than module-level: settings.secret_key could differ
    # across test parametrization; this is cheap (no I/O) so it's not worth a
    # premature cache.
    return URLSafeTimedSerializer(settings.secret_key, salt="adera-session-v1")


def sign_session_id(session_id: uuid.UUID) -> str:
    """The cookie VALUE. Signing prevents a client from substituting a
    different session_id; expiry/revocation are still checked server-side
    against the `sessions` table on every request (AGENTS.md rule 11: the
    signature alone is not the trust boundary)."""
    return _serializer().dumps(str(session_id))


def unsign_session_id(token: str) -> uuid.UUID | None:
    """None on ANY failure (bad signature, expired, malformed) -- the caller's
    cue to treat the request as unauthenticated, never to guess a session."""
    try:
        raw = _serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
        return uuid.UUID(raw)
    except (BadSignature, SignatureExpired, ValueError):
        return None


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_tokens_match(cookie_value: str | None, header_value: str | None) -> bool:
    """Double-submit pattern: no server-side CSRF storage needed. A same-site
    attacker cannot read the cookie to put its value in the header (that's the
    whole point), so a matching pair proves the request came from a page that
    could read our cookie -- i.e. our own origin (with SameSite=Lax as a second
    layer, see the Set-Cookie call sites)."""
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)


def create_bot_jwt(service_account: str, ttl_seconds: int = 300) -> str:
    """Telegram bot service-account token -- short-lived by design (05 §3);
    the bot re-requests one rather than holding a long-lived credential."""
    now = datetime.now(UTC)
    payload = {
        "sub": service_account,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def verify_bot_jwt(token: str) -> str | None:
    """Returns the service_account subject, or None on any failure (expired,
    bad signature, malformed) -- same never-guess discipline as sessions."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        sub = payload.get("sub")
        return sub if isinstance(sub, str) else None
    except jwt.PyJWTError:
        return None
