"""Spatial query functions for transportation segments (streets)."""

from __future__ import annotations

from geoalchemy2 import Geography
from overture.schema.transportation.segment.models import Segment as OvertureSegment
from sqlalchemy import JSON, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import OvertureValidationError
from ..models import TransportationSegment
from ..results import NearbySegmentResult, StreetAtPointResult
from ._utils import DEFAULT_LIMIT, _parse_feature, handle_db_errors, validate_coords

_LIMIT = DEFAULT_LIMIT


def _segment(row: dict) -> OvertureSegment | None:
    return _parse_feature(OvertureSegment, row, "transportation", "segment")


@handle_db_errors
async def street_at_point(
    session: AsyncSession, lat: float, lon: float
) -> StreetAtPointResult:
    """Return the nearest street and its cross streets for the given point."""
    validate_coords(lat, lon)

    # Uses text() because the CTE with jsonb_array_elements (set-returning function)
    # and UNION ALL does not map cleanly to SQLAlchemy ORM.
    result = await session.execute(
        text(
            """
            WITH nearest AS (
                SELECT id, version, names, "class", subtype, connectors, geom
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
                SELECT DISTINCT ts.id, ts.version, ts.names,
                    ts."class", ts.subtype, ts.geom
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
                version,
                names,
                "class",
                subtype,
                ST_AsGeoJSON(geom)::json AS geometry
            FROM nearest
            UNION ALL
            SELECT
                'cross_street' AS role,
                id,
                version,
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
    main_rows = [dict(r) for r in rows if r["role"] == "street"]
    cross_rows = [dict(r) for r in rows if r["role"] == "cross_street"]

    # Remove the role key before passing to the model validator
    for r in main_rows + cross_rows:
        r.pop("role", None)

    street = _segment(main_rows[0]) if main_rows else None
    cross_streets = [s for r in cross_rows if (s := _segment(r)) is not None]

    return StreetAtPointResult(street=street, cross_streets=cross_streets)


@handle_db_errors
async def streets_near_place(
    session: AsyncSession, lat: float, lon: float, limit: int = _LIMIT
) -> list[NearbySegmentResult]:
    """Return the nearest streets to the given point."""
    validate_coords(lat, lon)
    if not isinstance(limit, int) or limit < 1:
        raise OvertureValidationError(
            f"limit must be a positive integer, got: {limit!r}"
        )

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
            TransportationSegment.bbox,
            TransportationSegment.sources,
            TransportationSegment.names,
            TransportationSegment.connectors,
            func.ST_AsGeoJSON(TransportationSegment.geom).cast(JSON).label("geometry"),
            distance.label("distance_meters"),
        )
        .order_by(distance)
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = [dict(row) for row in result.mappings()]

    out: list[NearbySegmentResult] = []
    for row in rows:
        segment = _segment(row)
        if segment is not None:
            out.append(
                NearbySegmentResult(
                    segment=segment, distance_meters=row["distance_meters"]
                )
            )
    return out


@handle_db_errors
async def search_streets(
    session: AsyncSession, q: str, limit: int = _LIMIT
) -> list[OvertureSegment]:
    """Return streets whose name matches the given string."""
    if not q or not q.strip():
        raise OvertureValidationError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise OvertureValidationError(
            f"limit must be a positive integer, got: {limit!r}"
        )

    stmt = (
        select(
            TransportationSegment.id,
            TransportationSegment.version,
            TransportationSegment.subtype,
            TransportationSegment.road_class.label("class"),
            TransportationSegment.subclass,
            TransportationSegment.bbox,
            TransportationSegment.sources,
            TransportationSegment.names,
            TransportationSegment.connectors,
            func.ST_AsGeoJSON(TransportationSegment.geom).cast(JSON).label("geometry"),
        )
        .where(TransportationSegment.names["primary"].astext.ilike(f"%{q}%"))
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = [dict(row) for row in result.mappings()]

    return [seg for row in rows if (seg := _segment(row)) is not None]
