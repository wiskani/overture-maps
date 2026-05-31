"""overture-maps: PostGIS spatial queries over Overture Maps data."""

from overture.schema.addresses.address import Address as OvertureAddress
from overture.schema.divisions.division_area import DivisionArea as OvertureDivisionArea
from overture.schema.places.place import Place as OverturePlace
from overture.schema.transportation.segment.models import Segment as OvertureSegment

from .exceptions import (
    OvertureConnectionError,
    OvertureError,
    OvertureNotFoundError,
    OvertureValidationError,
)
from .queries.addresses import nearby_addresses
from .queries.divisions import search_divisions, streets_in_division
from .queries.health import health
from .queries.places import nearby_places, search_places
from .queries.streets import search_streets, street_at_point, streets_near_place
from .results import (
    NearbyAddressResult,
    NearbyPlaceResult,
    NearbySegmentResult,
    StreetAtPointResult,
)

__all__ = [
    # query functions
    "nearby_addresses",
    "street_at_point",
    "nearby_places",
    "search_places",
    "streets_near_place",
    "search_streets",
    "search_divisions",
    "streets_in_division",
    "health",
    # result wrapper types
    "NearbyAddressResult",
    "NearbyPlaceResult",
    "NearbySegmentResult",
    "StreetAtPointResult",
    # official Overture schema types
    "OvertureAddress",
    "OverturePlace",
    "OvertureDivisionArea",
    "OvertureSegment",
    # exceptions
    "OvertureError",
    "OvertureConnectionError",
    "OvertureValidationError",
    "OvertureNotFoundError",
]
