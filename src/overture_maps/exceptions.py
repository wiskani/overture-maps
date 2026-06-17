"""Custom exception hierarchy for the overture-maps library.

All public functions raise subclasses of OvertureError so callers can
distinguish library errors from their own code without importing SQLAlchemy.
"""

from __future__ import annotations


class OvertureError(Exception):
    """Base class for all overture-maps errors."""


class OvertureConnectionError(OvertureError):
    """Raised when overture_db is unreachable or returns a database error."""


class OvertureValidationError(OvertureError):
    """Raised when a function receives an invalid parameter."""


class OvertureNotFoundError(OvertureError):
    """Raised when a referenced entity does not exist in the database."""


class OvertureDataNotFoundError(OvertureError):
    """Raised when the GeoParquet data directory is missing or empty."""


class OvertureCoverageError(OvertureError):
    """Raised when a query point falls outside the configured coverage bbox."""
