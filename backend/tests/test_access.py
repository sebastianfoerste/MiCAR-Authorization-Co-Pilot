from __future__ import annotations

from datetime import UTC, datetime

from micar.api.access import can_access_mandate
from micar.models import Mandate, UserRole
from micar.schemas import UserOut


def _user(id_: int, role: str = UserRole.LAWYER.value) -> UserOut:
    return UserOut(
        id=id_,
        email=f"user{id_}@example.com",
        role=role,
        created_at=datetime.now(UTC),
    )


def test_owner_can_access_own_mandate() -> None:
    mandate = Mandate(owner_id=7)
    assert can_access_mandate(mandate, _user(7))


def test_lawyer_cannot_access_another_owners_mandate() -> None:
    mandate = Mandate(owner_id=7)
    assert not can_access_mandate(mandate, _user(8))


def test_admin_can_access_any_mandate() -> None:
    mandate = Mandate(owner_id=7)
    assert can_access_mandate(mandate, _user(8, UserRole.ADMIN.value))
