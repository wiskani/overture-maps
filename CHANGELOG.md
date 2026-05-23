# Changelog

## [0.1.0] - 2026-05-23

Built and tested against **Overture Maps `data_release: 2024-11-13.0` / `schema_version: 1.0.0`**.

### Added

- Initial release.
- Load Overture Maps themes (addresses, places, divisions, transportation segments and connectors) from GeoParquet files into PostGIS `reference` schema.
- `reference.schema_meta` table populated at load time with data_release, schema_version, columns, row_count, and load_timestamp per theme.
- Query functions: `nearby_addresses`, `street_at_point`, `nearby_places`, `search_places`, `streets_near_place`, `search_streets`, `search_divisions`, `streets_in_division`, `health`.
- CLI commands wrapping every query function with JSON output.
- Configuration via `overture.yaml` with environment variable overrides.
