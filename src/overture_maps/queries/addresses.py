"""Spatial query functions for addresses."""

from __future__ import annotations

from geoalchemy2 import Geography
from sqlalchemy import JSON, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Address
from ._utils import DEFAULT_LIMIT, validate_coords

_LIMIT = DEFAULT_LIMIT


async def nearby_addresses(
    session: AsyncSession, lat: float, lon: float, limit: int = _LIMIT
) -> list[dict]:
    """Return the nearest addresses to the given point.

    Returns an empty list if the theme has no data for the configured bbox.
    """
    validate_coords(lat, lon)
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got: {limit!r}")

    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    geog = Geography(srid=4326)

    stmt = (
        select(
            Address.id,
            Address.version,
            Address.country,
            Address.number,
            Address.postal_city,
            Address.postcode,
            Address.street,
            Address.unit,
            Address.address_levels,
            func.ST_AsGeoJSON(Address.geom).cast(JSON).label("geometry"),
            func.ST_Distance(
                cast(Address.geom, geog),
                cast(point, geog),
            ).label("distance_meters"),
        )
        .order_by(Address.geom.op("<->")(point))
        .limit(limit)
    )

    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings()]
