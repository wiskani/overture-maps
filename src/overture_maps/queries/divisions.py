"""Spatial query functions for divisions."""

from __future__ import annotations

from sqlalchemy import JSON, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Division, TransportationSegment

_LIMIT = 10

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


async def search_divisions(
    session: AsyncSession, q: str, limit: int = _LIMIT
) -> list[dict]:
    """Return the lowest-hierarchy division whose name matches the given string.

    Filters by the most granular subtype present in the loaded data.
    """
    if not q or not q.strip():
        raise ValueError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got: {limit!r}")

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

    _cols = (
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
        Division.names,
        func.ST_AsGeoJSON(func.ST_Centroid(Division.geom)).cast(JSON).label("geometry"),
    )

    if most_granular is None:
        stmt = (
            select(*_cols)
            .where(Division.names["primary"].astext.ilike(pattern))
            .limit(limit)
        )
    else:
        stmt = (
            select(*_cols)
            .where(Division.subtype == most_granular)
            .where(Division.names["primary"].astext.ilike(pattern))
            .limit(limit)
        )

    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings()]


async def streets_in_division(
    session: AsyncSession, division_id: str, q: str, limit: int = _LIMIT
) -> list[dict]:
    """Return streets whose name matches q within the given division.

    Raises ValueError if division_id is not found.
    """
    if not division_id or not str(division_id).strip():
        raise ValueError("division_id must be a non-empty string")
    if not q or not q.strip():
        raise ValueError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got: {limit!r}")

    exists = await session.execute(
        select(Division.id).where(Division.id == division_id).limit(1)
    )
    if exists.fetchone() is None:
        raise ValueError(f"division_id {division_id!r} not found")

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
        .join(
            Division,
            func.ST_Intersects(TransportationSegment.geom, Division.geom),
        )
        .where(Division.id == division_id)
        .where(TransportationSegment.names["primary"].astext.ilike(f"%{q}%"))
        .limit(limit)
    )

    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings()]
