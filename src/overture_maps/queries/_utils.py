"""Shared utilities for query modules."""

from __future__ import annotations

DEFAULT_LIMIT = 10


def validate_coords(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise ValueError(f"lat must be between -90 and 90, got: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"lon must be between -180 and 180, got: {lon}")
