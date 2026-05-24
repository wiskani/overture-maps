"""Spatial query functions for addresses."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_LIMIT = 10


def _validate_coords(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise ValueError(f"lat must be between -90 and 90, got: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"lon must be between -180 and 180, got: {lon}")


async def nearby_addresses(
    session: AsyncSession, lat: float, lon: float, limit: int = _LIMIT
) -> list[dict]:
    """Return the nearest addresses to the given point.

    Returns an empty list if the theme has no data for the configured bbox.
    """
    _validate_coords(lat, lon)
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got: {limit!r}")

    result = await session.execute(
        text(
            """
            SELECT
                id, version, country, number, postal_city, postcode, street, unit,
                address_levels,
                ST_AsGeoJSON(geom)::json AS geometry,
                ST_Distance(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_meters
            FROM reference.addresses
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT :limit
            """
        ),
        {"lat": lat, "lon": lon, "limit": limit},
    )
    return [dict(row) for row in result.mappings()]
