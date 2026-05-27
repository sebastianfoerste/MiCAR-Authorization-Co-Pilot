from __future__ import annotations

from micar.anchors.changes import record_anchor_change
from micar.models import Anchor, AnchorChange, TemplateUse


class _Scalars:
    def __init__(self, uses: list[TemplateUse]) -> None:
        self._uses = uses

    def all(self) -> list[TemplateUse]:
        return self._uses


class _Result:
    def __init__(self, uses: list[TemplateUse]) -> None:
        self._uses = uses

    def scalars(self) -> _Scalars:
        return _Scalars(self._uses)


class _Session:
    def __init__(self, uses: list[TemplateUse]) -> None:
        self.uses = uses
        self.added: list[object] = []

    def add(self, row: object) -> None:
        self.added.append(row)
        if isinstance(row, AnchorChange):
            row.id = 41

    def flush(self) -> None:
        return None

    def execute(self, _statement) -> _Result:
        return _Result(self.uses)


def test_source_change_flags_only_rendered_uses_that_cite_changed_anchor() -> None:
    anchor = Anchor(id=7, citation_canonical="Art. 68 MiCAR", level="level_1", authority="eu_regulation")
    affected = TemplateUse(citations=[{"anchor_id": 7}], flagged_by_change_id=None)
    unaffected = TemplateUse(citations=[{"anchor_id": 8}], flagged_by_change_id=None)
    session = _Session([affected, unaffected])

    change = record_anchor_change(  # type: ignore[arg-type]
        session,
        anchor=anchor,
        prior_fingerprint="old",
        source_url="https://example.test/source",
        summary="Changed text.",
    )

    assert change.kind == "amended"
    assert affected.flagged_by_change_id == 41
    assert unaffected.flagged_by_change_id is None


def test_initial_source_text_records_a_new_change_item() -> None:
    anchor = Anchor(id=7, citation_canonical="EBA guidance", level="level_3", authority="eba")
    session = _Session([])

    change = record_anchor_change(  # type: ignore[arg-type]
        session,
        anchor=anchor,
        prior_fingerprint=None,
        source_url="https://example.test/source",
        summary="New text.",
    )

    assert change.kind == "new"
    assert change.anchor_id_prev is None
