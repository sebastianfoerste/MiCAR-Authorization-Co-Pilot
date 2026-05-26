"""Shared pytest fixtures. Tests use sqlite in-memory by default — the small
number of Postgres-only column types (JSONB, ARRAY) are avoided in fixtures by
using direct SQLAlchemy session helpers rather than Alembic migrations.
"""
from __future__ import annotations

import os

import pytest

# Force test env before any micar imports
os.environ.setdefault("JWT_SHARED_SECRET", "test-secret-thirty-two-bytes-min-aaaaa")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:x@localhost/x")


@pytest.fixture
def jwt_secret() -> str:
    return os.environ["JWT_SHARED_SECRET"]
