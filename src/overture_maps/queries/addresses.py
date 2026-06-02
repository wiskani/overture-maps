"""Spatial query functions for addresses."""

from __future__ import annotations

from geoalchemy2 import Geography
from overture.schema.addresses.address import Address as OvertureAddress
from sqlalchemy import JSON, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import OvertureValidationError
from ..models import Address
from ..results import NearbyAddressResult
from ._utils import DEFAULT_LIMIT, _parse_feature, handle_db_errors, validate_coords

_ADDRESS_COLS = (
    Address.id,
    Address.version,
    Address.country,
    Address.number,
    Address.postal_city,
    Address.postcode,
    Address.street,
    Address.unit,
    Address.address_levels,
    Address.bbox,
    Address.sources,
    func.ST_AsGeoJSON(Address.geom).cast(JSON).label("geometry"),
)

_LIMIT = DEFAULT_LIMIT


@handle_db_errors
async def nearby_addresses(
    session: AsyncSession, lat: float, lon: float, limit: int = _LIMIT
) -> list[NearbyAddressResult]:
    """Return the nearest addresses to the given point.

    Returns an empty list if the theme has no data for the configured bbox.
    """
    validate_coords(lat, lon)
    if not isinstance(limit, int) or limit < 1:
        raise OvertureValidationError(
            f"limit must be a positive integer, got: {limit!r}"
        )

    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    geog = Geography(srid=4326)

    stmt = (
        select(
            *_ADDRESS_COLS,
            func.ST_Distance(
                cast(Address.geom, geog),
                cast(point, geog),
            ).label("distance_meters"),
        )
        .order_by(Address.geom.op("<->")(point))
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = [dict(row) for row in result.mappings()]

    out: list[NearbyAddressResult] = []
    for row in rows:
        address = _parse_feature(OvertureAddress, row, "addresses", "address")
        if address is not None:
            out.append(
                NearbyAddressResult(
                    address=address, distance_meters=row["distance_meters"]
                )
            )
    return out


@handle_db_errors
async def get_address_by_id(
    session: AsyncSession, address_id: str
) -> OvertureAddress | None:
    """Return a single OvertureAddress by its Overture id, or None if not found."""
    stmt = select(*_ADDRESS_COLS).where(Address.id == address_id)
    result = await session.execute(stmt)
    row = result.mappings().fetchone()
    if row is None:
        return None
    return _parse_feature(OvertureAddress, dict(row), "addresses", "address")
