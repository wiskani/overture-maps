"""Place spatial query functions."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_LIMIT = 10


def _validate_coords(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise ValueError(f"lat must be between -90 and 90, got {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"lon must be between -180 and 180, got {lon}")


async def nearby_places(
    session: AsyncSession, lat: float, lon: float, limit: int = _LIMIT
) -> list[dict]:
    """Return the nearest points of interest to the given point."""
    _validate_coords(lat, lon)
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got {limit!r}")

    result = await session.execute(
        text("""
            SELECT
                id, name, category,
                ST_AsGeoJSON(geom)::json AS geometry,
                ST_Distance(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_meters,
                raw
            FROM reference.places
            WHERE name IS NOT NULL
            ORDER BY ST_Distance(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            )
            LIMIT :limit
        """),
        {"lat": lat, "lon": lon, "limit": limit},
    )
    return [dict(row) for row in result.mappings()]


async def search_places(
    session: AsyncSession, q: str, limit: int = _LIMIT
) -> list[dict]:
    """Return points of interest whose name matches the given string."""
    if not q or not q.strip():
        raise ValueError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got {limit!r}")

    result = await session.execute(
        text("""
            SELECT
                id, name, category,
                ST_AsGeoJSON(geom)::json AS geometry,
                raw
            FROM reference.places
            WHERE name ILIKE :pattern
            LIMIT :limit
        """),
        {"pattern": f"%{q}%", "limit": limit},
    )
    return [dict(row) for row in result.mappings()]
