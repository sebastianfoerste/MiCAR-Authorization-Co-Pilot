"""Template version gates for review and export."""

from __future__ import annotations

import pytest

from micar.artifacts.package import (
    latest_template_uses_by_clause,
    template_version_problem,
    validated_latest_template_uses,
)
from micar.models import Template, TemplateUse


class _RowsResult:
    def __init__(self, rows: list[tuple[TemplateUse, Template]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[TemplateUse, Template]]:
        return self.rows


class _Session:
    def __init__(self, rows: list[tuple[TemplateUse, Template]]) -> None:
        self.rows = rows
        self.templates = {template.id: template for _, template in rows}

    def execute(self, _statement) -> _RowsResult:
        return _RowsResult(self.rows)

    def get(self, model, row_id: int):
        assert model is Template
        return self.templates.get(row_id)


def _template(row_id: int, clause_key: str, version: str) -> Template:
    return Template(
        id=row_id,
        track="casp",
        clause_key=clause_key,
        title=clause_key,
        version=version,
    )


def _use(row_id: int, template: Template, version: str) -> TemplateUse:
    return TemplateUse(
        id=row_id,
        mandate_id=4,
        template_id=template.id,
        template_version=version,
        lawyer_review_status="approved",
    )


def test_latest_uses_collapse_superseded_template_rows_by_clause_key() -> None:
    old = _template(10, "authorization_application", "0.1.0")
    new = _template(11, "authorization_application", "0.2.0")
    complaints = _template(12, "complaints_handling", "0.2.0")
    rows = [
        (_use(103, new, "0.2.0"), new),
        (_use(102, complaints, "0.2.0"), complaints),
        (_use(101, old, "0.1.0"), old),
    ]

    latest = latest_template_uses_by_clause(_Session(rows), mandate_id=4)  # type: ignore[arg-type]

    assert [use.id for use in latest] == [102, 103]


def test_superseded_template_version_must_be_regenerated_before_export() -> None:
    old = _template(10, "authorization_application", "0.1.0")
    use = _use(101, old, "0.1.0")
    session = _Session([(use, old)])

    assert template_version_problem(session, use) == "101 (0.1.0 -> 0.3.0)"  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="regenerated against current template versions"):
        validated_latest_template_uses(session, mandate_id=4)  # type: ignore[arg-type]
