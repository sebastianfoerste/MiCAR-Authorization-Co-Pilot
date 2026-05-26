"""Template registry.

Templates are YAML files under `templates/catalog/<track>/<clause_key>.yaml`.
Each describes one renderable clause: which anchors it must cite, which facts
it consumes, and a skeleton the lawyer-authored prompt fills in.

YAML shape (Phase 3):

  clause_key: governance
  track: casp
  version: "0.1.0"
  title: "Governance-Konzept"
  anchor_refs:
    - "Art. 68 VO (EU) 2023/1114 (MiCAR)"
    - "Art. 68 Abs. 1 VO (EU) 2023/1114 (MiCAR)"
  required_sections:
    - entity
    - governance
  prose_skeleton: |
    ## 1. Geschäftsleitung
    [Hier füllt das gunnercooke-Team die fachliche Aussage entlang von
     {{ anchor:Art. 68 Abs. 1 VO (EU) 2023/1114 (MiCAR) }} aus.]
  author_note: "Lawyer review required before any client-facing render."

The renderer (see `templates/renderer.py`) takes a Template + intake facts +
resolved anchors and asks the LLM to produce a RenderedClause(prose, citations).
The registry itself is pure — it loads, validates, and serves Templates.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

CATALOG_DIR = Path(__file__).parent / "catalog"


class TemplateDef(BaseModel):
    """Strict in-memory representation of a template YAML."""

    model_config = ConfigDict(extra="forbid")

    clause_key: str = Field(min_length=1, max_length=128)
    track: str = Field(pattern=r"^(casp|emt|art)$")
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    anchor_refs: list[str] = Field(default_factory=list)
    required_sections: list[str] = Field(default_factory=list)
    prose_skeleton: str = ""
    author_note: str = ""
    conditional_on_services: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class TemplateRegistry:
    """Loaded templates, keyed by (track, clause_key)."""

    by_key: dict[tuple[str, str], TemplateDef]

    def get(self, track: str, clause_key: str) -> TemplateDef | None:
        return self.by_key.get((track, clause_key))

    def for_track(self, track: str) -> list[TemplateDef]:
        return [t for (tr, _), t in self.by_key.items() if tr == track]

    def __iter__(self) -> Iterator[TemplateDef]:
        return iter(self.by_key.values())


def _iter_yaml_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    yield from sorted(root.rglob("*.yaml"))


def load_registry(catalog_dir: Path | None = None) -> TemplateRegistry:
    root = catalog_dir or CATALOG_DIR
    by_key: dict[tuple[str, str], TemplateDef] = {}
    for path in _iter_yaml_files(root):
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:  # empty placeholder file
            continue
        tpl = TemplateDef.model_validate(data)
        by_key[(tpl.track, tpl.clause_key)] = tpl
    return TemplateRegistry(by_key=by_key)
