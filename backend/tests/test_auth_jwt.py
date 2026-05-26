"""Smoke tests for the JWT bridge with the Next.js frontend.

Locks the contract: the backend accepts HS256 tokens signed with
JWT_SHARED_SECRET whose `iss` matches and `aud` matches, and rejects everything
else with 401.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from micar.api.auth import _decode, _provision_or_touch
from micar.config import get_settings


def _mint(secret: str, *, iss: str, aud: str, sub: str = "user@example.com") -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": sub,
            "name": "Test User",
            "iss": iss,
            "aud": aud,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )


def test_decode_accepts_well_formed_token(jwt_secret: str) -> None:
    settings = get_settings()
    token = _mint(jwt_secret, iss=settings.jwt_issuer, aud=settings.jwt_audience)
    claims = _decode(token)
    assert claims["sub"] == "user@example.com"
    assert claims["name"] == "Test User"


def test_decode_rejects_wrong_audience(jwt_secret: str) -> None:
    settings = get_settings()
    token = _mint(jwt_secret, iss=settings.jwt_issuer, aud="other-aud")
    with pytest.raises(HTTPException) as exc:
        _decode(token)
    assert exc.value.status_code == 401


def test_decode_rejects_wrong_issuer(jwt_secret: str) -> None:
    settings = get_settings()
    token = _mint(jwt_secret, iss="other-issuer", aud=settings.jwt_audience)
    with pytest.raises(HTTPException) as exc:
        _decode(token)
    assert exc.value.status_code == 401


def test_decode_rejects_wrong_signature(jwt_secret: str) -> None:
    settings = get_settings()
    token = _mint(
        "a-different-secret-of-sufficient-length",
        iss=settings.jwt_issuer,
        aud=settings.jwt_audience,
    )
    with pytest.raises(HTTPException) as exc:
        _decode(token)
    assert exc.value.status_code == 401


def test_decode_rejects_expired_token(jwt_secret: str) -> None:
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=10)
    token = jwt.encode(
        {
            "sub": "user@example.com",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=1)).timestamp()),
        },
        jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        _decode(token)
    assert exc.value.status_code == 401


def test_decode_rejects_unconfigured_short_shared_secret(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SHARED_SECRET", "too-short")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc:
            _decode("irrelevant")
        assert exc.value.status_code == 503
    finally:
        get_settings.cache_clear()


def test_provisioning_denies_empty_allowlist_without_dev_override(monkeypatch) -> None:
    monkeypatch.setenv("USER_EMAIL_ALLOWLIST", "")
    monkeypatch.setenv("ALLOW_UNRESTRICTED_DEV_AUTH", "false")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc:
            _provision_or_touch(None, email="user@example.com", name=None)  # type: ignore[arg-type]
        assert exc.value.status_code == 403
    finally:
        get_settings.cache_clear()
