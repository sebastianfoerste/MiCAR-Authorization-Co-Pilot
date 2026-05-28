"""SQLAlchemy 2.0 ORM models for the MiCAR Co-Pilot data model."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from micar.config import get_settings


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enumerations (stored as String — explicit, migration-friendly)
# ---------------------------------------------------------------------------


class Track(StrEnum):
    CASP = "casp"
    EMT = "emt"
    ART = "art"


class MandateState(StrEnum):
    DRAFT = "draft"
    INTAKE = "intake"
    READY_TO_GENERATE = "ready_to_generate"
    GENERATED = "generated"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    FILED = "filed"


class AnchorLevel(StrEnum):
    LEVEL_1 = "level_1"  # Regulation / Directive
    LEVEL_2 = "level_2"  # RTS / ITS / Delegated Act
    LEVEL_3 = "level_3"  # ESMA / EBA / BaFin guidance, Q&A, Merkblätter


class AnchorAuthority(StrEnum):
    EU_REG = "eu_regulation"
    EU_DIR = "eu_directive"
    ESMA = "esma"
    EBA = "eba"
    EBA_ESMA = "eba_esma"
    BAFIN = "bafin"
    NATIONAL_LAW = "national_law"


class TriageStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SourceStatus(StrEnum):
    SEED_UNVERIFIED = "seed_unverified"
    FETCHED_UNVERIFIED = "fetched_unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class UserRole(StrEnum):
    LAWYER = "lawyer"
    CURATOR = "curator"
    ADMIN = "admin"


# ---------------------------------------------------------------------------
# User and audit
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default=UserRole.LAWYER.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    """Append-only event log. BRAO § 203-aware: payload is redacted by writer."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    mandate_id: Mapped[int | None] = mapped_column(ForeignKey("mandates.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    payload_redacted: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


# ---------------------------------------------------------------------------
# Mandates and intake
# ---------------------------------------------------------------------------


class Mandate(Base):
    __tablename__ = "mandates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    client_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    track: Mapped[str] = mapped_column(String(16), index=True)
    state: Mapped[str] = mapped_column(String(32), default=MandateState.DRAFT.value, index=True)
    target_filing_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    redact_client_identifiers: Mapped[bool] = mapped_column(Boolean, default=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    intake_sections: Mapped[list[IntakeSection]] = relationship(
        back_populates="mandate", cascade="all, delete-orphan"
    )


class IntakeSection(Base):
    __tablename__ = "intake_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    mandate_id: Mapped[int] = mapped_column(ForeignKey("mandates.id"), index=True)
    section_key: Mapped[str] = mapped_column(String(64))
    answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    mandate: Mapped[Mandate] = relationship(back_populates="intake_sections")

    __table_args__ = (UniqueConstraint("mandate_id", "section_key", name="uq_intake_section_mandate_key"),)


# ---------------------------------------------------------------------------
# Anchor library
# ---------------------------------------------------------------------------


class Anchor(Base):
    """A pinpoint-citable regulatory norm. Versioned via effective_from/to."""

    __tablename__ = "anchors"

    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    authority: Mapped[str] = mapped_column(String(32), index=True)
    citation_canonical: Mapped[str] = mapped_column(String(512), index=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    version: Mapped[str] = mapped_column(String(64))
    effective_from: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    binding_force_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_status: Mapped[str] = mapped_column(
        String(32), default=SourceStatus.SEED_UNVERIFIED.value, index=True
    )
    source_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("citation_canonical", "version", name="uq_anchor_citation_version"),)


class AnchorChange(Base):
    __tablename__ = "anchor_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    anchor_id_prev: Mapped[int | None] = mapped_column(ForeignKey("anchors.id"), nullable=True)
    anchor_id_new: Mapped[int | None] = mapped_column(ForeignKey("anchors.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32))  # new | amended | superseded | withdrawn
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    triage_status: Mapped[str] = mapped_column(String(32), default=TriageStatus.PENDING.value, index=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Templates and rendered uses
# ---------------------------------------------------------------------------


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    track: Mapped[str] = mapped_column(String(16), index=True)
    clause_key: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(255))
    anchor_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    facts_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    prose_skeleton: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(64))
    last_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("track", "clause_key", "version", name="uq_template_track_clause_ver"),
    )


class TemplateUse(Base):
    __tablename__ = "template_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    mandate_id: Mapped[int] = mapped_column(ForeignKey("mandates.id"), index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"), index=True)
    template_version: Mapped[str] = mapped_column(String(64))
    facts_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rendered_prose: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    llm_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lawyer_review_status: Mapped[str] = mapped_column(String(32), default="pending")
    flagged_by_change_id: Mapped[int | None] = mapped_column(
        ForeignKey("anchor_changes.id"), nullable=True, index=True
    )
    rendered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    mandate_id: Mapped[int] = mapped_column(ForeignKey("mandates.id"), index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    format: Mapped[str] = mapped_column(String(16))
    template_use_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    version: Mapped[int] = mapped_column(Integer, default=1)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    mandate_id: Mapped[int | None] = mapped_column(ForeignKey("mandates.id"), nullable=True, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    agent_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed", index=True)
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    input_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    step_key: Mapped[str] = mapped_column(String(96))
    status: Mapped[str] = mapped_column(String(32), default="completed")
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AgentFinding(Base):
    __tablename__ = "agent_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    mandate_id: Mapped[int | None] = mapped_column(ForeignKey("mandates.id"), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    mandate_id: Mapped[int | None] = mapped_column(ForeignKey("mandates.id"), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="proposed", index=True)
    title: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index("ix_anchors_effective", Anchor.effective_from, Anchor.effective_to)
Index("ix_anchor_changes_status_detected", AnchorChange.triage_status, AnchorChange.detected_at)
Index("ix_agent_runs_mandate_created", AgentRun.mandate_id, AgentRun.created_at)
Index("ix_agent_findings_mandate_status", AgentFinding.mandate_id, AgentFinding.status)


# ---------------------------------------------------------------------------
# Engine / session factory
# ---------------------------------------------------------------------------

_engine = None
_SessionFactory: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True, future=True)
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionFactory


@contextmanager
def session_scope() -> Iterator:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_schema() -> None:
    """Create all tables. For tests + bootstrap. Production uses Alembic."""
    Base.metadata.create_all(get_engine())
