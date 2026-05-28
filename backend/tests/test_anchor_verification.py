from __future__ import annotations

import pytest
from pydantic import ValidationError

from micar.api.anchors import AnchorVerifyIn, _to_out, _to_source_out
from micar.models import Anchor


def test_anchor_verification_requires_review_note() -> None:
    with pytest.raises(ValidationError):
        AnchorVerifyIn(expected_fingerprint="a" * 64)


def test_anchor_verification_normalizes_review_note() -> None:
    body = AnchorVerifyIn(
        expected_fingerprint="a" * 64,
        review_note="  Amtliche Fundstelle,   Fassung und Fingerprint geprüft.  ",
    )

    assert body.review_note == "Amtliche Fundstelle, Fassung und Fingerprint geprüft."


def test_anchor_output_includes_review_note() -> None:
    anchor = Anchor(
        id=1,
        level="level_3",
        authority="eba",
        citation_canonical="EBA source",
        version="reviewed",
        source_status="verified",
        review_note="Amtliche Fundstelle und Fingerprint geprüft.",
    )

    assert _to_out(anchor).review_note == "Amtliche Fundstelle und Fingerprint geprüft."


def test_anchor_source_output_includes_full_body_metadata() -> None:
    anchor = Anchor(
        id=1,
        level="level_3",
        authority="eba_esma",
        citation_canonical="EBA/ESMA source",
        version="review",
        body="Amtlicher Quellentext.",
        source_status="fetched_unverified",
    )

    out = _to_source_out(anchor)

    assert out.body == "Amtlicher Quellentext."
    assert out.body_char_count == 22
    assert out.title_or_excerpt == "Amtlicher Quellentext."
