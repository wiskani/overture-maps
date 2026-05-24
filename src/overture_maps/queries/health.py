"""Health check."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Config

# Columns required by the query functions — derived from the real Overture Maps schema
_REQUIRED_COLUMNS: dict[str, list[str]] = {
    "places": [
        "id",
        "version",
        "confidence",
        "operating_status",
        "basic_category",
        "names",
        "categories",
        "geom",
    ],
    "addresses": [
        "id",
        "version",
        "country",
        "number",
        "postal_city",
        "postcode",
        "street",
        "unit",
        "address_levels",
        "geom",
    ],
    "divisions": [
        "id",
        "version",
        "subtype",
        "class",
        "country",
        "region",
        "admin_level",
        "division_id",
        "is_land",
        "is_territorial",
        "names",
        "geom",
    ],
    "transportation_segments": [
        "id",
        "version",
        "subtype",
        "class",
        "subclass",
        "names",
        "connectors",
        "geom",
    ],
    "transportation_connectors": ["id", "version", "geom"],
    "schema_meta": [
        "theme",
        "data_release",
        "schema_version",
        "columns",
        "row_count",
        "load_timestamp",
    ],
}


async def health(session: AsyncSession, config: Config) -> dict:
    """Return connectivity status, data summary, and schema validation result.

    Never raises — returns connectivity: false when overture_db is unreachable.
    """
    try:
        return await _health(session, config)
    except Exception:
        return {"connectivity": False}


async def _health(session: AsyncSession, config: Config) -> dict:
    meta_result = await session.execute(
        text(
            """
            SELECT theme, data_release, schema_version, row_count
            FROM reference.schema_meta
            """
        )
    )
    meta_rows = {r["theme"]: r for r in meta_result.mappings()}

    data_release = next((r["data_release"] for r in meta_rows.values()), None)
    schema_version = next((r["schema_version"] for r in meta_rows.values()), None)
    row_counts = {theme: meta_rows[theme]["row_count"] for theme in meta_rows}

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
        required = _REQUIRED_COLUMNS.get(table_name, [])
        if not required:
            continue
        col_result = await session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = :tname
                """
            ),
            {"schema": schema_name, "tname": table_name},
        )
        actual = {row[0] for row in col_result}
        missing = [c for c in required if c not in actual]
        if missing:
            drift.append(f"{schema_name}.{table_name}: missing columns {missing}")

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
        "schema_status": "drift_detected" if drift else "ok",
        "schema_drift": drift,
    }
