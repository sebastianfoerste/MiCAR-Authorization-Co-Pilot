"""Track registry — single lookup point."""

from __future__ import annotations

from micar.tracks.art import ARTTrack
from micar.tracks.base import Track
from micar.tracks.casp import CASPTrack
from micar.tracks.emt import EMTTrack

_TRACKS: dict[str, Track] = {
    "casp": CASPTrack(),
    "emt": EMTTrack(),
    "art": ARTTrack(),
}


def get_track(code: str) -> Track | None:
    return _TRACKS.get(code)


def all_tracks() -> list[Track]:
    return list(_TRACKS.values())
