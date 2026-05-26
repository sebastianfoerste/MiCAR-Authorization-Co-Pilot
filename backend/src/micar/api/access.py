"""Matter-level authorisation helpers."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from micar.models import Mandate, UserRole
from micar.schemas import UserOut


def can_access_mandate(mandate: Mandate, user: UserOut) -> bool:
    return user.role == UserRole.ADMIN.value or mandate.owner_id == user.id


def load_accessible_mandate_or_404(
    session: Session, mandate_id: int, user: UserOut
) -> Mandate:
    mandate = session.get(Mandate, mandate_id)
    if mandate is None or not can_access_mandate(mandate, user):
        raise HTTPException(status_code=404, detail="mandate not found")
    return mandate
