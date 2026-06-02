"""Tests for nearby_addresses() and get_address_by_id()."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from overture_maps import NearbyAddressResult, OvertureAddress
from overture_maps.exceptions import OvertureConnectionError, OvertureValidationError
from overture_maps.queries.addresses import get_address_by_id, nearby_addresses
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


# --- get_address_by_id ---

@pytest.fixture(scope="module")
async def any_sf_address_id(session_factory):
    """Return a real address id from the SF dataset."""
    async with session_factory() as s:
        result = await s.execute(
            text("SELECT id FROM reference.addresses LIMIT 1")
        )
        row = result.fetchone()
        assert row is not None, "No addresses loaded — cannot run test"
        return row[0]


@pytest.mark.asyncio
async def test_get_address_by_id_existing(session, any_sf_address_id):
    result = await get_address_by_id(session, any_sf_address_id)
    assert isinstance(result, OvertureAddress)
    assert result.id == any_sf_address_id


@pytest.mark.asyncio
async def test_get_address_by_id_unknown_returns_none(session):
    result = await get_address_by_id(session, "nonexistent-address-id-xyz")
    assert result is None


@pytest.mark.asyncio
async def test_get_address_by_id_has_geometry(session, any_sf_address_id):
    result = await get_address_by_id(session, any_sf_address_id)
    assert result is not None
    assert result.geometry is not None


@pytest.mark.asyncio
async def test_get_address_by_id_db_error_raises_connection_error():
    from unittest.mock import AsyncMock
    from sqlalchemy.exc import OperationalError

    mock_session = AsyncMock()
    mock_session.execute.side_effect = OperationalError("connection refused", None, None)

    with pytest.raises(OvertureConnectionError):
        await get_address_by_id(mock_session, "some-id")
