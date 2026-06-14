"""Session fixtures for overture-maps integration tests.

Downloads real Overture Maps data for two small bboxes:
  - Cochabamba (~3 km² around Plaza 14 de Septiembre) — has places, divisions,
    transportation, but NO addresses. Used to test the empty-list case.
  - San Francisco (~3 km² around Union Square) — has all themes including addresses.

Both datasets are loaded into the same overture_db_test database so they coexist
(bboxes don't overlap). Parquets are cached in tests/data/ — subsequent runs skip
the download and complete in seconds.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from overture_maps.config import BBox, Config
from overture_maps.load import load

_TEST_DB_URL_SYNC = os.environ.get(
    "OVERTURE_TEST_DB_SYNC_URL",
    "postgresql://overture:overture@localhost:7003/overture",
)
_TEST_DB_URL_ASYNC = os.environ.get(
    "OVERTURE_TEST_DB_ASYNC_URL",
    "postgresql+asyncpg://overture:overture@localhost:7003/overture",
)

_DATA_DIR = Path(__file__).parent / "data"

_COCHABAMBA_BBOX = "-66.175,-17.405,-66.145,-17.375"
_SF_BBOX = "-122.42,37.77,-122.39,37.80"

_DOWNLOADS = [
    (_COCHABAMBA_BBOX, "cbba", [
        ("place",        "places.parquet"),
        ("segment",      "segments.parquet"),
        ("address",      "addresses.parquet"),
        ("division_area","divisions.parquet"),
        ("connector",    "connectors.parquet"),
    ]),
    (_SF_BBOX, "sf", [
        ("place",        "places.parquet"),
        ("segment",      "segments.parquet"),
        ("address",      "addresses.parquet"),
        ("division_area","divisions.parquet"),
        ("connector",    "connectors.parquet"),
    ]),
]

# Config used for health() tests (city-agnostic, just needs valid bbox)
COCHABAMBA_CONFIG = Config(
    city="cochabamba",
    bbox=BBox(min_lon=-66.175, min_lat=-17.405, max_lon=-66.145, max_lat=-17.375),
    data_release="2024-11-13.0",
    schema_version="1.0.0",
    themes=["addresses", "places", "divisions", "transportation"],
)

SF_CONFIG = Config(
    city="san_francisco",
    bbox=BBox(min_lon=-122.42, min_lat=37.77, max_lon=-122.39, max_lat=37.80),
    data_release="2024-11-13.0",
    schema_version="1.0.0",
    themes=["addresses", "places", "divisions", "transportation"],
)

# Coordinates for queries
CBBA_LAT, CBBA_LON = -17.3895, -66.1568   # Plaza 14 de Septiembre
SF_LAT, SF_LON = 37.788, -122.407          # Union Square


def _download_if_missing() -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    for bbox_str, prefix, downloads in _DOWNLOADS:
        city_dir = _DATA_DIR / prefix
        city_dir.mkdir(exist_ok=True)
        for type_, fname in downloads:
            out = city_dir / fname
            if out.exists():
                continue
            try:
                subprocess.run(
                    [
                        "overturemaps", "download",
                        f"--bbox={bbox_str}",
                        f"--type={type_}",
                        "-f", "geoparquet",
                        "-o", str(out),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.strip() if exc.stderr else "(no stderr)"
                pytest.fail(
                    f"Failed to download Overture data — type='{type_}', bbox={bbox_str}\n"
                    f"stderr: {stderr}\n\n"
                    "The Overture Maps service may be unavailable.\n"
                    "Check status at: https://docs.overturemaps.org/getting-data/overturemaps-py/"
                )


@pytest.fixture(scope="session", autouse=True)
def loaded_db():
    """Download both city datasets and load them into overture_db_test."""
    _download_if_missing()
    load(_DATA_DIR / "cbba", _TEST_DB_URL_SYNC, COCHABAMBA_CONFIG, init_schema=True)
    load(_DATA_DIR / "sf", _TEST_DB_URL_SYNC, SF_CONFIG, init_schema=False)


@pytest.fixture(scope="session")
def session_factory():
    engine = create_async_engine(_TEST_DB_URL_ASYNC, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def session() -> AsyncSession:
    # NullPool: connections are not retained between operations, no dispose needed.
    engine = create_async_engine(_TEST_DB_URL_ASYNC, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
