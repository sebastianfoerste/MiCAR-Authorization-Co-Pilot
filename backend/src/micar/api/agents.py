"""Supervised agent endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select

from micar.agents.runtime import AGENT_DEFINITIONS, all_agent_catalog, execute_mandate_agent_run
from micar.api.access import load_accessible_mandate_or_404
from micar.api.auth import get_current_user
from micar.compliance.audit import write_audit
from micar.models import AgentAction, AgentFinding, AgentRun, AgentStep, session_scope
from micar.schemas import UserOut

router = APIRouter(tags=["agents"])


class AgentCatalogOut(BaseModel):
    key: str
    label: str
    description: str


class AgentRunCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_key: Literal[
        "all",
        "readiness",
        "citation_auditor",
        "draft_qa",
        "source_monitor",
        "package_review",
        "template_improvement",
    ] = "all"


class AgentActionDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    review_note: str = Field(min_length=20, max_length=2000)

    @field_validator("review_note")
    @classmethod
    def normalize_review_note(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 20:
            raise ValueError("review_note must document the action decision")
        return cleaned


class AgentRunOut(BaseModel):
    id: int
    mandate_id: int | None
    agent_key: str
    status: str
    trigger: str
    result_summary: str | None
    created_at: datetime
    completed_at: datetime | None
    finding_count: int
    action_count: int


class AgentStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    step_key: str
    status: str
    input_summary: str | None
    output: dict | None
    created_at: datetime


class AgentFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    mandate_id: int | None
    severity: str
    title: str
    body: str
    evidence: dict | None
    status: str
    created_at: datetime


class AgentActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    mandate_id: int | None
    action_type: str
    status: str
    title: str
    payload: dict | None
    created_at: datetime
    decided_by: int | None
    decided_at: datetime | None
    decision_note: str | None


class AgentRunDetailOut(BaseModel):
    run: AgentRunOut
    steps: list[AgentStepOut]
    findings: list[AgentFindingOut]
    actions: list[AgentActionOut]


def _run_out(session, run: AgentRun) -> AgentRunOut:
    finding_count = (
        session.scalar(select(func.count()).select_from(AgentFinding).where(AgentFinding.run_id == run.id))
        or 0
    )
    action_count = (
        session.scalar(select(func.count()).select_from(AgentAction).where(AgentAction.run_id == run.id)) or 0
    )
    return AgentRunOut(
        id=run.id,
        mandate_id=run.mandate_id,
        agent_key=run.agent_key,
        status=run.status,
        trigger=run.trigger,
        result_summary=run.result_summary,
        created_at=run.created_at,
        completed_at=run.completed_at,
        finding_count=finding_count,
        action_count=action_count,
    )


@router.get("/agents/catalog", response_model=list[AgentCatalogOut])
def list_agent_catalog(_user: UserOut = Depends(get_current_user)) -> list[AgentCatalogOut]:
    return [AgentCatalogOut(**definition.__dict__) for definition in all_agent_catalog()]


@router.get("/mandates/{mandate_id}/agent-runs", response_model=list[AgentRunOut])
def list_mandate_agent_runs(
    mandate_id: int,
    user: UserOut = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50),
) -> list[AgentRunOut]:
    with session_scope() as session:
        load_accessible_mandate_or_404(session, mandate_id, user)
        rows = (
            session.execute(
                select(AgentRun)
                .where(AgentRun.mandate_id == mandate_id)
                .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [_run_out(session, run) for run in rows]


@router.post("/mandates/{mandate_id}/agent-runs", response_model=AgentRunDetailOut, status_code=201)
def create_mandate_agent_run(
    mandate_id: int,
    body: AgentRunCreateIn,
    user: UserOut = Depends(get_current_user),
) -> AgentRunDetailOut:
    with session_scope() as session:
        mandate = load_accessible_mandate_or_404(session, mandate_id, user)
        run = execute_mandate_agent_run(
            session,
            mandate=mandate,
            actor_id=user.id,
            agent_key=body.agent_key,
        )
        write_audit(
            session,
            kind="agent.run.completed",
            actor_id=user.id,
            mandate_id=mandate.id,
            payload={
                "agent_key": run.agent_key,
                "requested_agent_key": body.agent_key,
            },
        )
        return _run_detail_out(session, run.id, mandate_id)


@router.get("/mandates/{mandate_id}/agent-runs/{run_id}", response_model=AgentRunDetailOut)
def get_mandate_agent_run(
    mandate_id: int,
    run_id: int,
    user: UserOut = Depends(get_current_user),
) -> AgentRunDetailOut:
    with session_scope() as session:
        load_accessible_mandate_or_404(session, mandate_id, user)
        return _run_detail_out(session, run_id, mandate_id)


@router.post("/mandates/{mandate_id}/agent-actions/{action_id}/decision", response_model=AgentActionOut)
def decide_agent_action(
    mandate_id: int,
    action_id: int,
    body: AgentActionDecisionIn,
    user: UserOut = Depends(get_current_user),
) -> AgentActionOut:
    with session_scope() as session:
        mandate = load_accessible_mandate_or_404(session, mandate_id, user)
        action = session.get(AgentAction, action_id)
        if action is None or action.mandate_id != mandate.id:
            raise HTTPException(status_code=404, detail="agent action not found")
        if action.status != "proposed":
            raise HTTPException(status_code=409, detail="agent action already decided")
        action.status = body.decision
        action.decided_by = user.id
        action.decided_at = datetime.now(UTC)
        action.decision_note = body.review_note
        write_audit(
            session,
            kind="agent.action.decided",
            actor_id=user.id,
            mandate_id=mandate.id,
            payload={
                "action_id": action.id,
                "action_type": action.action_type,
                "decision": body.decision,
            },
        )
        return AgentActionOut.model_validate(action)


def _run_detail_out(session, run_id: int, mandate_id: int) -> AgentRunDetailOut:
    run = session.get(AgentRun, run_id)
    if run is None or run.mandate_id != mandate_id:
        raise HTTPException(status_code=404, detail="agent run not found")
    steps = (
        session.execute(select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.id))
        .scalars()
        .all()
    )
    findings = (
        session.execute(select(AgentFinding).where(AgentFinding.run_id == run.id).order_by(AgentFinding.id))
        .scalars()
        .all()
    )
    actions = (
        session.execute(select(AgentAction).where(AgentAction.run_id == run.id).order_by(AgentAction.id))
        .scalars()
        .all()
    )
    return AgentRunDetailOut(
        run=_run_out(session, run),
        steps=[AgentStepOut.model_validate(step) for step in steps],
        findings=[AgentFindingOut.model_validate(finding) for finding in findings],
        actions=[AgentActionOut.model_validate(action) for action in actions],
    )


def validate_agent_key(agent_key: str) -> None:
    if agent_key != "all" and agent_key not in AGENT_DEFINITIONS:
        raise HTTPException(status_code=400, detail=f"unknown agent: {agent_key}")
