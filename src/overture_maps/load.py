"""Load Overture Maps GeoParquet files into the reference schema of PostGIS.

Uses a synchronous SQLAlchemy Session for bulk inserts (CLI-only operation).
Schema is initialized from the ORM models in models.py via SQLAlchemy.

Validates each row against the official Overture Maps Pydantic models.
Validation errors are logged by row id without aborting the load.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from geoalchemy2.elements import WKTElement
from overture.schema.addresses.address import Address as OvertureAddress
from overture.schema.divisions.division_area import DivisionArea as OvertureDivisionArea
from overture.schema.places.place import Place as OverturePlace
from overture.schema.transportation.connector.models import (
    Connector as OvertureConnector,
)
from overture.schema.transportation.segment.models import Segment as OvertureSegment
from shapely import wkb
from sqlalchemy import create_engine, func
from sqlalchemy import null as sa_null
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .config import Config
from .models import (
    Address,
    Base,
    Division,
    Place,
    SchemaMeta,
    TransportationConnector,
    TransportationSegment,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


def _init_schema(dsn: str) -> None:
    engine = create_engine(dsn)
    with engine.begin() as conn:
        conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(sa_text("CREATE SCHEMA IF NOT EXISTS reference"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    engine.dispose()


def _clean(obj: Any) -> Any:
    """Ensure obj is a JSON-serializable Python native type."""
    if obj is None:
        return None
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def _jsonb(v: Any) -> Any:
    """Return SQLAlchemy null() for None so JSONB columns get SQL NULL, not JSON null.

    psycopg2 converts Python None via its JSON adapter to JSON null (null::jsonb)
    instead of SQL NULL when the column type is JSONB. Using null() bypasses that.
    """
    cleaned = _clean(v)
    return sa_null() if cleaned is None else cleaned


def _validate(model_cls: type, row: dict, theme: str, type_: str, row_id: Any) -> None:
    """Validate a row against the Overture Pydantic model and log discrepancies.

    Does not interrupt the load — validation errors are data-quality signals.
    Rows that fail validation are still inserted; only rows that fail the INSERT
    itself (null id, invalid geometry, etc.) are skipped.
    """
    try:
        validate_dict = {k: _clean(v) for k, v in row.items() if k != "geometry"}
        validate_dict["theme"] = theme
        validate_dict["type"] = type_
        from shapely.geometry import mapping as _mapping

        validate_dict["geometry"] = _mapping(wkb.loads(bytes(row["geometry"])))
        model_cls.model_validate(validate_dict)
    except Exception as exc:
        logger.debug("Schema discrepancy id=%s: %s", row_id, exc)


def _iter_rows(path: Path):
    """Yield (columns, row_dict) for each row using pyarrow native types."""
    table = pq.read_table(path)
    columns = table.schema.names
    # to_pylist() calls as_py() on each element → Python native types, None for nulls
    data = {col: table.column(col).to_pylist() for col in columns}
    for i in range(table.num_rows):
        yield columns, {col: data[col][i] for col in columns}


def _load_places(session: Session, path: Path) -> tuple[int, list[str]]:
    logger.info("Loading places from %s", path.name)
    columns: list[str] = []
    total = 0
    batch: list[dict] = []

    for columns, row in _iter_rows(path):
        row_id = row.get("id")
        _validate(OverturePlace, row, "places", "place", row_id)
        try:
            geom = wkb.loads(bytes(row["geometry"]))
            batch.append(
                {
                    "id": str(row_id),
                    "version": _clean(row.get("version")),
                    "confidence": _clean(row.get("confidence")),
                    "operating_status": _clean(row.get("operating_status")),
                    "basic_category": _clean(row.get("basic_category")),
                    "bbox": _jsonb(row.get("bbox")),
                    "sources": _jsonb(row.get("sources")),
                    "names": _jsonb(row.get("names")),
                    "categories": _jsonb(row.get("categories")),
                    "taxonomy": _jsonb(row.get("taxonomy")),
                    "websites": _jsonb(row.get("websites")),
                    "emails": _jsonb(row.get("emails")),
                    "socials": _jsonb(row.get("socials")),
                    "phones": _jsonb(row.get("phones")),
                    "brand": _jsonb(row.get("brand")),
                    "addresses": _jsonb(row.get("addresses")),
                    "geom": WKTElement(geom.wkt, srid=4326),
                }
            )
            if len(batch) >= _BATCH_SIZE:
                session.execute(pg_insert(Place).values(batch).on_conflict_do_nothing())
                session.commit()
                total += len(batch)
                batch = []
        except Exception as exc:
            logger.warning("Failed to insert place id=%s: %s", row_id, exc)

    if batch:
        session.execute(pg_insert(Place).values(batch).on_conflict_do_nothing())
        session.commit()
        total += len(batch)

    return total, columns


def _load_addresses(session: Session, path: Path) -> tuple[int, list[str]]:
    logger.info("Loading addresses from %s", path.name)
    columns: list[str] = []
    total = 0
    batch: list[dict] = []

    for columns, row in _iter_rows(path):
        row_id = row.get("id")
        _validate(OvertureAddress, row, "addresses", "address", row_id)
        try:
            geom = wkb.loads(bytes(row["geometry"]))
            batch.append(
                {
                    "id": str(row_id),
                    "version": _clean(row.get("version")),
                    "country": _clean(row.get("country")),
                    "number": _clean(row.get("number")),
                    "postal_city": _clean(row.get("postal_city")),
                    "postcode": _clean(row.get("postcode")),
                    "street": _clean(row.get("street")),
                    "unit": _clean(row.get("unit")),
                    "bbox": _jsonb(row.get("bbox")),
                    "sources": _jsonb(row.get("sources")),
                    "address_levels": _jsonb(row.get("address_levels")),
                    "geom": WKTElement(geom.wkt, srid=4326),
                }
            )
            if len(batch) >= _BATCH_SIZE:
                session.execute(
                    pg_insert(Address).values(batch).on_conflict_do_nothing()
                )
                session.commit()
                total += len(batch)
                batch = []
        except Exception as exc:
            logger.warning("Failed to insert address id=%s: %s", row_id, exc)

    if batch:
        session.execute(pg_insert(Address).values(batch).on_conflict_do_nothing())
        session.commit()
        total += len(batch)

    return total, columns


def _load_divisions(session: Session, path: Path) -> tuple[int, list[str]]:
    logger.info("Loading divisions from %s", path.name)
    columns: list[str] = []
    total = 0
    batch: list[dict] = []

    for columns, row in _iter_rows(path):
        row_id = row.get("id")
        _validate(OvertureDivisionArea, row, "divisions", "division_area", row_id)
        try:
            geom = wkb.loads(bytes(row["geometry"]))
            batch.append(
                {
                    "id": str(row_id),
                    "version": _clean(row.get("version")),
                    "subtype": _clean(row.get("subtype")),
                    "class": _clean(row.get("class")),
                    "is_land": _clean(row.get("is_land")),
                    "is_territorial": _clean(row.get("is_territorial")),
                    "division_id": _clean(row.get("division_id")),
                    "country": _clean(row.get("country")),
                    "region": _clean(row.get("region")),
                    "admin_level": _clean(row.get("admin_level")),
                    "bbox": _jsonb(row.get("bbox")),
                    "sources": _jsonb(row.get("sources")),
                    "names": _jsonb(row.get("names")),
                    "geom": WKTElement(geom.wkt, srid=4326),
                }
            )
            if len(batch) >= _BATCH_SIZE:
                session.execute(
                    pg_insert(Division).values(batch).on_conflict_do_nothing()
                )
                session.commit()
                total += len(batch)
                batch = []
        except Exception as exc:
            logger.warning("Failed to insert division id=%s: %s", row_id, exc)

    if batch:
        session.execute(pg_insert(Division).values(batch).on_conflict_do_nothing())
        session.commit()
        total += len(batch)

    return total, columns


def _load_segments(session: Session, path: Path) -> tuple[int, list[str]]:
    logger.info("Loading transportation segments from %s", path.name)
    columns: list[str] = []
    total = 0
    batch: list[dict] = []

    for columns, row in _iter_rows(path):
        row_id = row.get("id")
        _validate(OvertureSegment, row, "transportation", "segment", row_id)
        try:
            geom = wkb.loads(bytes(row["geometry"]))
            batch.append(
                {
                    "id": str(row_id),
                    "version": _clean(row.get("version")),
                    "subtype": _clean(row.get("subtype")),
                    "class": _clean(row.get("class")),
                    "subclass": _clean(row.get("subclass")),
                    "bbox": _jsonb(row.get("bbox")),
                    "sources": _jsonb(row.get("sources")),
                    "names": _jsonb(row.get("names")),
                    "subclass_rules": _jsonb(row.get("subclass_rules")),
                    "connectors": _jsonb(row.get("connectors")),
                    "road_surface": _jsonb(row.get("road_surface")),
                    "road_flags": _jsonb(row.get("road_flags")),
                    "rail_flags": _jsonb(row.get("rail_flags")),
                    "width_rules": _jsonb(row.get("width_rules")),
                    "level_rules": _jsonb(row.get("level_rules")),
                    "access_restrictions": _jsonb(row.get("access_restrictions")),
                    "speed_limits": _jsonb(row.get("speed_limits")),
                    "prohibited_transitions": _jsonb(row.get("prohibited_transitions")),
                    "routes": _jsonb(row.get("routes")),
                    "destinations": _jsonb(row.get("destinations")),
                    "geom": WKTElement(geom.wkt, srid=4326),
                }
            )
            if len(batch) >= _BATCH_SIZE:
                session.execute(
                    pg_insert(TransportationSegment)
                    .values(batch)
                    .on_conflict_do_nothing()
                )
                session.commit()
                total += len(batch)
                batch = []
        except Exception as exc:
            logger.warning("Failed to insert segment id=%s: %s", row_id, exc)

    if batch:
        session.execute(
            pg_insert(TransportationSegment).values(batch).on_conflict_do_nothing()
        )
        session.commit()
        total += len(batch)

    return total, columns


def _load_connectors(session: Session, path: Path) -> tuple[int, list[str]]:
    logger.info("Loading transportation connectors from %s", path.name)
    columns: list[str] = []
    total = 0
    batch: list[dict] = []

    for columns, row in _iter_rows(path):
        row_id = row.get("id")
        _validate(OvertureConnector, row, "transportation", "connector", row_id)
        try:
            geom = wkb.loads(bytes(row["geometry"]))
            batch.append(
                {
                    "id": str(row_id),
                    "version": _clean(row.get("version")),
                    "bbox": _jsonb(row.get("bbox")),
                    "sources": _jsonb(row.get("sources")),
                    "geom": WKTElement(geom.wkt, srid=4326),
                }
            )
            if len(batch) >= _BATCH_SIZE:
                session.execute(
                    pg_insert(TransportationConnector)
                    .values(batch)
                    .on_conflict_do_nothing()
                )
                session.commit()
                total += len(batch)
                batch = []
        except Exception as exc:
            logger.warning("Failed to insert connector id=%s: %s", row_id, exc)

    if batch:
        session.execute(
            pg_insert(TransportationConnector).values(batch).on_conflict_do_nothing()
        )
        session.commit()
        total += len(batch)

    return total, columns


def _upsert_schema_meta(
    session: Session,
    theme: str,
    data_release: str,
    schema_version: str,
    columns: list[str],
    row_count: int,
) -> None:
    stmt = (
        pg_insert(SchemaMeta)
        .values(
            theme=theme,
            data_release=data_release,
            schema_version=schema_version,
            columns=columns,
            row_count=row_count,
        )
        .on_conflict_do_update(
            index_elements=["theme"],
            set_={
                "data_release": data_release,
                "schema_version": schema_version,
                "columns": columns,
                "row_count": row_count,
                "load_timestamp": func.now(),
            },
        )
    )
    session.execute(stmt)
    session.commit()


def load(data_dir: Path, dsn: str, config: Config, *, init_schema: bool = True) -> None:
    """Load all themes from GeoParquet files into PostGIS.

    Args:
        data_dir: Directory containing the downloaded .parquet files.
        dsn: SQLAlchemy DSN for overture_db.
        config: Config with data_release, schema_version, etc.
        init_schema: If True (default), recreates the schema before loading.
    """
    if init_schema:
        logger.info("Initializing reference schema...")
        _init_schema(dsn)

    engine = create_engine(dsn)
    logger.info("Connecting to %s", dsn)

    _LOADERS = [
        ("places", "places.parquet", _load_places),
        ("addresses", "addresses.parquet", _load_addresses),
        ("divisions", "divisions.parquet", _load_divisions),
        ("transportation_segments", "segments.parquet", _load_segments),
        ("transportation_connectors", "connectors.parquet", _load_connectors),
    ]

    with Session(engine) as session:
        for theme, filename, loader_fn in _LOADERS:
            path = data_dir / filename
            if not path.exists():
                logger.warning("%s not found, skipping theme %s.", filename, theme)
                _upsert_schema_meta(
                    session, theme, config.data_release, config.schema_version, [], 0
                )
                continue
            count, cols = loader_fn(session, path)
            logger.info("  %s: %d rows loaded.", theme, count)
            _upsert_schema_meta(
                session, theme, config.data_release, config.schema_version, cols, count
            )

    engine.dispose()
    logger.info("Load complete.")
