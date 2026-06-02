"""Spatial query functions for divisions."""

from __future__ import annotations

from overture.schema.divisions.division_area import DivisionArea as OvertureDivisionArea
from overture.schema.transportation.segment.models import Segment as OvertureSegment
from sqlalchemy import JSON, func, nullslast, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import OvertureNotFoundError, OvertureValidationError
from ..models import Division, TransportationSegment
from ._utils import DEFAULT_LIMIT, _parse_feature, handle_db_errors, validate_coords

_LIMIT = DEFAULT_LIMIT

# DivisionSubtype hierarchy from most to least granular
# (derived from overture.schema.divisions._common.DivisionSubtype enum)
_DIVISION_SUBTYPE_HIERARCHY = [
    "microhood",
    "neighborhood",
    "macrohood",
    "borough",
    "locality",
    "localadmin",
    "county",
    "macrocounty",
    "region",
    "macroregion",
    "dependency",
    "country",
]

_DIVISION_COLS = (
    Division.id,
    Division.version,
    Division.subtype,
    Division.division_class.label("class"),
    Division.country,
    Division.region,
    Division.admin_level,
    Division.division_id,
    Division.is_land,
    Division.is_territorial,
    Division.bbox,
    Division.sources,
    Division.names,
    func.ST_AsGeoJSON(Division.geom).cast(JSON).label("geometry"),
)


def _division(row: dict) -> OvertureDivisionArea | None:
    return _parse_feature(OvertureDivisionArea, row, "divisions", "division_area")


@handle_db_errors
async def search_divisions(
    session: AsyncSession, q: str, limit: int = _LIMIT
) -> list[OvertureDivisionArea]:
    """Return the lowest-hierarchy division whose name matches the given string.

    Filters by the most granular subtype present in the loaded data.
    """
    if not q or not q.strip():
        raise OvertureValidationError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise OvertureValidationError(
            f"limit must be a positive integer, got: {limit!r}"
        )

    pattern = f"%{q}%"

    types_result = await session.execute(
        select(Division.subtype)
        .where(Division.subtype.isnot(None))
        .where(Division.names["primary"].astext.ilike(pattern))
        .distinct()
    )
    present_types = {row.subtype for row in types_result}

    most_granular: str | None = None
    for st in _DIVISION_SUBTYPE_HIERARCHY:
        if st in present_types:
            most_granular = st
            break

    if most_granular is None:
        stmt = (
            select(*_DIVISION_COLS)
            .where(Division.names["primary"].astext.ilike(pattern))
            .limit(limit)
        )
    else:
        stmt = (
            select(*_DIVISION_COLS)
            .where(Division.subtype == most_granular)
            .where(Division.names["primary"].astext.ilike(pattern))
            .limit(limit)
        )

    result = await session.execute(stmt)
    rows = [dict(row) for row in result.mappings()]

    return [div for row in rows if (div := _division(row)) is not None]


@handle_db_errors
async def streets_in_division(
    session: AsyncSession, division_id: str, q: str, limit: int = _LIMIT
) -> list[OvertureSegment]:
    """Return streets whose name matches q within the given division.

    Raises OvertureNotFoundError if division_id is not found.
    """
    if not division_id or not str(division_id).strip():
        raise OvertureValidationError("division_id must be a non-empty string")
    if not q or not q.strip():
        raise OvertureValidationError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise OvertureValidationError(
            f"limit must be a positive integer, got: {limit!r}"
        )

    exists = await session.execute(
        select(Division.id).where(Division.id == division_id).limit(1)
    )
    if exists.fetchone() is None:
        raise OvertureNotFoundError(f"division_id {division_id!r} not found")

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
        .join(
            Division,
            func.ST_Intersects(TransportationSegment.geom, Division.geom),
        )
        .where(Division.id == division_id)
        .where(TransportationSegment.names["primary"].astext.ilike(f"%{q}%"))
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = [dict(row) for row in result.mappings()]

    return [
        seg
        for row in rows
        if (seg := _parse_feature(OvertureSegment, row, "transportation", "segment"))
        is not None
    ]


@handle_db_errors
async def divisions_containing_point(
    session: AsyncSession, lat: float, lon: float
) -> list[OvertureDivisionArea]:
    """Return all divisions whose polygon contains the given point.

    Ordered from most to least granular (highest admin_level first).
    Returns an empty list if the point falls outside all loaded divisions.
    """
    validate_coords(lat, lon)

    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)

    stmt = (
        select(*_DIVISION_COLS)
        .where(Division.subtype.isnot(None))
        .where(func.ST_Contains(Division.geom, point))
        .order_by(nullslast(Division.admin_level.desc()))
    )

    result = await session.execute(stmt)
    rows = [dict(row) for row in result.mappings()]

    return [div for row in rows if (div := _division(row)) is not None]
