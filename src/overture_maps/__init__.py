"""overture-maps: PostGIS spatial queries over Overture Maps data."""

from overture.schema.addresses.address import Address as OvertureAddress
from overture.schema.divisions.division_area import DivisionArea as OvertureDivisionArea
from overture.schema.places.place import Place as OverturePlace
from overture.schema.transportation.segment.models import Segment as OvertureSegment

from .client import OvertureClient
from .exceptions import (
    OvertureConnectionError,
    OvertureCoverageError,
    OvertureDataNotFoundError,
    OvertureError,
    OvertureNotFoundError,
    OvertureValidationError,
)
from .queries.addresses import get_address_by_id, nearby_addresses
from .queries.divisions import (
    divisions_containing_point,
    search_divisions,
    streets_in_division,
)
from .queries.health import health
from .queries.places import nearby_places, search_places
from .queries.streets import (
    get_segment_by_id,
    search_streets,
    street_at_point,
    streets_near_place,
)
from .results import (
    NearbyAddressResult,
    NearbyPlaceResult,
    NearbySegmentResult,
    StreetAtPointResult,
)

__all__ = [
    # high-level client
    "OvertureClient",
    # query functions
    "nearby_addresses",
    "get_address_by_id",
    "street_at_point",
    "nearby_places",
    "search_places",
    "streets_near_place",
    "search_streets",
    "get_segment_by_id",
    "search_divisions",
    "streets_in_division",
    "divisions_containing_point",
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
    "OvertureCoverageError",
    "OvertureValidationError",
    "OvertureNotFoundError",
    "OvertureDataNotFoundError",
]
