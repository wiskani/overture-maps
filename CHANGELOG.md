# Changelog

## [0.1.7] - 2026-06-14

### Added

- `OvertureDataNotFoundError` exception raised when the GeoParquet data directory
  is missing or contains no `.parquet` files. Exported from the top-level package.
- `Config.data_dir` field: stores the resolved path to the GeoParquet directory.
  Resolution priority: `OVERTURE_DATA_DIR` env var > `data_dir:` in `overture.yaml` >
  `~/.local/share/overture-maps/` (XDG Base Directory Specification).
- `config.py`: `_default_data_dir()` helper that respects `XDG_DATA_HOME` on Linux/macOS
  and falls back to `~/.local/share/overture-maps/`.
- `overture.yaml.example`: documented `data_dir:` field and `OVERTURE_DATA_DIR` env var.

### Changed

- `overture-load` CLI: `--data-dir` now defaults to `None` (resolved at runtime from
  `Config.data_dir`) instead of `Path.cwd() / "data"`. The explicit `--data-dir` flag
  still overrides all other sources.
- `overture-load` CLI: fails fast with a clear error message (including the exact
  `overturemaps download` commands to run) when the resolved data directory does not
  exist or contains no `.parquet` files.
- `tests/conftest.py`: `subprocess.CalledProcessError` during data download is now
  caught and re-raised as `pytest.fail(...)` with the stderr output and a pointer to
  the Overture Maps documentation, instead of an opaque traceback.

## [0.1.4] - 2026-06-01

### Added

- `get_address_by_id(session, address_id)` in `queries/addresses.py` — returns a single
  `OvertureAddress` by Overture id, or `None` if not found.
- `get_segment_by_id(session, segment_id)` in `queries/streets.py` — returns a single
  `OvertureSegment` by Overture id, or `None` if not found.
- `divisions_containing_point(session, lat, lon)` in `queries/divisions.py` — returns all
  `OvertureDivisionArea` instances whose polygon contains the given point, ordered from
  most to least granular (`admin_level DESC NULLS LAST`). Returns an empty list when the
  point falls outside all loaded divisions.
- All three functions exported from the top-level package `__init__.py`.
- Integration tests for all three new functions (including `@handle_db_errors` coverage
  via mocked `SQLAlchemyError`).

### Changed

- `queries/addresses.py`: extracted `_ADDRESS_COLS` tuple to avoid column list duplication
  between `nearby_addresses` and `get_address_by_id`.
- `queries/streets.py`: extracted `_SEGMENT_COLS` tuple shared by `streets_near_place`,
  `search_streets`, and `get_segment_by_id`.
- `queries/divisions.py`: extracted `_DIVISION_COLS` tuple and `_division()` helper shared
  by `search_divisions` and `divisions_containing_point`; added `validate_coords` import.

## [0.1.3] - 2026-05-31

### Changed

- Query functions now return official Overture Maps Pydantic model instances instead of
  plain dicts. The `overture-schema-*` packages moved from the optional `[load]` extra
  to main dependencies (the upstream packaging bug that required the workaround has been
  fixed in the official repo).
- Functions that compute a spatial distance (`nearby_addresses`, `nearby_places`,
  `streets_near_place`) return a dataclass wrapper (`NearbyAddressResult`,
  `NearbyPlaceResult`, `NearbySegmentResult`) that pairs the official model with the
  `distance_meters` field, keeping the Overture schema models unmodified.
- `street_at_point` returns `StreetAtPointResult(street, cross_streets)` instead of a
  plain dict. SQL updated to include `version` for all selected segments.
- `search_divisions` returns full geometry (Polygon/MultiPolygon) instead of the
  centroid Point, matching the `DivisionArea` schema definition.
- `streets_near_place`, `search_streets`, `streets_in_division` return
  `list[OvertureSegment]` / `list[NearbySegmentResult]`.
- Query SELECT lists expanded to include all columns available in each ORM model so
  `model_validate` receives complete data.

### Added

- `src/overture_maps/results.py` — `NearbyAddressResult`, `NearbyPlaceResult`,
  `NearbySegmentResult`, `StreetAtPointResult` dataclasses.
- `_parse_feature` helper in `queries/_utils.py` — validates a query row dict against
  an official Overture Pydantic model; logs debug and returns `None` on schema drift
  instead of crashing the query.
- Top-level exports: `NearbyAddressResult`, `NearbyPlaceResult`, `NearbySegmentResult`,
  `StreetAtPointResult`, `OvertureAddress`, `OverturePlace`, `OvertureDivisionArea`,
  `OvertureSegment`.

### Removed

- `[load]` optional extra — schema packages are now always installed.
- `_get_schema_models()` lazy import function in `load.py` — replaced with module-level
  `_SCHEMA_MODELS` dict using direct imports.

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
