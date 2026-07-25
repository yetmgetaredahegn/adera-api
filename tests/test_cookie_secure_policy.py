"""The `Secure` cookie flag is environment-driven, not hardcoded True.

Why this needs a test at all: a `Secure` cookie is silently dropped by a real
browser over plain HTTP, but `curl` and httpx ignore the flag entirely. So the
auth flow could be (and was) "proven live" with curl while a browser on
http://localhost got no session back at all -- the failure is invisible to every
tool we verify with. This pins the policy itself instead.
"""

from app.core.config import Settings


def test_local_env_relaxes_secure_so_browsers_work_without_tls() -> None:
    assert Settings(env="local", _env_file=None).cookie_secure is False


def test_non_local_envs_keep_secure_on() -> None:
    for env in ("ci", "staging", "prod"):
        # A real (non-default) key is required or the env=prod guard rejects it.
        settings = Settings(env=env, secret_key="not-the-default", _env_file=None)  # noqa: S106
        assert settings.cookie_secure is True, env


def test_explicit_setting_wins_over_the_env_default() -> None:
    """A local developer running behind TLS must be able to turn it back on."""
    assert Settings(env="local", cookie_secure=True, _env_file=None).cookie_secure is True
