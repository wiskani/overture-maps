"""Tests for health()."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from overture_maps.queries.health import health
from tests.conftest import COCHABAMBA_CONFIG, SF_CONFIG, _TEST_DB_URL_ASYNC


@pytest.mark.asyncio
async def test_health_returns_connectivity_true(session):
    result = await health(session, SF_CONFIG)
    assert result["connectivity"] is True


@pytest.mark.asyncio
async def test_health_returns_data_release(session):
    result = await health(session, SF_CONFIG)
    assert result["data_release"] == SF_CONFIG.data_release


@pytest.mark.asyncio
async def test_health_returns_schema_version(session):
    result = await health(session, SF_CONFIG)
    assert result["schema_version"] == SF_CONFIG.schema_version


@pytest.mark.asyncio
async def test_health_returns_bbox(session):
    result = await health(session, SF_CONFIG)
    bbox = result["bbox"]
    assert bbox["min_lon"] == SF_CONFIG.bbox.min_lon
    assert bbox["min_lat"] == SF_CONFIG.bbox.min_lat
    assert bbox["max_lon"] == SF_CONFIG.bbox.max_lon
    assert bbox["max_lat"] == SF_CONFIG.bbox.max_lat


@pytest.mark.asyncio
async def test_health_returns_row_counts(session):
    result = await health(session, SF_CONFIG)
    assert "row_counts" in result
    for theme in ("places", "transportation_segments", "divisions"):
        assert theme in result["row_counts"]
        assert result["row_counts"][theme] >= 0


@pytest.mark.asyncio
async def test_health_schema_status_ok_when_intact(session):
    result = await health(session, SF_CONFIG)
    assert result["schema_status"] == "ok"
    assert result["schema_drift"] == []


@pytest.mark.asyncio
async def test_health_schema_status_drift_when_column_missing():
    """Dropping a required column causes health() to report drift_detected."""
    engine = create_async_engine(_TEST_DB_URL_ASYNC, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        await session.execute(
            text("ALTER TABLE reference.addresses DROP COLUMN IF EXISTS street")
        )
        await session.commit()

    try:
        async with factory() as session:
            result = await health(session, SF_CONFIG)
        assert result["schema_status"] == "drift_detected"
        assert any("street" in d for d in result["schema_drift"])
    finally:
        # Restore the column so other tests are not affected
        async with factory() as session:
            await session.execute(
                text("ALTER TABLE reference.addresses ADD COLUMN IF NOT EXISTS street TEXT")
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_health_connectivity_false_when_unreachable():
    """health() returns connectivity: false without raising when DB is unreachable."""
    engine = create_async_engine(
        "postgresql+asyncpg://overture:overture@localhost:9999/overture",
        connect_args={"timeout": 2},
        poolclass=NullPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        result = await health(session, SF_CONFIG)

    assert result["connectivity"] is False
    assert "error" in result
    await engine.dispose()


@pytest.mark.asyncio
async def test_health_cbba_bbox_uses_cbba_config(session):
    result = await health(session, COCHABAMBA_CONFIG)
    assert result["connectivity"] is True
    assert result["bbox"]["min_lon"] == COCHABAMBA_CONFIG.bbox.min_lon
