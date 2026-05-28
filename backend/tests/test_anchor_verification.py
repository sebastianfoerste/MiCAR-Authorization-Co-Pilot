from __future__ import annotations

import pytest
from pydantic import ValidationError

from micar.api.anchors import AnchorVerifyIn


def test_anchor_verification_requires_review_note() -> None:
    with pytest.raises(ValidationError):
        AnchorVerifyIn(expected_fingerprint="a" * 64)


def test_anchor_verification_normalizes_review_note() -> None:
    body = AnchorVerifyIn(
        expected_fingerprint="a" * 64,
        review_note="  Amtliche Fundstelle,   Fassung und Fingerprint geprüft.  ",
    )

    assert body.review_note == "Amtliche Fundstelle, Fassung und Fingerprint geprüft."
