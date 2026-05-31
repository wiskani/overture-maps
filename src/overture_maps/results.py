"""Wrapper types for query results that include computed spatial fields.

These types pair an official Overture Maps Pydantic model with extra fields
computed by the spatial query (e.g. distance_meters) that are not part of
the Overture schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from overture.schema.addresses.address import Address as OvertureAddress
from overture.schema.divisions.division_area import DivisionArea as OvertureDivisionArea
from overture.schema.places.place import Place as OverturePlace
from overture.schema.transportation.segment.models import Segment as OvertureSegment

__all__ = [
    "NearbyAddressResult",
    "NearbyPlaceResult",
    "NearbySegmentResult",
    "StreetAtPointResult",
    "OvertureAddress",
    "OvertureDivisionArea",
    "OverturePlace",
    "OvertureSegment",
]


@dataclass
class NearbyAddressResult:
    address: OvertureAddress
    distance_meters: float


@dataclass
class NearbyPlaceResult:
    place: OverturePlace
    distance_meters: float


@dataclass
class NearbySegmentResult:
    segment: OvertureSegment
    distance_meters: float


@dataclass
class StreetAtPointResult:
    street: OvertureSegment | None
    cross_streets: list[OvertureSegment] = field(default_factory=list)
