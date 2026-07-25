"""SECURITY.md gap G1: a prod deploy must never silently ship the default
SECRET_KEY (it signs session cookies -- app/core/security.py)."""

import pytest
from app.core.config import Settings


def test_insecure_secret_key_rejected_in_prod() -> None:
    with pytest.raises(ValueError, match="insecure default"):
        Settings(env="prod", secret_key="dev-only-insecure-change-me")


def test_real_secret_key_accepted_in_prod() -> None:
    Settings(env="prod", secret_key="a-real-generated-secret")  # must not raise


def test_insecure_secret_key_allowed_outside_prod() -> None:
    Settings(env="local", secret_key="dev-only-insecure-change-me")  # must not raise
    Settings(env="ci", secret_key="dev-only-insecure-change-me")  # must not raise
