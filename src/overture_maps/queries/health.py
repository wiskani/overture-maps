"""Health check function."""

from __future__ import annotations

from sqlalchemy import text

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Config

# Columns that each query function depends on. health() validates these exist.
_REQUIRED_COLUMNS: dict[str, list[str]] = {
    "places": ["id", "name", "category", "geom", "raw"],
    "addresses": ["id", "number", "street", "postcode", "locality", "country", "geom", "raw"],
    "divisions": ["id", "name", "division_type", "country", "geom", "raw"],
    "transportation_segments": ["id", "name", "road_class", "geom", "raw"],
    "transportation_connectors": ["id", "geom", "raw"],
    "schema_meta": ["theme", "data_release", "schema_version", "columns", "row_count", "load_timestamp"],
}


async def health(session: AsyncSession, config: Config) -> dict:
    """Return connectivity status, data summary, and schema validation result.

    Never raises — returns connectivity: false if overture_db is unreachable.
    """
    try:
        return await _health(session, config)
    except Exception:
        return {"connectivity": False}


async def _health(session: AsyncSession, config: Config) -> dict:
    # Row counts per theme from schema_meta
    meta_result = await session.execute(
        text("""
            SELECT theme, data_release, schema_version, row_count
            FROM reference.schema_meta
        """)
    )
    meta_rows = {r["theme"]: r for r in meta_result.mappings()}

    data_release = next((r["data_release"] for r in meta_rows.values()), None)
    schema_version = next((r["schema_version"] for r in meta_rows.values()), None)

    row_counts = {theme: meta_rows[theme]["row_count"] for theme in meta_rows}

    # Schema drift detection: compare required columns vs actual columns in DB
    drift: list[str] = []
    tables = [
        ("reference", "places"),
        ("reference", "addresses"),
        ("reference", "divisions"),
        ("reference", "transportation_segments"),
        ("reference", "transportation_connectors"),
        ("reference", "schema_meta"),
    ]
    for schema_name, table_name in tables:
        key = table_name
        required = _REQUIRED_COLUMNS.get(key, [])
        if not required:
            continue
        col_result = await session.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = :tname
            """),
            {"schema": schema_name, "tname": table_name},
        )
        actual = {row[0] for row in col_result}
        missing = [c for c in required if c not in actual]
        if missing:
            drift.append(f"{schema_name}.{table_name}: missing columns {missing}")

    schema_status = "drift_detected" if drift else "ok"

    return {
        "connectivity": True,
        "data_release": data_release,
        "schema_version": schema_version,
        "bbox": {
            "min_lon": config.bbox.min_lon,
            "min_lat": config.bbox.min_lat,
            "max_lon": config.bbox.max_lon,
            "max_lat": config.bbox.max_lat,
        },
        "row_counts": row_counts,
        "schema_status": schema_status,
        "schema_drift": drift,
    }
