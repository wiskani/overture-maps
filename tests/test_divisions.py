"""Tests for search_divisions(), streets_in_division(), and divisions_containing_point()."""

from __future__ import annotations

import pytest
from overture.schema.transportation.segment.models import RoadSegment, RailSegment, WaterSegment
from sqlalchemy import text

from overture_maps import OvertureDivisionArea
from overture_maps.exceptions import OvertureConnectionError, OvertureNotFoundError, OvertureValidationError
from overture_maps.queries.divisions import divisions_containing_point, search_divisions, streets_in_division
from tests.conftest import CBBA_LAT, CBBA_LON, SF_LAT, SF_LON  # noqa: F401

_SEGMENT_TYPES = (RoadSegment, RailSegment, WaterSegment)


@pytest.fixture(scope="module")
async def any_division_id(session_factory):
    """Return a real division_id from the test database."""
    async with session_factory() as s:
        result = await s.execute(
            text("SELECT id FROM reference.divisions LIMIT 1")
        )
        row = result.fetchone()
        assert row is not None, "No divisions loaded — cannot run test"
        return row[0]


# --- search_divisions ---

@pytest.mark.asyncio
async def test_search_divisions_returns_list(session):
    results = await search_divisions(session, "San")
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_divisions_sf_returns_results(session):
    results = await search_divisions(session, "San Francisco")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_divisions_result_type(session):
    results = await search_divisions(session, "San Francisco")
    for r in results:
        assert isinstance(r, OvertureDivisionArea)
        assert r.id is not None
        assert r.names is not None


@pytest.mark.asyncio
async def test_search_divisions_geometry_is_polygon(session):
    results = await search_divisions(session, "San Francisco")
    for r in results:
        geom = r.geometry
        # geometry is a Pydantic/Shapely object after full validation or a raw
        # GeoJSON dict after model_construct fallback (schema drift).
        geom_type = geom.get("type") if isinstance(geom, dict) else getattr(geom, "geom_type", None)
        assert geom_type in ("Polygon", "MultiPolygon")


@pytest.mark.asyncio
async def test_search_divisions_no_match_returns_empty(session):
    results = await search_divisions(session, "xyzxyzxyz999irrelevant")
    assert results == []


@pytest.mark.asyncio
async def test_search_divisions_cochabamba_returns_results(session):
    results = await search_divisions(session, "Cochabamba")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_divisions_returns_most_granular(session):
    results = await search_divisions(session, "San Francisco")
    types = {r.subtype for r in results if r.subtype}
    assert len(types) <= 1


@pytest.mark.asyncio
async def test_search_divisions_empty_query_raises(session):
    with pytest.raises(OvertureValidationError, match="q"):
        await search_divisions(session, "")


@pytest.mark.asyncio
async def test_search_divisions_limit_respected(session):
    results = await search_divisions(session, "a", limit=2)
    assert len(results) <= 2


# --- streets_in_division ---

@pytest.mark.asyncio
async def test_streets_in_division_returns_list(session, any_division_id):
    results = await streets_in_division(session, any_division_id, "a")
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_streets_in_division_result_type(session, any_division_id):
    results = await streets_in_division(session, any_division_id, "a")
    for r in results:
        assert isinstance(r, _SEGMENT_TYPES)


@pytest.mark.asyncio
async def test_streets_in_division_results_match_query(session, any_division_id):
    results = await streets_in_division(session, any_division_id, "st")
    for r in results:
        names = r.names
        if names is None:
            continue
        primary = names.get("primary") if isinstance(names, dict) else getattr(names, "primary", None)
        if primary:
            assert "st" in primary.lower()


@pytest.mark.asyncio
async def test_streets_in_division_has_geometry(session, any_division_id):
    results = await streets_in_division(session, any_division_id, "a")
    for r in results:
        assert r.geometry is not None


@pytest.mark.asyncio
async def test_streets_in_division_limit_respected(session, any_division_id):
    results = await streets_in_division(session, any_division_id, "a", limit=2)
    assert len(results) <= 2


@pytest.mark.asyncio
async def test_streets_in_division_nonexistent_raises(session):
    with pytest.raises(OvertureNotFoundError, match="division_id"):
        await streets_in_division(session, "nonexistent-id-xyz", "st")


@pytest.mark.asyncio
async def test_streets_in_division_empty_division_id_raises(session):
    with pytest.raises(OvertureValidationError, match="division_id"):
        await streets_in_division(session, "", "st")


@pytest.mark.asyncio
async def test_streets_in_division_empty_query_raises(session):
    with pytest.raises(OvertureValidationError, match="q"):
        await streets_in_division(session, "some-id", "")


# --- divisions_containing_point ---

@pytest.mark.asyncio
async def test_divisions_containing_point_cbba_returns_results(session):
    results = await divisions_containing_point(session, CBBA_LAT, CBBA_LON)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_divisions_containing_point_sf_returns_results(session):
    results = await divisions_containing_point(session, SF_LAT, SF_LON)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_divisions_containing_point_result_type(session):
    results = await divisions_containing_point(session, CBBA_LAT, CBBA_LON)
    for r in results:
        assert isinstance(r, OvertureDivisionArea)
        assert r.id is not None


@pytest.mark.asyncio
async def test_divisions_containing_point_outside_returns_empty(session):
    # Point in the middle of the Pacific Ocean — outside all loaded divisions
    results = await divisions_containing_point(session, 0.0, -150.0)
    assert results == []


@pytest.mark.asyncio
async def test_divisions_containing_point_ordered_by_admin_level(session):
    results = await divisions_containing_point(session, CBBA_LAT, CBBA_LON)
    levels = [r.admin_level for r in results if r.admin_level is not None]
    assert levels == sorted(levels, reverse=True)


@pytest.mark.asyncio
async def test_divisions_containing_point_invalid_lat_raises(session):
    with pytest.raises(OvertureValidationError, match="lat"):
        await divisions_containing_point(session, 95.0, CBBA_LON)


@pytest.mark.asyncio
async def test_divisions_containing_point_invalid_lon_raises(session):
    with pytest.raises(OvertureValidationError, match="lon"):
        await divisions_containing_point(session, CBBA_LAT, 185.0)


@pytest.mark.asyncio
async def test_divisions_containing_point_db_error_raises_connection_error():
    from unittest.mock import AsyncMock
    from sqlalchemy.exc import OperationalError

    mock_session = AsyncMock()
    mock_session.execute.side_effect = OperationalError("connection refused", None, None)

    with pytest.raises(OvertureConnectionError):
        await divisions_containing_point(mock_session, CBBA_LAT, CBBA_LON)
