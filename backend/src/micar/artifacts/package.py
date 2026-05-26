"""Package assembly — TemplateUses → grouped DOCX + citation index CSV → zip."""
from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from micar.artifacts.docx import ClauseInput, render_package_docx
from micar.config import get_settings
from micar.models import Anchor, Artifact, Mandate, Template, TemplateUse


@dataclass
class PackageBuildResult:
    artifact_id: int
    zip_path: Path
    sha256: str
    total_clauses: int
    flagged_clauses: int


def _resolve_citation_anchor(
    session: Session, anchor_ids: list[int | None]
) -> dict[int, Anchor]:
    real_ids = [i for i in anchor_ids if i is not None]
    if not real_ids:
        return {}
    rows = session.execute(select(Anchor).where(Anchor.id.in_(real_ids))).scalars().all()
    return {a.id: a for a in rows}


def validated_latest_template_uses(session: Session, mandate_id: int) -> list[TemplateUse]:
    """Return latest clauses only after review and current-source validation."""
    rendered_uses = (
        session.execute(
            select(TemplateUse)
            .where(TemplateUse.mandate_id == mandate_id)
            .order_by(TemplateUse.id.desc())
        )
        .scalars()
        .all()
    )
    if not rendered_uses:
        raise ValueError("no template uses on this mandate yet")

    latest_by_template: dict[int, TemplateUse] = {}
    for use in rendered_uses:
        latest_by_template.setdefault(use.template_id, use)
    uses = sorted(latest_by_template.values(), key=lambda use: use.id)

    unapproved_uses = [
        f"{use.id} ({use.lawyer_review_status})"
        for use in uses
        if use.lawyer_review_status != "approved"
    ]
    if unapproved_uses:
        raise ValueError(
            "package blocked: latest template uses require lawyer approval: "
            + ", ".join(unapproved_uses)
        )
    flagged_uses = [str(use.id) for use in uses if use.flagged_by_change_id is not None]
    if flagged_uses:
        raise ValueError(
            "package blocked: latest template uses are flagged by source changes: "
            + ", ".join(flagged_uses)
        )
    cited_anchor_ids = {
        citation.get("anchor_id")
        for use in uses
        for citation in (use.citations or [])
        if citation.get("anchor_id") is not None
    }
    current_anchors = (
        session.execute(select(Anchor).where(Anchor.id.in_(cited_anchor_ids))).scalars().all()
        if cited_anchor_ids
        else []
    )
    if len(current_anchors) != len(cited_anchor_ids) or any(
        anchor.source_status != "verified" for anchor in current_anchors
    ):
        raise ValueError("package blocked: all cited sources must remain verified")
    return uses


def build_package(session: Session, *, mandate: Mandate) -> PackageBuildResult:
    """Bundle the latest approved TemplateUses into a DOCX + citation CSV + zip."""
    settings = get_settings()
    artifacts_root = Path(settings.artifacts_dir)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    uses = validated_latest_template_uses(session, mandate.id)

    clauses: list[ClauseInput] = []
    citation_rows: list[dict[str, str]] = []
    template_rows = (
        session.execute(select(Template).where(Template.id.in_([use.template_id for use in uses])))
        .scalars()
        .all()
    )
    titles = {row.id: row.title for row in template_rows}
    for use in uses:
        cits = [c.get("citation", "") for c in (use.citations or [])]
        clauses.append(
            ClauseInput(
                clause_key=str(use.template_id),
                title=titles.get(use.template_id, f"Klausel {use.template_id}"),
                prose=use.rendered_prose or "[leer]",
                citations=cits,
            )
        )
        anchor_ids = [c.get("anchor_id") for c in (use.citations or [])]
        anchors_by_id = _resolve_citation_anchor(session, anchor_ids)
        for c in use.citations or []:
            anchor = anchors_by_id.get(c.get("anchor_id")) if c.get("anchor_id") else None
            citation_rows.append(
                {
                    "template_use_id": str(use.id),
                    "citation": c.get("citation", ""),
                    "anchor_id": str(c.get("anchor_id") or ""),
                    "url": anchor.url if anchor else "",
                    "effective_from": str(anchor.effective_from) if anchor else "",
                }
            )

    # Compute next version
    last_version = (
        session.execute(
            select(Artifact.version)
            .where(Artifact.mandate_id == mandate.id)
            .where(Artifact.kind == "package_docx")
            .order_by(Artifact.version.desc())
        )
        .scalars()
        .first()
    )
    version = (last_version or 0) + 1

    mandate_dir = artifacts_root / f"mandate-{mandate.id}"
    mandate_dir.mkdir(parents=True, exist_ok=True)
    docx_path = mandate_dir / f"package-v{version}.docx"
    render_package_docx(
        docx_path,
        mandate_name=mandate.name,
        track=mandate.track,
        clauses=clauses,
        version=version,
    )

    # Citation index CSV
    csv_buf = io.StringIO()
    writer = csv.DictWriter(
        csv_buf,
        fieldnames=["template_use_id", "citation", "anchor_id", "url", "effective_from"],
    )
    writer.writeheader()
    writer.writerows(citation_rows)
    citations_csv_bytes = csv_buf.getvalue().encode("utf-8")
    citations_csv_path = mandate_dir / f"citations-v{version}.csv"
    citations_csv_path.write_bytes(citations_csv_bytes)

    # Zip
    zip_path = mandate_dir / f"package-v{version}.zip"
    sha = hashlib.sha256()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(docx_path, arcname=docx_path.name)
        z.writestr(citations_csv_path.name, citations_csv_bytes)
    sha.update(zip_path.read_bytes())

    template_use_ids = [u.id for u in uses]
    artifact = Artifact(
        mandate_id=mandate.id,
        kind="package_docx",
        format="zip",
        template_use_ids=template_use_ids,
        file_path=str(zip_path),
        version=version,
        sha256=sha.hexdigest(),
    )
    session.add(artifact)
    session.flush()

    return PackageBuildResult(
        artifact_id=artifact.id,
        zip_path=zip_path,
        sha256=sha.hexdigest(),
        total_clauses=len(clauses),
        flagged_clauses=0,
    )
