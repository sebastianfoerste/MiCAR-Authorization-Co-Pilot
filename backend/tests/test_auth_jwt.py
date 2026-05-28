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
from micar.models import AuditEvent, User


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


def test_provisioning_rejects_invalid_email_claim_before_database_access(monkeypatch) -> None:
    monkeypatch.setenv("USER_EMAIL_ALLOWLIST", "")
    monkeypatch.setenv("ALLOW_UNRESTRICTED_DEV_AUTH", "true")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc:
            _provision_or_touch(None, email="audit-browser@example.test", name=None)  # type: ignore[arg-type]
        assert exc.value.status_code == 401
    finally:
        get_settings.cache_clear()


class _Result:
    def __init__(self, *, one_or_none=None, one=None) -> None:
        self._one_or_none = one_or_none
        self._one = one

    def scalar_one_or_none(self):
        return self._one_or_none

    def scalar_one(self):
        return self._one


class _ConcurrentProvisionSession:
    def __init__(self, existing_user: User) -> None:
        self.existing_user = existing_user
        self.calls = 0
        self.added = []

    def execute(self, _statement):
        self.calls += 1
        if self.calls in {1, 2}:
            return _Result(one_or_none=None)
        return _Result(one=self.existing_user)

    def add(self, row) -> None:
        self.added.append(row)

    def flush(self) -> None:
        return None


class _NewProvisionSession:
    def __init__(self, user: User) -> None:
        self.user = user
        self.calls = 0
        self.added: list[object] = []

    def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return _Result(one_or_none=None)
        return _Result(one_or_none=self.user.id)

    def get(self, _model, _identifier: int) -> User:
        return self.user

    def add(self, row: object) -> None:
        self.added.append(row)

    def flush(self) -> None:
        return None


def test_new_user_audit_payload_does_not_include_email(monkeypatch) -> None:
    monkeypatch.setenv("USER_EMAIL_ALLOWLIST", "")
    monkeypatch.setenv("ALLOW_UNRESTRICTED_DEV_AUTH", "true")
    get_settings.cache_clear()
    user = User(id=7, email="user@example.com", role="lawyer", name=None)
    session = _NewProvisionSession(user)
    try:
        result = _provision_or_touch(  # type: ignore[arg-type]
            session, email="user@example.com", name="Test User"
        )
        assert result is user
        audit = next(row for row in session.added if isinstance(row, AuditEvent))
        assert audit.payload_redacted == {"user_id": 7}
    finally:
        get_settings.cache_clear()


def test_concurrent_provisioning_reloads_conflicting_user_without_duplicate_audit(monkeypatch) -> None:
    monkeypatch.setenv("USER_EMAIL_ALLOWLIST", "")
    monkeypatch.setenv("ALLOW_UNRESTRICTED_DEV_AUTH", "true")
    get_settings.cache_clear()
    user = User(id=7, email="user@example.com", role="lawyer", name=None)
    session = _ConcurrentProvisionSession(user)
    try:
        result = _provision_or_touch(  # type: ignore[arg-type]
            session, email="user@example.com", name="Test User"
        )
        assert result is user
        assert user.name == "Test User"
        assert user.last_login_at is not None
        assert session.added == []
    finally:
        get_settings.cache_clear()
