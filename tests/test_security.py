"""Pure crypto logic — no DB, no network (SKILLS.md R6)."""

from datetime import UTC, datetime, timedelta

import jwt
from app.core.config import settings
from app.core.security import (
    create_bot_jwt,
    csrf_tokens_match,
    generate_csrf_token,
    hash_password,
    sign_session_id,
    unsign_session_id,
    verify_bot_jwt,
    verify_password,
)


def test_password_hash_round_trips() -> None:
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True


def test_password_hash_rejects_wrong_password() -> None:
    h = hash_password("correct horse battery staple")
    assert verify_password("wrong password", h) is False


def test_password_hash_is_not_the_plaintext() -> None:
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"


def test_session_id_signs_and_unsigns() -> None:
    import uuid

    session_id = uuid.uuid4()
    token = sign_session_id(session_id)
    assert unsign_session_id(token) == session_id


def test_session_id_rejects_tampered_token() -> None:
    import uuid

    token = sign_session_id(uuid.uuid4())
    # Tamper a MIDDLE character, not the last one: the last character of a
    # base64 group can carry "don't-care" bits (padding-adjacent), so some
    # substitutions there decode to identical bytes and aren't real tampering
    # at all -- verified live: flipping the last char of a real token left it
    # still valid, which is a base64 encoding artifact, not a signature bug.
    mid = len(token) // 2
    tampered = token[:mid] + ("A" if token[mid] != "A" else "B") + token[mid + 1 :]
    assert unsign_session_id(tampered) is None


def test_session_id_rejects_garbage() -> None:
    assert unsign_session_id("not-a-real-token") is None


def test_csrf_tokens_match_requires_both_present() -> None:
    token = generate_csrf_token()
    assert csrf_tokens_match(token, token) is True
    assert csrf_tokens_match(token, None) is False
    assert csrf_tokens_match(None, token) is False
    assert csrf_tokens_match(None, None) is False


def test_csrf_tokens_match_rejects_mismatch() -> None:
    assert csrf_tokens_match(generate_csrf_token(), generate_csrf_token()) is False


def test_bot_jwt_round_trips() -> None:
    token = create_bot_jwt("telegram-bot")
    assert verify_bot_jwt(token) == "telegram-bot"


def test_bot_jwt_rejects_garbage() -> None:
    assert verify_bot_jwt("not-a-real-jwt") is None


def test_bot_jwt_rejects_expired() -> None:
    now = datetime.now(UTC)
    already_expired = jwt.encode(
        {
            "sub": "telegram-bot",
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    assert verify_bot_jwt(already_expired) is None
