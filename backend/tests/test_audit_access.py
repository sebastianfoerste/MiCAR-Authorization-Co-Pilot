from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from micar.api.audit import _require_admin
from micar.models import UserRole
from micar.schemas import UserOut


def _user(role: str) -> UserOut:
    return UserOut(
        id=1,
        email="user@example.com",
        role=role,
        created_at=datetime.now(UTC),
    )


def test_admin_can_open_audit_log() -> None:
    _require_admin(_user(UserRole.ADMIN.value))


def test_lawyer_cannot_open_audit_log() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(_user(UserRole.LAWYER.value))

    assert exc.value.status_code == 403
