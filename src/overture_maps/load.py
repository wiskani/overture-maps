"""Load Overture Maps GeoParquet files into the reference schema of PostGIS.

Uses psycopg2 for bulk inserts (synchronous, CLI-only operation).
Schema is initialized from the ORM models in models.py via SQLAlchemy.

Validates each row against the official Overture Maps Pydantic models.
Validation errors are logged by row id without aborting the load.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import pyarrow.parquet as pq
from overture.schema.addresses.address import Address as OvertureAddress
from overture.schema.divisions.division_area import DivisionArea as OvertureDivisionArea
from overture.schema.places.place import Place as OverturePlace
from overture.schema.transportation.connector.models import (
    Connector as OvertureConnector,
)
from overture.schema.transportation.segment.models import Segment as OvertureSegment
from shapely import wkb
from sqlalchemy import create_engine
from sqlalchemy import text as sa_text

from .config import Config
from .models import Base

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


def _connect(dsn: str) -> psycopg2.extensions.connection:
    return psycopg2.connect(
        dsn,
        options="-c log_statement=none -c log_min_duration_statement=-1",
    )


def _clean_numpy(obj: Any) -> Any:
    try:
        import numpy as np  # numpy is a transitive dependency of pandas

        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj) if np.isfinite(obj) else None
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return [_clean(v) for v in obj.tolist()]
    except ImportError:
        pass
    return obj


def _clean_pandas(obj: Any) -> Any:
    try:
        import pandas as pd

        if pd.isna(obj):
            return None
    except (TypeError, ValueError, ImportError):
        pass
    return obj


def _clean(obj: Any) -> Any:
    """Convert numpy/pandas types to native Python and strip NaN/inf."""
    if obj is None:
        return None
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    obj = _clean_numpy(obj)
    return _clean_pandas(obj)


def _to_jsonb(v: Any) -> str | None:
    v = _clean(v)
    if v is None:
        return None
    return json.dumps(v, default=str)


def _scalar(v: Any) -> Any:
    return _clean(v)


def _geojson(wkb_bytes: bytes) -> dict:
    import json as _json

    geom = wkb.loads(bytes(wkb_bytes))
    return (
        _json.loads(geom.__geo_interface__.__str__())
        if False
        else {
            "type": geom.geom_type,
            "coordinates": (
                list(geom.__geo_interface__["coordinates"])
                if "coordinates" in geom.__geo_interface__
                else []
            ),
        }
    )


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


def _load_places(
    conn: psycopg2.extensions.connection, path: Path
) -> tuple[int, list[str]]:
    logger.info("Loading places from %s", path.name)
    table = pq.read_table(path)
    columns = table.schema.names
    df = table.to_pandas()
    total = 0
    sql = (
        "INSERT INTO reference.places"
        "(id,version,confidence,operating_status,basic_category,"
        "bbox,sources,names,categories,taxonomy,"
        "websites,emails,socials,phones,brand,addresses,geom)"
        " VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,"
        "%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,"
        "%s::jsonb,ST_GeomFromText(%s,4326))"
        " ON CONFLICT(id) DO NOTHING"
    )
    with conn.cursor() as cur:
        batch: list = []
        for _, row in df.iterrows():
            row_id = row.get("id")
            _validate(OverturePlace, row, "places", "place", row_id)
            try:
                geom = wkb.loads(bytes(row["geometry"]))
                batch.append(
                    (
                        str(row_id),
                        _scalar(row.get("version")),
                        _scalar(row.get("confidence")),
                        _scalar(row.get("operating_status")),
                        _scalar(row.get("basic_category")),
                        _to_jsonb(row.get("bbox")),
                        _to_jsonb(row.get("sources")),
                        _to_jsonb(row.get("names")),
                        _to_jsonb(row.get("categories")),
                        _to_jsonb(row.get("taxonomy")),
                        _to_jsonb(row.get("websites")),
                        _to_jsonb(row.get("emails")),
                        _to_jsonb(row.get("socials")),
                        _to_jsonb(row.get("phones")),
                        _to_jsonb(row.get("brand")),
                        _to_jsonb(row.get("addresses")),
                        geom.wkt,
                    )
                )
                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_batch(cur, sql, batch)
                    total += len(batch)
                    batch = []
            except Exception as exc:
                logger.warning("Failed to insert place id=%s: %s", row_id, exc)
        if batch:
            psycopg2.extras.execute_batch(cur, sql, batch)
            total += len(batch)
    conn.commit()
    return total, columns


def _load_addresses(
    conn: psycopg2.extensions.connection, path: Path
) -> tuple[int, list[str]]:
    logger.info("Loading addresses from %s", path.name)
    table = pq.read_table(path)
    columns = table.schema.names
    df = table.to_pandas()
    total = 0
    sql = (
        "INSERT INTO reference.addresses"
        "(id,version,country,number,postal_city,postcode,street,unit,"
        "bbox,sources,address_levels,geom)"
        " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,"
        "%s::jsonb,%s::jsonb,%s::jsonb,ST_GeomFromText(%s,4326))"
        " ON CONFLICT(id) DO NOTHING"
    )
    with conn.cursor() as cur:
        batch: list = []
        for _, row in df.iterrows():
            row_id = row.get("id")
            _validate(OvertureAddress, row, "addresses", "address", row_id)
            try:
                geom = wkb.loads(bytes(row["geometry"]))
                batch.append(
                    (
                        str(row_id),
                        _scalar(row.get("version")),
                        _scalar(row.get("country")),
                        _scalar(row.get("number")),
                        _scalar(row.get("postal_city")),
                        _scalar(row.get("postcode")),
                        _scalar(row.get("street")),
                        _scalar(row.get("unit")),
                        _to_jsonb(row.get("bbox")),
                        _to_jsonb(row.get("sources")),
                        _to_jsonb(row.get("address_levels")),
                        geom.wkt,
                    )
                )
                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_batch(cur, sql, batch)
                    total += len(batch)
                    batch = []
            except Exception as exc:
                logger.warning("Failed to insert address id=%s: %s", row_id, exc)
        if batch:
            psycopg2.extras.execute_batch(cur, sql, batch)
            total += len(batch)
    conn.commit()
    return total, columns


def _load_divisions(
    conn: psycopg2.extensions.connection, path: Path
) -> tuple[int, list[str]]:
    logger.info("Loading divisions from %s", path.name)
    table = pq.read_table(path)
    columns = table.schema.names
    df = table.to_pandas()
    total = 0
    sql = (
        "INSERT INTO reference.divisions"
        '(id,version,subtype,"class",is_land,is_territorial,'
        "division_id,country,region,admin_level,bbox,sources,names,geom)"
        " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
        "%s::jsonb,%s::jsonb,%s::jsonb,ST_GeomFromText(%s,4326))"
        " ON CONFLICT(id) DO NOTHING"
    )
    with conn.cursor() as cur:
        batch: list = []
        for _, row in df.iterrows():
            row_id = row.get("id")
            _validate(OvertureDivisionArea, row, "divisions", "division_area", row_id)
            try:
                geom = wkb.loads(bytes(row["geometry"]))
                batch.append(
                    (
                        str(row_id),
                        _scalar(row.get("version")),
                        _scalar(row.get("subtype")),
                        _scalar(row.get("class")),
                        _scalar(row.get("is_land")),
                        _scalar(row.get("is_territorial")),
                        _scalar(row.get("division_id")),
                        _scalar(row.get("country")),
                        _scalar(row.get("region")),
                        _scalar(row.get("admin_level")),
                        _to_jsonb(row.get("bbox")),
                        _to_jsonb(row.get("sources")),
                        _to_jsonb(row.get("names")),
                        geom.wkt,
                    )
                )
                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_batch(cur, sql, batch)
                    total += len(batch)
                    batch = []
            except Exception as exc:
                logger.warning("Failed to insert division id=%s: %s", row_id, exc)
        if batch:
            psycopg2.extras.execute_batch(cur, sql, batch)
            total += len(batch)
    conn.commit()
    return total, columns


def _load_segments(
    conn: psycopg2.extensions.connection, path: Path
) -> tuple[int, list[str]]:
    logger.info("Loading transportation segments from %s", path.name)
    table = pq.read_table(path)
    columns = table.schema.names
    df = table.to_pandas()
    total = 0
    sql = (
        "INSERT INTO reference.transportation_segments"
        '(id,version,subtype,"class",subclass,'
        "bbox,sources,names,subclass_rules,connectors,"
        "road_surface,road_flags,rail_flags,"
        "width_rules,level_rules,access_restrictions,"
        "speed_limits,prohibited_transitions,routes,destinations,geom)"
        " VALUES(%s,%s,%s,%s,%s,"
        "%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,"
        "%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,"
        "%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,"
        "ST_GeomFromText(%s,4326))"
        " ON CONFLICT(id) DO NOTHING"
    )
    with conn.cursor() as cur:
        batch: list = []
        for _, row in df.iterrows():
            row_id = row.get("id")
            _validate(OvertureSegment, row, "transportation", "segment", row_id)
            try:
                geom = wkb.loads(bytes(row["geometry"]))
                batch.append(
                    (
                        str(row_id),
                        _scalar(row.get("version")),
                        _scalar(row.get("subtype")),
                        _scalar(row.get("class")),
                        _scalar(row.get("subclass")),
                        _to_jsonb(row.get("bbox")),
                        _to_jsonb(row.get("sources")),
                        _to_jsonb(row.get("names")),
                        _to_jsonb(row.get("subclass_rules")),
                        _to_jsonb(row.get("connectors")),
                        _to_jsonb(row.get("road_surface")),
                        _to_jsonb(row.get("road_flags")),
                        _to_jsonb(row.get("rail_flags")),
                        _to_jsonb(row.get("width_rules")),
                        _to_jsonb(row.get("level_rules")),
                        _to_jsonb(row.get("access_restrictions")),
                        _to_jsonb(row.get("speed_limits")),
                        _to_jsonb(row.get("prohibited_transitions")),
                        _to_jsonb(row.get("routes")),
                        _to_jsonb(row.get("destinations")),
                        geom.wkt,
                    )
                )
                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_batch(cur, sql, batch)
                    total += len(batch)
                    batch = []
            except Exception as exc:
                logger.warning("Failed to insert segment id=%s: %s", row_id, exc)
        if batch:
            psycopg2.extras.execute_batch(cur, sql, batch)
            total += len(batch)
    conn.commit()
    return total, columns


def _load_connectors(
    conn: psycopg2.extensions.connection, path: Path
) -> tuple[int, list[str]]:
    logger.info("Loading transportation connectors from %s", path.name)
    table = pq.read_table(path)
    columns = table.schema.names
    df = table.to_pandas()
    total = 0
    sql = (
        "INSERT INTO reference.transportation_connectors(id,version,bbox,sources,geom)"
        " VALUES(%s,%s,%s::jsonb,%s::jsonb,ST_GeomFromText(%s,4326))"
        " ON CONFLICT(id) DO NOTHING"
    )
    with conn.cursor() as cur:
        batch: list = []
        for _, row in df.iterrows():
            row_id = row.get("id")
            _validate(OvertureConnector, row, "transportation", "connector", row_id)
            try:
                geom = wkb.loads(bytes(row["geometry"]))
                batch.append(
                    (
                        str(row_id),
                        _scalar(row.get("version")),
                        _to_jsonb(row.get("bbox")),
                        _to_jsonb(row.get("sources")),
                        geom.wkt,
                    )
                )
                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_batch(cur, sql, batch)
                    total += len(batch)
                    batch = []
            except Exception as exc:
                logger.warning("Failed to insert connector id=%s: %s", row_id, exc)
        if batch:
            psycopg2.extras.execute_batch(cur, sql, batch)
            total += len(batch)
    conn.commit()
    return total, columns


def _upsert_schema_meta(
    conn: psycopg2.extensions.connection,
    theme: str,
    data_release: str,
    schema_version: str,
    columns: list[str],
    row_count: int,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reference.schema_meta
            (theme,data_release,schema_version,columns,row_count,load_timestamp)
            VALUES(%s,%s,%s,%s::jsonb,%s,NOW())
            ON CONFLICT(theme) DO UPDATE SET
                data_release=EXCLUDED.data_release,
                schema_version=EXCLUDED.schema_version,
                columns=EXCLUDED.columns,
                row_count=EXCLUDED.row_count,
                load_timestamp=EXCLUDED.load_timestamp
            """,
            (theme, data_release, schema_version, json.dumps(columns), row_count),
        )
    conn.commit()


def load(data_dir: Path, dsn: str, config: Config, *, init_schema: bool = True) -> None:
    """Load all themes from GeoParquet files into PostGIS.

    Args:
        data_dir: Directory containing the downloaded .parquet files.
        dsn: psycopg2 DSN for overture_db.
        config: Config with data_release, schema_version, etc.
        init_schema: If True (default), recreates the schema before loading.
    """
    if init_schema:
        logger.info("Initializing reference schema...")
        _init_schema(dsn)
    logger.info("Connecting to %s", dsn)
    conn = _connect(dsn)

    _LOADERS = [
        ("places", "places.parquet", _load_places),
        ("addresses", "addresses.parquet", _load_addresses),
        ("divisions", "divisions.parquet", _load_divisions),
        ("transportation_segments", "segments.parquet", _load_segments),
        ("transportation_connectors", "connectors.parquet", _load_connectors),
    ]

    for theme, filename, loader_fn in _LOADERS:
        path = data_dir / filename
        if not path.exists():
            logger.warning("%s not found, skipping theme %s.", filename, theme)
            _upsert_schema_meta(
                conn, theme, config.data_release, config.schema_version, [], 0
            )
            continue
        count, cols = loader_fn(conn, path)
        logger.info("  %s: %d rows loaded.", theme, count)
        _upsert_schema_meta(
            conn, theme, config.data_release, config.schema_version, cols, count
        )

    conn.close()
    logger.info("Load complete.")
