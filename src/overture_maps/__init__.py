"""overture-maps: PostGIS spatial queries over Overture Maps data."""

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
    # exceptions
    "OvertureError",
    "OvertureConnectionError",
    "OvertureValidationError",
    "OvertureNotFoundError",
]
