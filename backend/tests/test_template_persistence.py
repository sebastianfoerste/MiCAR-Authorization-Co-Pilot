from __future__ import annotations

from micar.models import Template
from micar.templates.registry import load_registry
from micar.templates.renderer import _omitted_required_citations, _upsert_template_row


class _Result:
    def __init__(self, row: Template | None) -> None:
        self._row = row

    def scalar_one_or_none(self) -> Template | None:
        return self._row


class _Session:
    def __init__(self, existing: Template | None = None) -> None:
        self.existing = existing
        self.added: list[Template] = []

    def execute(self, _statement) -> _Result:
        return _Result(self.existing)

    def add(self, row: Template) -> None:
        self.added.append(row)

    def flush(self) -> None:
        return None


def test_template_row_is_created_before_template_use_persistence() -> None:
    template = load_registry().get("casp", "governance")
    assert template is not None
    session = _Session()

    row = _upsert_template_row(session, template)  # type: ignore[arg-type]

    assert session.added == [row]
    assert row.clause_key == "governance"
    assert row.anchor_refs == template.anchor_refs


def test_existing_template_row_is_refreshed_from_catalog() -> None:
    template = load_registry().get("casp", "governance")
    assert template is not None
    existing = Template(
        track="casp",
        clause_key="governance",
        version=template.version,
        title="stale",
    )
    session = _Session(existing)

    row = _upsert_template_row(session, template)  # type: ignore[arg-type]

    assert row is existing
    assert not session.added
    assert row.title == template.title


def test_required_citations_cannot_be_silently_omitted() -> None:
    template = load_registry().get("casp", "governance")
    assert template is not None

    omitted = _omitted_required_citations(
        template,
        ["Artikel 68 VO (EU) 2023/1114 (MiCAR)"],
    )

    assert "Art. 67 VO (EU) 2023/1114 (MiCAR)" in omitted
    assert "Art. 73 VO (EU) 2023/1114 (MiCAR)" in omitted
    assert "Art. 68 VO (EU) 2023/1114 (MiCAR)" not in omitted
