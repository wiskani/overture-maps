"""CLI commands — each function prints JSON to stdout."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import click
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import load_config
from .load import load as _load
from .queries.addresses import nearby_addresses as _nearby_addresses
from .queries.divisions import search_divisions as _search_divisions
from .queries.divisions import streets_in_division as _streets_in_division
from .queries.health import health as _health
from .queries.places import nearby_places as _nearby_places
from .queries.places import search_places as _search_places
from .queries.streets import search_streets as _search_streets
from .queries.streets import street_at_point as _street_at_point
from .queries.streets import streets_near_place as _streets_near_place

_DEFAULT_DATA_DIR = Path.cwd() / "data"


def _get_dsn() -> str:
    dsn = os.environ.get("OVERTURE_DB_URL") or load_config().db_url
    if not dsn:
        raise click.UsageError(
            "Database URL not configured. "
            "Set OVERTURE_DB_URL env var or add db_url to overture.yaml."
        )
    return dsn


def _get_sync_dsn(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    dsn = os.environ.get("OVERTURE_DB_SYNC_URL") or load_config().db_sync_url
    if not dsn:
        raise click.UsageError(
            "Sync database URL not configured. "
            "Set OVERTURE_DB_SYNC_URL env var or add db_sync_url to overture.yaml."
        )
    return dsn


def _make_session_factory(dsn: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(dsn, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def _out(data: object) -> None:
    click.echo(json.dumps(data, default=str, ensure_ascii=False))


@click.command("overture-load")
@click.option("--data-dir", default=str(_DEFAULT_DATA_DIR), show_default=True)
@click.option(
    "--dsn",
    default=None,
    help="Sync DSN (postgresql://...). Defaults to env OVERTURE_DB_SYNC_URL.",
)
@click.option(
    "--init-schema/--no-init-schema",
    default=True,
    show_default=True,
    help="Recreate the reference schema before loading.",
)
def load(data_dir: str, dsn: str | None, init_schema: bool) -> None:
    """Load Overture Maps GeoParquet files into PostGIS."""
    sync_dsn = _get_sync_dsn(dsn)
    config = load_config()
    _load(Path(data_dir), sync_dsn, config, init_schema=init_schema)


@click.command("overture-nearby-addresses")
@click.argument("lat", type=float)
@click.argument("lon", type=float)
@click.option("--limit", default=10, show_default=True)
def nearby_addresses(lat: float, lon: float, limit: int) -> None:
    """Return nearest addresses to the given point."""
    factory = _make_session_factory(_get_dsn())

    async def _run_query() -> list[dict]:
        async with factory() as session:
            return await _nearby_addresses(session, lat, lon, limit)

    _out(_run(_run_query()))


@click.command("overture-street-at-point")
@click.argument("lat", type=float)
@click.argument("lon", type=float)
def street_at_point(lat: float, lon: float) -> None:
    """Return street at point and its cross streets."""
    factory = _make_session_factory(_get_dsn())

    async def _run_query() -> dict:
        async with factory() as session:
            return await _street_at_point(session, lat, lon)

    _out(_run(_run_query()))


@click.command("overture-nearby-places")
@click.argument("lat", type=float)
@click.argument("lon", type=float)
@click.option("--limit", default=10, show_default=True)
def nearby_places(lat: float, lon: float, limit: int) -> None:
    """Return nearest places to the given point."""
    factory = _make_session_factory(_get_dsn())

    async def _run_query() -> list[dict]:
        async with factory() as session:
            return await _nearby_places(session, lat, lon, limit)

    _out(_run(_run_query()))


@click.command("overture-search-places")
@click.argument("q")
@click.option("--limit", default=10, show_default=True)
def search_places(q: str, limit: int) -> None:
    """Search places by name."""
    factory = _make_session_factory(_get_dsn())

    async def _run_query() -> list[dict]:
        async with factory() as session:
            return await _search_places(session, q, limit)

    _out(_run(_run_query()))


@click.command("overture-streets-near-place")
@click.argument("lat", type=float)
@click.argument("lon", type=float)
@click.option("--limit", default=10, show_default=True)
def streets_near_place(lat: float, lon: float, limit: int) -> None:
    """Return nearest streets to the given point."""
    factory = _make_session_factory(_get_dsn())

    async def _run_query() -> list[dict]:
        async with factory() as session:
            return await _streets_near_place(session, lat, lon, limit)

    _out(_run(_run_query()))


@click.command("overture-search-streets")
@click.argument("q")
@click.option("--limit", default=10, show_default=True)
def search_streets(q: str, limit: int) -> None:
    """Search streets by name."""
    factory = _make_session_factory(_get_dsn())

    async def _run_query() -> list[dict]:
        async with factory() as session:
            return await _search_streets(session, q, limit)

    _out(_run(_run_query()))


@click.command("overture-search-divisions")
@click.argument("q")
@click.option("--limit", default=10, show_default=True)
def search_divisions(q: str, limit: int) -> None:
    """Search divisions by name (most granular type first)."""
    factory = _make_session_factory(_get_dsn())

    async def _run_query() -> list[dict]:
        async with factory() as session:
            return await _search_divisions(session, q, limit)

    _out(_run(_run_query()))


@click.command("overture-streets-in-division")
@click.argument("division_id")
@click.argument("q")
@click.option("--limit", default=10, show_default=True)
def streets_in_division(division_id: str, q: str, limit: int) -> None:
    """Return streets matching q within the given division."""
    factory = _make_session_factory(_get_dsn())

    async def _run_query() -> list[dict]:
        async with factory() as session:
            return await _streets_in_division(session, division_id, q, limit)

    try:
        _out(_run(_run_query()))
    except ValueError as exc:
        click.echo(json.dumps({"error": str(exc)}), err=True)
        sys.exit(1)


@click.command("overture-health")
def health() -> None:
    """Return health status of the overture_db connection and schema."""
    config = load_config()
    factory = _make_session_factory(_get_dsn())

    async def _run_query() -> dict:
        async with factory() as session:
            return await _health(session, config)

    _out(_run(_run_query()))
