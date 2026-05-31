"""Tests for street_at_point(), streets_near_place(), search_streets()."""

from __future__ import annotations

import pytest
from overture.schema.transportation.segment.models import RoadSegment, RailSegment, WaterSegment

from overture_maps import NearbySegmentResult, StreetAtPointResult
from overture_maps.exceptions import OvertureValidationError
from overture_maps.queries.streets import search_streets, street_at_point, streets_near_place
from tests.conftest import CBBA_LAT, CBBA_LON, SF_LAT, SF_LON

_SEGMENT_TYPES = (RoadSegment, RailSegment, WaterSegment)


def _primary_name(segment) -> str:
    """Extract the primary street name regardless of whether names is a Pydantic
    model or a raw dict (schema drift fallback)."""
    names = segment.names
    if names is None:
        return ""
    if isinstance(names, dict):
        return names.get("primary") or ""
    return getattr(names, "primary", None) or ""


# --- street_at_point ---

@pytest.mark.asyncio
async def test_street_at_point_returns_result_type(session):
    result = await street_at_point(session, SF_LAT, SF_LON)
    assert isinstance(result, StreetAtPointResult)
    assert isinstance(result.cross_streets, list)


@pytest.mark.asyncio
async def test_street_at_point_street_has_name(session):
    result = await street_at_point(session, SF_LAT, SF_LON)
    assert result.street is not None
    assert result.street.names is not None


@pytest.mark.asyncio
async def test_street_at_point_street_has_geometry(session):
    result = await street_at_point(session, SF_LAT, SF_LON)
    assert result.street is not None
    assert result.street.geometry is not None


@pytest.mark.asyncio
async def test_street_at_point_cross_streets_are_segments(session):
    result = await street_at_point(session, SF_LAT, SF_LON)
    for seg in result.cross_streets:
        assert isinstance(seg, _SEGMENT_TYPES)


@pytest.mark.asyncio
async def test_street_at_point_cbba_returns_street(session):
    result = await street_at_point(session, CBBA_LAT, CBBA_LON)
    assert result.street is not None


@pytest.mark.asyncio
async def test_street_at_point_invalid_lat_raises(session):
    with pytest.raises(OvertureValidationError, match="lat"):
        await street_at_point(session, 200.0, SF_LON)


@pytest.mark.asyncio
async def test_street_at_point_invalid_lon_raises(session):
    with pytest.raises(OvertureValidationError, match="lon"):
        await street_at_point(session, SF_LAT, 200.0)


# --- streets_near_place ---

@pytest.mark.asyncio
async def test_streets_near_place_returns_list(session):
    results = await streets_near_place(session, SF_LAT, SF_LON)
    assert isinstance(results, list)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_streets_near_place_result_type(session):
    results = await streets_near_place(session, SF_LAT, SF_LON, limit=3)
    for r in results:
        assert isinstance(r, NearbySegmentResult)
        assert isinstance(r.segment, _SEGMENT_TYPES)
        assert isinstance(r.distance_meters, float)


@pytest.mark.asyncio
async def test_streets_near_place_has_id_and_geometry(session):
    results = await streets_near_place(session, SF_LAT, SF_LON, limit=5)
    for r in results:
        assert r.segment.id is not None
        assert r.segment.geometry is not None


@pytest.mark.asyncio
async def test_streets_near_place_ordered_by_distance(session):
    results = await streets_near_place(session, SF_LAT, SF_LON, limit=5)
    distances = [r.distance_meters for r in results]
    assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_streets_near_place_cbba_returns_results(session):
    results = await streets_near_place(session, CBBA_LAT, CBBA_LON)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_streets_near_place_limit_respected(session):
    results = await streets_near_place(session, SF_LAT, SF_LON, limit=2)
    assert len(results) <= 2


@pytest.mark.asyncio
async def test_streets_near_place_invalid_lat_raises(session):
    with pytest.raises(OvertureValidationError, match="lat"):
        await streets_near_place(session, -95.0, SF_LON)


# --- search_streets ---

@pytest.mark.asyncio
async def test_search_streets_returns_list(session):
    results = await search_streets(session, "st")
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_streets_result_type(session):
    results = await search_streets(session, "st")
    for r in results:
        assert isinstance(r, _SEGMENT_TYPES)


@pytest.mark.asyncio
async def test_search_streets_results_match_query(session):
    results = await search_streets(session, "st")
    for r in results:
        primary = _primary_name(r)
        if primary:
            assert "st" in primary.lower()


@pytest.mark.asyncio
async def test_search_streets_has_geometry(session):
    results = await search_streets(session, "st")
    for r in results:
        assert r.geometry is not None


@pytest.mark.asyncio
async def test_search_streets_no_match_returns_empty(session):
    results = await search_streets(session, "xyzxyzxyz999")
    assert results == []


@pytest.mark.asyncio
async def test_search_streets_limit_respected(session):
    results = await search_streets(session, "a", limit=2)
    assert len(results) <= 2


@pytest.mark.asyncio
async def test_search_streets_empty_query_raises(session):
    with pytest.raises(OvertureValidationError, match="q"):
        await search_streets(session, "")
