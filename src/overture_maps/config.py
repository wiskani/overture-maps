"""Configuration loader for overture-maps library.

Priority order: environment variables > overture.yaml > ValueError.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "overture.yaml"


@dataclass
class BBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def __post_init__(self) -> None:
        if not (-180 <= self.min_lon <= 180) or not (-180 <= self.max_lon <= 180):
            raise ValueError(f"Invalid longitude in bbox: {self}")
        if not (-90 <= self.min_lat <= 90) or not (-90 <= self.max_lat <= 90):
            raise ValueError(f"Invalid latitude in bbox: {self}")
        if self.min_lon >= self.max_lon or self.min_lat >= self.max_lat:
            raise ValueError(f"bbox min values must be less than max values: {self}")

    def as_str(self) -> str:
        return f"{self.min_lon},{self.min_lat},{self.max_lon},{self.max_lat}"


@dataclass
class Config:
    city: str
    bbox: BBox
    data_release: str
    schema_version: str
    themes: list[str] = field(default_factory=list)


def load_config(path: Path | None = None) -> Config:
    """Load config from overture.yaml with environment variable overrides."""
    config_path = path or _DEFAULT_CONFIG_PATH
    raw: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}

    city = os.environ.get("OVERTURE_CITY") or raw.get("city") or ""
    if not city:
        raise ValueError(
            "city not configured. Set OVERTURE_CITY env var or create overture.yaml."
        )

    bbox_raw = raw.get("bbox", {})
    bbox = BBox(
        min_lon=float(
            os.environ.get("OVERTURE_BBOX_MIN_LON") or bbox_raw.get("min_lon", 0)
        ),
        min_lat=float(
            os.environ.get("OVERTURE_BBOX_MIN_LAT") or bbox_raw.get("min_lat", 0)
        ),
        max_lon=float(
            os.environ.get("OVERTURE_BBOX_MAX_LON") or bbox_raw.get("max_lon", 0)
        ),
        max_lat=float(
            os.environ.get("OVERTURE_BBOX_MAX_LAT") or bbox_raw.get("max_lat", 0)
        ),
    )

    data_release = (
        os.environ.get("OVERTURE_DATA_RELEASE") or raw.get("data_release") or ""
    )
    if not data_release:
        raise ValueError(
            "data_release not configured. "
            "Set OVERTURE_DATA_RELEASE or create overture.yaml."
        )

    schema_version = (
        os.environ.get("OVERTURE_SCHEMA_VERSION") or raw.get("schema_version") or ""
    )
    if not schema_version:
        raise ValueError(
            "schema_version not configured. "
            "Set OVERTURE_SCHEMA_VERSION or create overture.yaml."
        )

    themes = raw.get("themes", ["addresses", "places", "divisions", "transportation"])

    return Config(
        city=city,
        bbox=bbox,
        data_release=data_release,
        schema_version=schema_version,
        themes=themes,
    )
