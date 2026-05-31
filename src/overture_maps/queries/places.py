"""Spatial query functions for places."""

from __future__ import annotations

from geoalchemy2 import Geography
from overture.schema.places.place import Place as OverturePlace
from sqlalchemy import JSON, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import OvertureValidationError
from ..models import Place
from ..results import NearbyPlaceResult
from ._utils import DEFAULT_LIMIT, _parse_feature, handle_db_errors, validate_coords

_LIMIT = DEFAULT_LIMIT


@handle_db_errors
async def nearby_places(
    session: AsyncSession, lat: float, lon: float, limit: int = _LIMIT
) -> list[NearbyPlaceResult]:
    """Return the nearest points of interest to the given point."""
    validate_coords(lat, lon)
    if not isinstance(limit, int) or limit < 1:
        raise OvertureValidationError(
            f"limit must be a positive integer, got: {limit!r}"
        )

    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    geog = Geography(srid=4326)
    distance = func.ST_Distance(cast(Place.geom, geog), cast(point, geog))

    stmt = (
        select(
            Place.id,
            Place.version,
            Place.confidence,
            Place.operating_status,
            Place.basic_category,
            Place.bbox,
            Place.sources,
            Place.names,
            Place.categories,
            Place.taxonomy,
            Place.websites,
            Place.emails,
            Place.socials,
            Place.phones,
            Place.brand,
            Place.addresses,
            func.ST_AsGeoJSON(Place.geom).cast(JSON).label("geometry"),
            distance.label("distance_meters"),
        )
        .order_by(distance)
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = [dict(row) for row in result.mappings()]

    out: list[NearbyPlaceResult] = []
    for row in rows:
        place = _parse_feature(OverturePlace, row, "places", "place")
        if place is not None:
            out.append(
                NearbyPlaceResult(place=place, distance_meters=row["distance_meters"])
            )
    return out


@handle_db_errors
async def search_places(
    session: AsyncSession, q: str, limit: int = _LIMIT
) -> list[OverturePlace]:
    """Return points of interest whose name matches the given string."""
    if not q or not q.strip():
        raise OvertureValidationError("q must be a non-empty string")
    if not isinstance(limit, int) or limit < 1:
        raise OvertureValidationError(
            f"limit must be a positive integer, got: {limit!r}"
        )

    stmt = (
        select(
            Place.id,
            Place.version,
            Place.confidence,
            Place.operating_status,
            Place.basic_category,
            Place.bbox,
            Place.sources,
            Place.names,
            Place.categories,
            Place.taxonomy,
            Place.websites,
            Place.emails,
            Place.socials,
            Place.phones,
            Place.brand,
            Place.addresses,
            func.ST_AsGeoJSON(Place.geom).cast(JSON).label("geometry"),
        )
        .where(Place.names["primary"].astext.ilike(f"%{q}%"))
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = [dict(row) for row in result.mappings()]

    return [
        place
        for row in rows
        if (place := _parse_feature(OverturePlace, row, "places", "place")) is not None
    ]
