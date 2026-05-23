"""Tests for the load script and schema_meta population."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.conftest import SF_CONFIG


@pytest.mark.asyncio
async def test_schema_meta_has_one_row_per_theme(session):
    result = await session.execute(text("SELECT theme FROM reference.schema_meta ORDER BY theme"))
    themes = [r[0] for r in result]
    expected = {
        "places",
        "addresses",
        "divisions",
        "transportation_segments",
        "transportation_connectors",
    }
    assert set(themes) == expected


@pytest.mark.asyncio
async def test_schema_meta_has_data_release(session):
    result = await session.execute(
        text("SELECT data_release FROM reference.schema_meta LIMIT 1")
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == SF_CONFIG.data_release


@pytest.mark.asyncio
async def test_schema_meta_has_schema_version(session):
    result = await session.execute(
        text("SELECT schema_version FROM reference.schema_meta LIMIT 1")
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == SF_CONFIG.schema_version


@pytest.mark.asyncio
async def test_schema_meta_row_count_is_non_negative(session):
    result = await session.execute(
        text("SELECT theme, row_count FROM reference.schema_meta")
    )
    for theme, count in result:
        assert count >= 0, f"Theme {theme} has negative row_count"


@pytest.mark.asyncio
async def test_schema_meta_columns_is_list(session):
    result = await session.execute(
        text("SELECT theme, columns FROM reference.schema_meta")
    )
    for theme, cols in result:
        assert isinstance(cols, list), f"columns for {theme} is not a list: {cols!r}"


@pytest.mark.asyncio
async def test_places_table_has_data(session):
    result = await session.execute(text("SELECT COUNT(*) FROM reference.places"))
    assert result.scalar() > 0


@pytest.mark.asyncio
async def test_segments_table_has_data(session):
    result = await session.execute(
        text("SELECT COUNT(*) FROM reference.transportation_segments")
    )
    assert result.scalar() > 0


@pytest.mark.asyncio
async def test_divisions_table_has_data(session):
    result = await session.execute(text("SELECT COUNT(*) FROM reference.divisions"))
    assert result.scalar() > 0
