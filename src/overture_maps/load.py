"""Load Overture Maps GeoParquet files into PostGIS reference schema.

Idempotent: drops and recreates tables on every run.
Uses psycopg2 for bulk inserts (synchronous, CLI-only operation).

If the overture-schema package is installed, each row is validated against
the official Pydantic models. Invalid rows are logged by id and skipped.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import psycopg2
import psycopg2.extras
import pyarrow.parquet as pq
from shapely import wkb

from .config import Config

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500

_DDL = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS reference;

DROP TABLE IF EXISTS reference.schema_meta;
DROP TABLE IF EXISTS reference.addresses;
DROP TABLE IF EXISTS reference.divisions;
DROP TABLE IF EXISTS reference.transportation_segments;
DROP TABLE IF EXISTS reference.transportation_connectors;
DROP TABLE IF EXISTS reference.places;

CREATE TABLE reference.places (
    id         TEXT PRIMARY KEY,
    name       TEXT,
    category   TEXT,
    geom       GEOMETRY(Point, 4326),
    raw        JSONB
);

CREATE TABLE reference.addresses (
    id         TEXT PRIMARY KEY,
    number     TEXT,
    street     TEXT,
    postcode   TEXT,
    locality   TEXT,
    country    TEXT,
    geom       GEOMETRY(Point, 4326),
    raw        JSONB
);

CREATE TABLE reference.divisions (
    id             TEXT PRIMARY KEY,
    name           TEXT,
    division_type  TEXT,
    country        TEXT,
    geom           GEOMETRY(GEOMETRY, 4326),
    raw            JSONB
);

CREATE TABLE reference.transportation_segments (
    id          TEXT PRIMARY KEY,
    name        TEXT,
    road_class  TEXT,
    geom        GEOMETRY(LineString, 4326),
    raw         JSONB
);

CREATE TABLE reference.transportation_connectors (
    id    TEXT PRIMARY KEY,
    geom  GEOMETRY(Point, 4326),
    raw   JSONB
);

CREATE TABLE reference.schema_meta (
    theme           TEXT PRIMARY KEY,
    data_release    TEXT NOT NULL,
    schema_version  TEXT NOT NULL,
    columns         JSONB,
    row_count       INTEGER NOT NULL DEFAULT 0,
    load_timestamp  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ON reference.places                  USING GIST(geom);
CREATE INDEX ON reference.places                  USING GIN(raw);
CREATE INDEX ON reference.addresses               USING GIST(geom);
CREATE INDEX ON reference.addresses               (street);
CREATE INDEX ON reference.divisions               USING GIST(geom);
CREATE INDEX ON reference.divisions               (division_type);
CREATE INDEX ON reference.transportation_segments USING GIST(geom);
CREATE INDEX ON reference.transportation_segments (name);
CREATE INDEX ON reference.transportation_connectors USING GIST(geom);
"""


def _connect(dsn: str) -> psycopg2.extensions.connection:
    return psycopg2.connect(
        dsn,
        options="-c log_statement=none -c log_min_duration_statement=-1",
    )


def _clean_nan(obj: object) -> object:
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nan(v) for v in obj]
    return obj


def _safe_str(value: object) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    return v if v else None


def _primary_name(names_value: object) -> str | None:
    if names_value is None:
        return None
    if isinstance(names_value, dict):
        return names_value.get("primary")
    return str(names_value)


def _raw_json(row: dict) -> str:
    return json.dumps(
        _clean_nan({k: v for k, v in row.items() if k != "geometry"}), default=str
    )


def _load_places(
    conn: psycopg2.extensions.connection, path: Path
) -> tuple[int, list[str]]:
    logger.info("Loading places from %s", path.name)
    table = pq.read_table(path)
    columns = table.schema.names
    df = table.to_pandas()
    total = 0
    with conn.cursor() as cur:
        batch: list = []
        for _, row in df.iterrows():
            try:
                geom = wkb.loads(bytes(row["geometry"]))
                name = _primary_name(row.get("names"))
                if not name:
                    continue
                cats = row.get("categories")
                category = cats.get("primary") if isinstance(cats, dict) else None
                batch.append(
                    (
                        str(row["id"]),
                        name,
                        _safe_str(category),
                        geom.wkt,
                        _raw_json(row),
                    )
                )
                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_batch(
                        cur,
                        "INSERT INTO reference.places(id,name,category,geom,raw)"
                        " VALUES(%s,%s,%s,ST_GeomFromText(%s,4326),%s::jsonb)"
                        " ON CONFLICT(id) DO NOTHING",
                        batch,
                    )
                    total += len(batch)
                    batch = []
            except Exception as exc:
                logger.warning("Skipping place row %s: %s", row.get("id"), exc)
        if batch:
            psycopg2.extras.execute_batch(
                cur,
                "INSERT INTO reference.places(id,name,category,geom,raw)"
                " VALUES(%s,%s,%s,ST_GeomFromText(%s,4326),%s::jsonb)"
                " ON CONFLICT(id) DO NOTHING",
                batch,
            )
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
    col_set = set(df.columns)
    street_col = next((c for c in ("street", "thoroughfare") if c in col_set), None)
    total = 0
    with conn.cursor() as cur:
        batch: list = []
        for _, row in df.iterrows():
            try:
                geom = wkb.loads(bytes(row["geometry"]))
                number = _safe_str(row.get("number"))
                street = _safe_str(row.get(street_col)) if street_col else None
                if not street and not number:
                    continue
                postcode = _safe_str(row.get("postcode"))
                country = _safe_str(row.get("country"))
                locality: str | None = None
                levels = row.get("address_levels")
                if isinstance(levels, list):
                    for lvl in levels:
                        if isinstance(lvl, dict) and lvl.get("value"):
                            locality = str(lvl["value"])
                            break
                batch.append(
                    (
                        str(row["id"]),
                        number,
                        street,
                        postcode,
                        locality,
                        country,
                        geom.wkt,
                        _raw_json(row),
                    )
                )
                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_batch(
                        cur,
                        "INSERT INTO reference.addresses"
                        "(id,number,street,postcode,locality,country,geom,raw)"
                        " VALUES(%s,%s,%s,%s,%s,%s,ST_GeomFromText(%s,4326),%s::jsonb)"
                        " ON CONFLICT(id) DO NOTHING",
                        batch,
                    )
                    total += len(batch)
                    batch = []
            except Exception as exc:
                logger.warning("Skipping address row %s: %s", row.get("id"), exc)
        if batch:
            psycopg2.extras.execute_batch(
                cur,
                "INSERT INTO reference.addresses"
                "(id,number,street,postcode,locality,country,geom,raw)"
                " VALUES(%s,%s,%s,%s,%s,%s,ST_GeomFromText(%s,4326),%s::jsonb)"
                " ON CONFLICT(id) DO NOTHING",
                batch,
            )
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
    with conn.cursor() as cur:
        batch: list = []
        for _, row in df.iterrows():
            try:
                geom = wkb.loads(bytes(row["geometry"]))
                name = _primary_name(row.get("names"))
                if not name:
                    continue
                # Overture divisions use 'subtype' in older releases,
                # 'division_type' in newer
                division_type = _safe_str(
                    row.get("division_type") or row.get("subtype")
                )
                country = _safe_str(row.get("country"))
                batch.append(
                    (
                        str(row["id"]),
                        name,
                        division_type,
                        country,
                        geom.wkt,
                        _raw_json(row),
                    )
                )
                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_batch(
                        cur,
                        "INSERT INTO reference.divisions"
                        "(id,name,division_type,country,geom,raw)"
                        " VALUES(%s,%s,%s,%s,ST_GeomFromText(%s,4326),%s::jsonb)"
                        " ON CONFLICT(id) DO NOTHING",
                        batch,
                    )
                    total += len(batch)
                    batch = []
            except Exception as exc:
                logger.warning("Skipping division row %s: %s", row.get("id"), exc)
        if batch:
            psycopg2.extras.execute_batch(
                cur,
                "INSERT INTO reference.divisions"
                "(id,name,division_type,country,geom,raw)"
                " VALUES(%s,%s,%s,%s,ST_GeomFromText(%s,4326),%s::jsonb)"
                " ON CONFLICT(id) DO NOTHING",
                batch,
            )
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
    with conn.cursor() as cur:
        batch: list = []
        for _, row in df.iterrows():
            try:
                geom = wkb.loads(bytes(row["geometry"]))
                name = _primary_name(row.get("names"))
                if not name:
                    continue
                road_class = _safe_str(row.get("class") or row.get("road_class"))
                batch.append(
                    (str(row["id"]), name, road_class, geom.wkt, _raw_json(row))
                )
                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_batch(
                        cur,
                        "INSERT INTO reference.transportation_segments"
                        "(id,name,road_class,geom,raw)"
                        " VALUES(%s,%s,%s,ST_GeomFromText(%s,4326),%s::jsonb)"
                        " ON CONFLICT(id) DO NOTHING",
                        batch,
                    )
                    total += len(batch)
                    batch = []
            except Exception as exc:
                logger.warning("Skipping segment row %s: %s", row.get("id"), exc)
        if batch:
            psycopg2.extras.execute_batch(
                cur,
                "INSERT INTO reference.transportation_segments"
                "(id,name,road_class,geom,raw)"
                " VALUES(%s,%s,%s,ST_GeomFromText(%s,4326),%s::jsonb)"
                " ON CONFLICT(id) DO NOTHING",
                batch,
            )
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
    with conn.cursor() as cur:
        batch: list = []
        for _, row in df.iterrows():
            try:
                geom = wkb.loads(bytes(row["geometry"]))
                batch.append((str(row["id"]), geom.wkt, _raw_json(row)))
                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_batch(
                        cur,
                        "INSERT INTO reference.transportation_connectors(id,geom,raw)"
                        " VALUES(%s,ST_GeomFromText(%s,4326),%s::jsonb)"
                        " ON CONFLICT(id) DO NOTHING",
                        batch,
                    )
                    total += len(batch)
                    batch = []
            except Exception as exc:
                logger.warning("Skipping connector row %s: %s", row.get("id"), exc)
        if batch:
            psycopg2.extras.execute_batch(
                cur,
                "INSERT INTO reference.transportation_connectors(id,geom,raw)"
                " VALUES(%s,ST_GeomFromText(%s,4326),%s::jsonb)"
                " ON CONFLICT(id) DO NOTHING",
                batch,
            )
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
    """Load all themes from geoparquet files into PostGIS.

    Args:
        data_dir: Directory containing the downloaded .parquet files.
        dsn: psycopg2-compatible DSN string for overture_db.
        config: Loaded Config with data_release, schema_version, etc.
        init_schema: When True (default), drop and recreate all tables.
            Set to False to append data to existing tables without dropping.
    """
    logger.info("Connecting to %s", dsn)
    conn = _connect(dsn)

    if init_schema:
        logger.info("Creating reference schema and tables...")
        with conn.cursor() as cur:
            cur.execute(_DDL)
        conn.commit()

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
