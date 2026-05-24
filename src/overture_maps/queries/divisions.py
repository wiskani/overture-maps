"""Spatial query functions for divisions."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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

    types_result = await session.execute(
        text(
            """
            SELECT DISTINCT subtype
            FROM reference.divisions
            WHERE subtype IS NOT NULL
              AND names->>'primary' ILIKE :pattern
            """
        ),
        {"pattern": f"%{q}%"},
    )
    present_types = {row[0] for row in types_result}

    most_granular: str | None = None
    for st in _DIVISION_SUBTYPE_HIERARCHY:
        if st in present_types:
            most_granular = st
            break

    if most_granular is None:
        result = await session.execute(
            text(
                """
                SELECT
                    id, version, subtype, "class", country, region, admin_level,
                    division_id, is_land, is_territorial, names,
                    ST_AsGeoJSON(ST_Centroid(geom))::json AS geometry
                FROM reference.divisions
                WHERE names->>'primary' ILIKE :pattern
                LIMIT :limit
                """
            ),
            {"pattern": f"%{q}%", "limit": limit},
        )
    else:
        result = await session.execute(
            text(
                """
                SELECT
                    id, version, subtype, "class", country, region, admin_level,
                    division_id, is_land, is_territorial, names,
                    ST_AsGeoJSON(ST_Centroid(geom))::json AS geometry
                FROM reference.divisions
                WHERE subtype = :subtype
                  AND names->>'primary' ILIKE :pattern
                LIMIT :limit
                """
            ),
            {"subtype": most_granular, "pattern": f"%{q}%", "limit": limit},
        )

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
        text("SELECT 1 FROM reference.divisions WHERE id = :did LIMIT 1"),
        {"did": division_id},
    )
    if exists.fetchone() is None:
        raise ValueError(f"division_id {division_id!r} not found")

    result = await session.execute(
        text(
            """
            SELECT
                ts.id, ts.version, ts.subtype, ts."class", ts.subclass, ts.names,
                ST_AsGeoJSON(ts.geom)::json AS geometry
            FROM reference.transportation_segments ts
            JOIN reference.divisions d ON ST_Intersects(ts.geom, d.geom)
            WHERE d.id = :did
              AND ts.names->>'primary' ILIKE :pattern
            LIMIT :limit
            """
        ),
        {"did": division_id, "pattern": f"%{q}%", "limit": limit},
    )
    return [dict(row) for row in result.mappings()]
