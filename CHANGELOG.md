# Changelog

## [0.1.2] - 2026-05-28

### Added

- Custom exception hierarchy (`exceptions.py`): `OvertureError` (base), `OvertureConnectionError`,
  `OvertureValidationError`, `OvertureNotFoundError`. All exceptions are exported from the top-level
  package so callers never need to import SQLAlchemy to distinguish error categories.
- `handle_db_errors` decorator in `queries/_utils.py` wraps `SQLAlchemyError` and `OSError`
  (asyncpg connection failures) into `OvertureConnectionError`, applied to every public query function.
- `health()` now includes an `"error"` field in the response when `connectivity` is `False`.

### Changed

- All `ValueError` raises in query functions replaced with the appropriate custom exception type.
- `streets_in_division()` raises `OvertureNotFoundError` (instead of `ValueError`) when
  `division_id` is not found.
- CLI error handler unified: all commands now emit `{"error": "<ExceptionType>", "detail": "..."}` to
  stderr with exit code 1 on any `OvertureError`.
- `health()` now catches only `OvertureConnectionError` (instead of bare `Exception`), preventing
  internal bugs from being silently reported as connectivity failures.

## [0.1.1] - 2026-05-27

### Fixed

- `config.py`: default config path now uses `Path.cwd()` instead of a path
  relative to the installed package, so the CLI finds `overture.yaml` correctly
  when the library is installed as a `.whl` in another project.
- `config.py`: `Config` gains optional `db_url` and `db_sync_url` fields read
  from `overture.yaml` (or `OVERTURE_DB_URL` / `OVERTURE_DB_SYNC_URL` env vars).
- `cli.py`: removed hardcoded `overture:overture` credential defaults; both
  `_get_dsn()` and `_get_sync_dsn()` now raise a clear `UsageError` when no URL
  is configured via env var or `overture.yaml`.
- `cli.py`: `_DEFAULT_DATA_DIR` now uses `Path.cwd()` for the same reason.

### Refactored

- Extracted shared `validate_coords` and `DEFAULT_LIMIT` to `queries/_utils.py`,
  removing duplication across `addresses`, `places`, and `streets` modules.

## [0.1.0] - 2026-05-23

Built and tested against **Overture Maps `data_release: 2024-11-13.0` / `schema_version: 1.0.0`**.

### Added

- Initial release.
- Load Overture Maps themes (addresses, places, divisions, transportation segments and connectors) from GeoParquet files into PostGIS `reference` schema.
- `reference.schema_meta` table populated at load time with data_release, schema_version, columns, row_count, and load_timestamp per theme.
- Query functions: `nearby_addresses`, `street_at_point`, `nearby_places`, `search_places`, `streets_near_place`, `search_streets`, `search_divisions`, `streets_in_division`, `health`.
- CLI commands wrapping every query function with JSON output.
- Configuration via `overture.yaml` with environment variable overrides.
