"""High-level async client for overture-maps queries.

Wraps the module-level query functions with session lifecycle management
so callers never need to instantiate or pass SQLAlchemy sessions.

Example::

    client = OvertureClient(dsn="postgresql+asyncpg://user:pw@host/db")
    results = await client.nearby_addresses(lat=-17.39, lon=-66.15)
"""

from __future__ import annotations

from overture.schema.addresses.address import Address as OvertureAddress
from overture.schema.divisions.division_area import DivisionArea as OvertureDivisionArea
from overture.schema.places.place import Place as OverturePlace
from overture.schema.transportation.segment.models import Segment as OvertureSegment
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import Config
from .queries.addresses import get_address_by_id as _get_address_by_id
from .queries.addresses import nearby_addresses as _nearby_addresses
from .queries.divisions import divisions_containing_point as _divisions_containing_point
from .queries.divisions import search_divisions as _search_divisions
from .queries.divisions import streets_in_division as _streets_in_division
from .queries.health import health as _health
from .queries.places import nearby_places as _nearby_places
from .queries.places import search_places as _search_places
from .queries.streets import get_segment_by_id as _get_segment_by_id
from .queries.streets import search_streets as _search_streets
from .queries.streets import street_at_point as _street_at_point
from .queries.streets import streets_near_place as _streets_near_place
from .results import (
    NearbyAddressResult,
    NearbyPlaceResult,
    NearbySegmentResult,
    StreetAtPointResult,
)


class OvertureClient:
    """Async facade over all overture-maps query functions.

    Manages the SQLAlchemy engine and session lifecycle internally.
    Callers only need a DSN string — no SQLAlchemy imports required.
    """

    def __init__(
        self,
        dsn: str,
        pool_size: int = 5,
        max_overflow: int = 2,
        pool_timeout: int = 10,
        pool_recycle: int = 1800,
        statement_timeout: int = 5000,
    ) -> None:
        engine = create_async_engine(
            dsn,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            connect_args={
                "server_settings": {
                    "statement_timeout": str(statement_timeout),
                }
            },
        )
        self._session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine,
            autocommit=False,
            expire_on_commit=False,
        )

    # ── Addresses ────────────────────────────────────────────────────────

    async def nearby_addresses(
        self, lat: float, lon: float, limit: int = 10
    ) -> list[NearbyAddressResult]:
        async with self._session_maker() as session:
            return await _nearby_addresses(session, lat, lon, limit)

    async def get_address_by_id(self, address_id: str) -> OvertureAddress | None:
        async with self._session_maker() as session:
            return await _get_address_by_id(session, address_id)

    # ── Streets ──────────────────────────────────────────────────────────

    async def street_at_point(self, lat: float, lon: float) -> StreetAtPointResult:
        async with self._session_maker() as session:
            return await _street_at_point(session, lat, lon)

    async def streets_near_place(
        self, lat: float, lon: float, limit: int = 10
    ) -> list[NearbySegmentResult]:
        async with self._session_maker() as session:
            return await _streets_near_place(session, lat, lon, limit)

    async def search_streets(self, q: str, limit: int = 10) -> list[OvertureSegment]:
        async with self._session_maker() as session:
            return await _search_streets(session, q, limit)

    async def get_segment_by_id(self, segment_id: str) -> OvertureSegment | None:
        async with self._session_maker() as session:
            return await _get_segment_by_id(session, segment_id)

    # ── Places ───────────────────────────────────────────────────────────

    async def nearby_places(
        self, lat: float, lon: float, limit: int = 10
    ) -> list[NearbyPlaceResult]:
        async with self._session_maker() as session:
            return await _nearby_places(session, lat, lon, limit)

    async def search_places(self, q: str, limit: int = 10) -> list[OverturePlace]:
        async with self._session_maker() as session:
            return await _search_places(session, q, limit)

    # ── Divisions ────────────────────────────────────────────────────────

    async def divisions_containing_point(
        self, lat: float, lon: float
    ) -> list[OvertureDivisionArea]:
        async with self._session_maker() as session:
            return await _divisions_containing_point(session, lat, lon)

    async def search_divisions(
        self, q: str, limit: int = 10
    ) -> list[OvertureDivisionArea]:
        async with self._session_maker() as session:
            return await _search_divisions(session, q, limit)

    async def streets_in_division(
        self, division_id: str, q: str, limit: int = 10
    ) -> list[OvertureSegment]:
        async with self._session_maker() as session:
            return await _streets_in_division(session, division_id, q, limit)

    # ── Health ───────────────────────────────────────────────────────────

    async def health(self, config: Config) -> dict:
        async with self._session_maker() as session:
            return await _health(session, config)
