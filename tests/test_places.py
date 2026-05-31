"""Tests for nearby_places() and search_places()."""

from __future__ import annotations

import pytest

from overture_maps import NearbyPlaceResult, OverturePlace
from overture_maps.exceptions import OvertureValidationError
from overture_maps.queries.places import nearby_places, search_places
from tests.conftest import CBBA_LAT, CBBA_LON, SF_LAT, SF_LON


def _primary_name(place: OverturePlace) -> str:
    """Extract the primary name from a Place regardless of whether names is a
    Pydantic model instance (after full validation) or a raw dict (after
    model_construct fallback due to schema drift)."""
    names = place.names
    if names is None:
        return ""
    if isinstance(names, dict):
        return names.get("primary") or ""
    return getattr(names, "primary", None) or ""


# --- nearby_places ---

@pytest.mark.asyncio
async def test_nearby_places_sf_returns_results(session):
    results = await nearby_places(session, SF_LAT, SF_LON)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_nearby_places_cbba_returns_results(session):
    results = await nearby_places(session, CBBA_LAT, CBBA_LON)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_nearby_places_result_type(session):
    results = await nearby_places(session, SF_LAT, SF_LON, limit=3)
    for r in results:
        assert isinstance(r, NearbyPlaceResult)
        assert isinstance(r.place, OverturePlace)
        assert isinstance(r.distance_meters, float)


@pytest.mark.asyncio
async def test_nearby_places_has_id_and_geometry(session):
    results = await nearby_places(session, SF_LAT, SF_LON, limit=3)
    for r in results:
        assert r.place.id is not None
        assert r.place.geometry is not None


@pytest.mark.asyncio
async def test_nearby_places_ordered_by_distance(session):
    results = await nearby_places(session, SF_LAT, SF_LON, limit=5)
    distances = [r.distance_meters for r in results]
    assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_nearby_places_limit_respected(session):
    results = await nearby_places(session, SF_LAT, SF_LON, limit=2)
    assert len(results) <= 2


# --- search_places ---

@pytest.mark.asyncio
async def test_search_places_returns_results(session):
    results = await search_places(session, "hotel")
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_places_result_type(session):
    results = await search_places(session, "hotel")
    for r in results:
        assert isinstance(r, OverturePlace)


@pytest.mark.asyncio
async def test_search_places_matches_query(session):
    results = await search_places(session, "hotel")
    for r in results:
        assert "hotel" in _primary_name(r).lower()


@pytest.mark.asyncio
async def test_search_places_no_match_returns_empty(session):
    results = await search_places(session, "xyzxyzxyz999irrelevant")
    assert results == []


@pytest.mark.asyncio
async def test_search_places_has_geometry(session):
    results = await search_places(session, "hotel")
    for r in results:
        assert r.geometry is not None


@pytest.mark.asyncio
async def test_search_places_limit_respected(session):
    results = await search_places(session, "a", limit=2)
    assert len(results) <= 2


# --- OvertureValidationError cases ---

@pytest.mark.asyncio
async def test_nearby_places_invalid_lat_raises(session):
    with pytest.raises(OvertureValidationError, match="lat"):
        await nearby_places(session, 95.0, SF_LON)


@pytest.mark.asyncio
async def test_nearby_places_invalid_lon_raises(session):
    with pytest.raises(OvertureValidationError, match="lon"):
        await nearby_places(session, SF_LAT, -200.0)


@pytest.mark.asyncio
async def test_search_places_empty_query_raises(session):
    with pytest.raises(OvertureValidationError, match="q"):
        await search_places(session, "")


@pytest.mark.asyncio
async def test_search_places_whitespace_query_raises(session):
    with pytest.raises(OvertureValidationError, match="q"):
        await search_places(session, "   ")
