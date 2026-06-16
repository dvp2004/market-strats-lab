from __future__ import annotations

TRACK_ID = "gma_alpha"
PHASE_ID = "gma0_feasibility"

FORBIDDEN_PHASE_PREFIXES = ("phase20", "phase21", "phase22", "phase23")


def validate_track_identifiers(track_id: str, phase_id: str) -> None:
    if track_id != TRACK_ID:
        raise ValueError(f"track.track_id must be {TRACK_ID!r}")
    if phase_id != PHASE_ID:
        raise ValueError(f"track.phase_id must be {PHASE_ID!r}")
    lowered = (track_id.lower(), phase_id.lower())
    for identifier in lowered:
        if identifier.startswith(FORBIDDEN_PHASE_PREFIXES):
            raise ValueError("GMA identifiers must not use frozen phase prefixes")
