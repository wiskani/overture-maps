"""Spatial query functions for transportation segments (streets)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_LIMIT = 10


def _validate_coords(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise ValueError(f"lat must be between -90 and 90, got: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"lon must be between -180 and 180, got: {lon}")


async def street_at_point(session: AsyncSession, lat: float, lon: float) -> dict:
    """Return the nearest street and its cross streets for the given point."""
    _validate_coords(lat, lon)

    result = await session.execute(
        text(
            """
            WITH nearest AS (
                SELECT id, names, "class", subtype, connectors, geom
                FROM reference.transportation_segments
                WHERE names IS NOT NULL
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                LIMIT 1
            ),
            connector_ids AS (
                SELECT DISTINCT
                    jsonb_array_elements(connectors)->>'connector_id' AS cid
                FROM nearest
                WHERE connectors IS NOT NULL
                  AND jsonb_typeof(connectors) = 'array'
            ),
            cross_streets AS (
                SELECT DISTINCT ts.id, ts.names, ts."class", ts.subtype, ts.geom
                FROM reference.transportation_segments ts
                JOIN connector_ids ci ON (
                    ts.connectors @> jsonb_build_array(
                        jsonb_build_object('connector_id', ci.cid)
                    )
                )
                WHERE ts.id != (SELECT id FROM nearest)
            )
            SELECT
                'street'       AS role,
                id,
                names,
                "class",
                subtype,
                ST_AsGeoJSON(geom)::json AS geometry
            FROM nearest
            UNION ALL
            SELECT
                'cross_street' AS role,
                id,
                names,
                "class",
                subtype,
                ST_AsGeoJSON(geom)::json AS geometry
            FROM cross_streets
            """
        ),
        {"lat": lat, "lon": lon},
    )

    rows = result.mappings().all()
    main = next((dict(r) for r in rows if r["role"] == "street"), None)
    crosses = [dict(r) for r in rows if r["role"] == "cross_street"]

    return {
        "street": {k: v for k, v in main.items() if k != "role"} if main else None,
        "cross_streets": [{k: v for k, v in r.items() if k != "role"} for r in crosses],
    }


async def streets_near_place(
    session: AsyncSession, lat: float, lon: float, limit: int = _LIMIT
) -> list[dict]:
    """Return the nearest streets to the given point."""
    _validate_coords(lat, lon)
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got: {limit!r}")

    result = await session.execute(
        text(
            """
            SELECT
                id, version, subtype, "class", subclass, names,
                ST_AsGeoJSON(geom)::json AS geometry,
                ST_Distance(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_meters
            FROM reference.transportation_segments
            ORDER BY ST_Distance(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            )
            LIMIT :limit
            """
        ),
        {"lat": lat, "lon": lon, "limit": limit},
    )
    return [dict(row) for row in result.mappings()]


async def search_streets(
    session: AsyncSession, q: str, limit: int = _LIMIT
) -> list[dict]:
    """Return streets whose name matches the given string."""
    if not q or not q.strip():
        raise ValueError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got: {limit!r}")

    result = await session.execute(
        text(
            """
            SELECT
                id, version, subtype, "class", subclass, names,
                ST_AsGeoJSON(geom)::json AS geometry
            FROM reference.transportation_segments
            WHERE names->>'primary' ILIKE :pattern
            LIMIT :limit
            """
        ),
        {"pattern": f"%{q}%", "limit": limit},
    )
    return [dict(row) for row in result.mappings()]
