"""Shared utilities for query modules."""

from __future__ import annotations

from functools import wraps

from sqlalchemy.exc import SQLAlchemyError

from ..exceptions import OvertureConnectionError, OvertureError, OvertureValidationError

DEFAULT_LIMIT = 10


def validate_coords(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise OvertureValidationError(f"lat must be between -90 and 90, got: {lat}")
    if not (-180 <= lon <= 180):
        raise OvertureValidationError(f"lon must be between -180 and 180, got: {lon}")


def handle_db_errors(func):  # type: ignore[no-untyped-def]
    """Wrap SQLAlchemyError into OvertureConnectionError.

    Applied to every public query function so callers never need to import
    SQLAlchemy to distinguish a DB connectivity failure from a bad parameter.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            return await func(*args, **kwargs)
        except OvertureError:
            raise
        except (SQLAlchemyError, OSError) as exc:
            # OSError covers asyncpg connection failures (e.g. ConnectionRefusedError)
            # that SQLAlchemy does not always wrap as OperationalError.
            raise OvertureConnectionError(f"Database error: {exc}") from exc

    return wrapper
