"""Division spatial query functions."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_LIMIT = 10

# Hierarchy from most granular to least granular (Overture Maps schema).
# search_divisions returns the most granular type present in the data.
_DIVISION_TYPE_HIERARCHY = [
    "microhood",
    "macrohood",
    "neighborhood",
    "localadmin",
    "locality",
    "county",
    "region",
    "country",
]


async def search_divisions(
    session: AsyncSession, q: str, limit: int = _LIMIT
) -> list[dict]:
    """Return the division of lowest hierarchy whose name matches the given string.

    Filters by the most granular division_type present in the loaded data.
    """
    if not q or not q.strip():
        raise ValueError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got {limit!r}")

    # Find the most granular division_type present in the data that matches q
    types_result = await session.execute(
        text("""
            SELECT DISTINCT division_type
            FROM reference.divisions
            WHERE division_type IS NOT NULL
              AND name ILIKE :pattern
        """),
        {"pattern": f"%{q}%"},
    )
    present_types = {row[0] for row in types_result}

    most_granular: str | None = None
    for dt in _DIVISION_TYPE_HIERARCHY:
        if dt in present_types:
            most_granular = dt
            break

    if most_granular is None:
        # No typed match — return any matching division
        result = await session.execute(
            text("""
                SELECT
                    id, name, division_type, country,
                    ST_AsGeoJSON(ST_Centroid(geom))::json AS geometry,
                    raw
                FROM reference.divisions
                WHERE name ILIKE :pattern
                LIMIT :limit
            """),
            {"pattern": f"%{q}%", "limit": limit},
        )
    else:
        result = await session.execute(
            text("""
                SELECT
                    id, name, division_type, country,
                    ST_AsGeoJSON(ST_Centroid(geom))::json AS geometry,
                    raw
                FROM reference.divisions
                WHERE division_type = :dtype
                  AND name ILIKE :pattern
                LIMIT :limit
            """),
            {"dtype": most_granular, "pattern": f"%{q}%", "limit": limit},
        )

    return [dict(row) for row in result.mappings()]


async def streets_in_division(
    session: AsyncSession, division_id: str, q: str, limit: int = _LIMIT
) -> list[dict]:
    """Return streets whose name matches q and whose geometry intersects the given division.

    Raises ValueError if division_id is not found.
    """
    if not division_id or not str(division_id).strip():
        raise ValueError("division_id must be a non-empty string")
    if not q or not q.strip():
        raise ValueError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise ValueError(f"limit must be a positive integer, got {limit!r}")

    # Verify division exists
    exists_result = await session.execute(
        text("SELECT 1 FROM reference.divisions WHERE id = :did LIMIT 1"),
        {"did": division_id},
    )
    if exists_result.fetchone() is None:
        raise ValueError(f"division_id {division_id!r} not found")

    result = await session.execute(
        text("""
            SELECT
                ts.id, ts.name, ts.road_class,
                ST_AsGeoJSON(ts.geom)::json AS geometry,
                ts.raw
            FROM reference.transportation_segments ts
            JOIN reference.divisions d ON ST_Intersects(ts.geom, d.geom)
            WHERE d.id = :did
              AND ts.name ILIKE :pattern
            LIMIT :limit
        """),
        {"did": division_id, "pattern": f"%{q}%", "limit": limit},
    )
    return [dict(row) for row in result.mappings()]
