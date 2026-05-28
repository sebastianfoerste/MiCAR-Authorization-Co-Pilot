"""Pydantic schemas for the API surface.

Domain models live in `models.py` (SQLAlchemy). This file contains shared
wire formats used by authentication and mandate routes.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str | None = None
    role: str
    created_at: datetime
    last_login_at: datetime | None = None


class MandateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    client_label: str | None = None
    track: str
    state: str
    target_filing_date: date | None = None
    created_at: datetime
    updated_at: datetime
