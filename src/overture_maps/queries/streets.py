"""Spatial query functions for transportation segments (streets)."""

from __future__ import annotations

from geoalchemy2 import Geography
from sqlalchemy import JSON, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import TransportationSegment

_LIMIT = 10


def _validate_coords(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise ValueError(f"lat must be between -90 and 90, got: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"lon must be between -180 and 180, got: {lon}")


async def street_at_point(session: AsyncSession, lat: float, lon: float) -> dict:
    """Return the nearest street and its cross streets for the given point."""
    _validate_coords(lat, lon)

    # Uses text() because the CTE with jsonb_array_elements (set-returning function)
    # and UNION ALL does not map cleanly to SQLAlchemy ORM.
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

    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    geog = Geography(srid=4326)
    distance = func.ST_Distance(
        cast(TransportationSegment.geom, geog),
        cast(point, geog),
    )

    stmt = (
        select(
            TransportationSegment.id,
            TransportationSegment.version,
            TransportationSegment.subtype,
            TransportationSegment.road_class.label("class"),
            TransportationSegment.subclass,
            TransportationSegment.names,
            func.ST_AsGeoJSON(TransportationSegment.geom).cast(JSON).label("geometry"),
            distance.label("distance_meters"),
        )
        .order_by(distance)
        .limit(limit)
    )

    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings()]


async def search_streets(
    session: AsyncSession, q: str, limit: int = _LIMIT
) -> list[dict]:
    """Return streets whose name matches the given string."""
    if not q or not q.strip():
        raise ValueError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got: {limit!r}")

    stmt = (
        select(
            TransportationSegment.id,
            TransportationSegment.version,
            TransportationSegment.subtype,
            TransportationSegment.road_class.label("class"),
            TransportationSegment.subclass,
            TransportationSegment.names,
            func.ST_AsGeoJSON(TransportationSegment.geom).cast(JSON).label("geometry"),
        )
        .where(TransportationSegment.names["primary"].astext.ilike(f"%{q}%"))
        .limit(limit)
    )

    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings()]
