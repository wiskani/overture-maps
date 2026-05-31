"""Shared utilities for query modules."""

from __future__ import annotations

import logging
from functools import wraps
from typing import TypeVar

from sqlalchemy.exc import SQLAlchemyError

from ..exceptions import OvertureConnectionError, OvertureError, OvertureValidationError

DEFAULT_LIMIT = 10

_T = TypeVar("_T")
_logger = logging.getLogger(__name__)


def _parse_feature(model_cls: type[_T], row: dict, theme: str, type_: str) -> _T | None:
    """Validate a query row against an official Overture Pydantic model.

    Uses TypeAdapter so Union types (e.g. Segment) work correctly.
    On ValidationError (schema drift between data_release and schema packages),
    falls back to model_construct to bypass validators while still returning a
    typed object. Logs a warning so callers can detect the drift.
    Returns None only if both paths fail.
    """
    from pydantic import TypeAdapter, ValidationError

    d = {k: v for k, v in row.items() if k != "distance_meters"}
    d["theme"] = theme
    d["type"] = type_
    try:
        return TypeAdapter(model_cls).validate_python(d)
    except ValidationError as exc:
        # Schema drift: data_release version predates current schema packages.
        # model_construct bypasses validators while preserving the typed interface.
        _logger.warning(
            "Schema drift id=%s theme=%s — constructing without validation: %s",
            d.get("id"),
            theme,
            str(exc)[:200],
        )
        if hasattr(model_cls, "model_construct"):
            try:
                return model_cls.model_construct(**d)  # type: ignore[return-value]
            except Exception as construct_exc:
                _logger.debug(
                    "model_construct failed id=%s: %s", d.get("id"), construct_exc
                )
        return None
    except Exception as exc:
        _logger.debug("Unexpected error id=%s: %s", d.get("id"), exc)
        return None


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
