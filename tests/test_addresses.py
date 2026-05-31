"""Tests for nearby_addresses()."""

from __future__ import annotations

import pytest

from overture_maps import NearbyAddressResult, OvertureAddress
from overture_maps.exceptions import OvertureValidationError
from overture_maps.queries.addresses import nearby_addresses
from tests.conftest import CBBA_LAT, CBBA_LON, SF_LAT, SF_LON


@pytest.mark.asyncio
async def test_sf_returns_list(session):
    result = await nearby_addresses(session, SF_LAT, SF_LON)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_sf_returns_addresses(session):
    result = await nearby_addresses(session, SF_LAT, SF_LON)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_sf_result_type(session):
    results = await nearby_addresses(session, SF_LAT, SF_LON, limit=3)
    for r in results:
        assert isinstance(r, NearbyAddressResult)
        assert isinstance(r.address, OvertureAddress)
        assert isinstance(r.distance_meters, float)


@pytest.mark.asyncio
async def test_sf_result_has_id_and_geometry(session):
    results = await nearby_addresses(session, SF_LAT, SF_LON, limit=3)
    for r in results:
        assert r.address.id is not None
        assert r.address.geometry is not None


@pytest.mark.asyncio
async def test_sf_ordered_by_distance(session):
    results = await nearby_addresses(session, SF_LAT, SF_LON, limit=5)
    distances = [r.distance_meters for r in results]
    assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_empty_table_returns_empty_list(session):
    from sqlalchemy import text
    count = (await session.execute(text("SELECT COUNT(*) FROM reference.addresses"))).scalar()
    result = await nearby_addresses(session, CBBA_LAT, CBBA_LON)
    if count == 0:
        assert result == []
    else:
        assert isinstance(result, list)


@pytest.mark.asyncio
async def test_limit_is_respected(session):
    results = await nearby_addresses(session, SF_LAT, SF_LON, limit=2)
    assert len(results) <= 2


# --- OvertureValidationError cases ---

@pytest.mark.asyncio
async def test_invalid_lat_too_high_raises(session):
    with pytest.raises(OvertureValidationError, match="lat"):
        await nearby_addresses(session, 91.0, SF_LON)


@pytest.mark.asyncio
async def test_invalid_lat_too_low_raises(session):
    with pytest.raises(OvertureValidationError, match="lat"):
        await nearby_addresses(session, -91.0, SF_LON)


@pytest.mark.asyncio
async def test_invalid_lon_too_high_raises(session):
    with pytest.raises(OvertureValidationError, match="lon"):
        await nearby_addresses(session, SF_LAT, 181.0)


@pytest.mark.asyncio
async def test_invalid_lon_too_low_raises(session):
    with pytest.raises(OvertureValidationError, match="lon"):
        await nearby_addresses(session, SF_LAT, -181.0)


@pytest.mark.asyncio
async def test_invalid_limit_raises(session):
    with pytest.raises(OvertureValidationError, match="limit"):
        await nearby_addresses(session, SF_LAT, SF_LON, limit=0)
