"""Unit tests for OvertureClient bbox coverage check.

These tests do not require a running database — OvertureCoverageError is raised
before any DB connection is attempted.
"""

from __future__ import annotations

import pytest

from overture_maps import OvertureClient, OvertureCoverageError


@pytest.fixture(scope="session", autouse=True)
def loaded_db():
    """Override conftest loaded_db — no database needed for these unit tests."""


_CBBA_BBOX = dict(
    bbox_min_lon=-66.175,
    bbox_min_lat=-17.405,
    bbox_max_lon=-66.145,
    bbox_max_lat=-17.375,
)
_FAKE_DSN = "postgresql+asyncpg://user:pw@localhost:9999/nonexistent"

_INSIDE_LAT, _INSIDE_LON = -17.390, -66.157   # Plaza 14 de Septiembre
_OUTSIDE_LAT, _OUTSIDE_LON = -17.367, -66.234  # Quillacollo — west of bbox


@pytest.fixture
def client_with_bbox() -> OvertureClient:
    return OvertureClient(dsn=_FAKE_DSN, **_CBBA_BBOX)


@pytest.fixture
def client_no_bbox() -> OvertureClient:
    return OvertureClient(dsn=_FAKE_DSN)


# ── _check_coverage directly ──────────────────────────────────────────


def test_check_coverage_raises_when_outside(client_with_bbox):
    with pytest.raises(OvertureCoverageError, match="outside the configured coverage bbox"):
        client_with_bbox._check_coverage(_OUTSIDE_LAT, _OUTSIDE_LON)


def test_check_coverage_does_not_raise_when_inside(client_with_bbox):
    client_with_bbox._check_coverage(_INSIDE_LAT, _INSIDE_LON)


def test_check_coverage_does_not_raise_without_bbox(client_no_bbox):
    client_no_bbox._check_coverage(_OUTSIDE_LAT, _OUTSIDE_LON)


def test_check_coverage_error_message_includes_coords(client_with_bbox):
    with pytest.raises(OvertureCoverageError) as exc_info:
        client_with_bbox._check_coverage(_OUTSIDE_LAT, _OUTSIDE_LON)
    msg = str(exc_info.value)
    assert str(_OUTSIDE_LAT) in msg
    assert str(_OUTSIDE_LON) in msg


def test_check_coverage_bbox_boundary_inside(client_with_bbox):
    client_with_bbox._check_coverage(-17.405, -66.175)  # min corner exact
    client_with_bbox._check_coverage(-17.375, -66.145)  # max corner exact


# ── coverage check fires before DB in each method ────────────────────


@pytest.mark.asyncio
async def test_streets_near_place_raises_coverage_before_db(client_with_bbox):
    with pytest.raises(OvertureCoverageError):
        await client_with_bbox.streets_near_place(_OUTSIDE_LAT, _OUTSIDE_LON)


@pytest.mark.asyncio
async def test_street_at_point_raises_coverage_before_db(client_with_bbox):
    with pytest.raises(OvertureCoverageError):
        await client_with_bbox.street_at_point(_OUTSIDE_LAT, _OUTSIDE_LON)


@pytest.mark.asyncio
async def test_nearby_addresses_raises_coverage_before_db(client_with_bbox):
    with pytest.raises(OvertureCoverageError):
        await client_with_bbox.nearby_addresses(_OUTSIDE_LAT, _OUTSIDE_LON)


@pytest.mark.asyncio
async def test_nearby_places_raises_coverage_before_db(client_with_bbox):
    with pytest.raises(OvertureCoverageError):
        await client_with_bbox.nearby_places(_OUTSIDE_LAT, _OUTSIDE_LON)
