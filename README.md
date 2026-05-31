# overture-maps

Python library that loads Overture Maps data for a configured bounding box into PostGIS and exposes spatial query functions. Used by the TSB backend — installed as a `.whl` via GitHub Releases, no HTTP service.

## Requirements

- Python 3.12+
- Docker (for PostGIS)
- [uv](https://docs.astral.sh/uv/)
- [overturemaps CLI](https://github.com/OvertureMaps/overturemaps-py)

## Setup

```bash
git clone <repo>
cd overture-maps
uv sync
cp overture.yaml.example overture.yaml
# Edit overture.yaml with your city, bbox, data_release, schema_version, and db_url
```

## Configuration

All settings live in `overture.yaml` (gitignored). Every field can be overridden with an environment variable:

| `overture.yaml` key | Environment variable       | Required |
| ------------------- | -------------------------- | -------- |
| `city`              | `OVERTURE_CITY`            | yes      |
| `bbox.*`            | `OVERTURE_BBOX_MIN_LON`, … | yes      |
| `data_release`      | `OVERTURE_DATA_RELEASE`    | yes      |
| `schema_version`    | `OVERTURE_SCHEMA_VERSION`  | yes      |
| `db_url`            | `OVERTURE_DB_URL`          | for CLI  |
| `db_sync_url`       | `OVERTURE_DB_SYNC_URL`     | for load |

There is **no default database URL**. Every CLI command requires either `OVERTURE_DB_URL` in the environment or `db_url` set in `overture.yaml`. If neither is present the command exits immediately with a clear error message.

When using the library programmatically (as the TSB backend does), pass a `Config` object and `AsyncSession` directly — `overture.yaml` is not read.

## Loading data

### 1. Download GeoParquet files

Download each theme using the `overturemaps` CLI. Substitute your bbox and release:

```bash
# Places
overturemaps download --bbox=<min_lon,min_lat,max_lon,max_lat> \
  --type=place -f geoparquet -o data/places.parquet

# Transportation segments
overturemaps download --bbox=<min_lon,min_lat,max_lon,max_lat> \
  --type=segment -f geoparquet -o data/segments.parquet

# Transportation connectors
overturemaps download --bbox=<min_lon,min_lat,max_lon,max_lat> \
  --type=connector -f geoparquet -o data/connectors.parquet

# Addresses
overturemaps download --bbox=<min_lon,min_lat,max_lon,max_lat> \
  --type=address -f geoparquet -o data/addresses.parquet

# Divisions (administrative boundaries)
overturemaps download --bbox=<min_lon,min_lat,max_lon,max_lat> \
  --type=division_area -f geoparquet -o data/divisions.parquet
```

### 2. Start overture_db

```bash
docker compose up -d overture_db_test
```

### 3. Run the load command

```bash
uv run overture-load --data-dir=data --dsn=postgresql://user:password@localhost:7003/overture
```

The load script creates (or recreates) the `reference` schema and all tables, then inserts all rows from the downloaded parquet files. It is idempotent: re-running drops and reloads.

## Query functions

All functions are async and require an `AsyncSession` connected to `overture_db`. They return official Overture Maps Pydantic model instances — the same models used by the official schema packages.

Functions that compute a spatial distance return a wrapper type that pairs the official model with the computed `distance_meters` field.

### Return types

| Function                                       | Return type                  |
| ---------------------------------------------- | ---------------------------- |
| `nearby_addresses(session, lat, lon)`          | `list[NearbyAddressResult]`  |
| `street_at_point(session, lat, lon)`           | `StreetAtPointResult`        |
| `nearby_places(session, lat, lon)`             | `list[NearbyPlaceResult]`    |
| `search_places(session, q)`                    | `list[OverturePlace]`        |
| `streets_near_place(session, lat, lon)`        | `list[NearbySegmentResult]`  |
| `search_streets(session, q)`                   | `list[OvertureSegment]`      |
| `search_divisions(session, q)`                 | `list[OvertureDivisionArea]` |
| `streets_in_division(session, division_id, q)` | `list[OvertureSegment]`      |
| `health(session, config)`                      | `dict`                       |

### Wrapper types

```python
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
    cross_streets: list[OvertureSegment]
```

All types are importable from the top-level package:

```python
from overture_maps import (
    nearby_addresses,
    NearbyAddressResult,
    OvertureAddress,
    OverturePlace,
    OvertureDivisionArea,
    OvertureSegment,
)
```

## CLI usage

All commands print JSON to stdout. Errors print a JSON object to stderr and exit with code 1.

Set `OVERTURE_DB_URL` or add `db_url` to `overture.yaml` before running any query command.

```bash
uv run overture-nearby-addresses 37.788 -122.407
uv run overture-street-at-point 37.788 -122.407
uv run overture-nearby-places 37.788 -122.407
uv run overture-search-places "coffee"
uv run overture-streets-near-place 37.788 -122.407
uv run overture-search-streets "Market"
uv run overture-search-divisions "San Francisco"
uv run overture-streets-in-division <division_id> "st"
uv run overture-health
```

Error output format (stderr, exit 1):

```json
{
  "error": "OvertureValidationError",
  "detail": "lat must be between -90 and 90, got: 999"
}
```

## Error handling

All public functions raise subclasses of `OvertureError`:

| Exception                 | When raised                                          |
| ------------------------- | ---------------------------------------------------- |
| `OvertureValidationError` | Invalid parameter (lat/lon out of range, empty q, …) |
| `OvertureNotFoundError`   | `division_id` not found in the database              |
| `OvertureConnectionError` | overture_db unreachable or returns a database error  |

Import them from the top-level package:

```python
from overture_maps import (
    OvertureError,
    OvertureConnectionError,
    OvertureValidationError,
    OvertureNotFoundError,
)
```

`health()` never raises. When the database is unreachable it returns:

```json
{ "connectivity": false, "error": "Database error: ..." }
```

## Running tests

The test suite requires the `overture_db_test` container (port 7003) running:

```bash
docker compose up -d
uv run pytest tests/ -v
```

Parquet files are downloaded on the first run and cached in `tests/data/`. Subsequent runs are fast.

## Building and releasing a new version

### 1. Build the wheel

```bash
uv build
```

The wheel is written to `dist/overture_maps-<version>-py3-none-any.whl`.

### 2. Create a GitHub Release

1. Bump `version` in `pyproject.toml` (e.g. `0.1.3`) and update `CHANGELOG.md`.
2. Commit and push.
3. Create a GitHub Release with tag `v<version>` (e.g. `v0.1.3`).
4. Upload the `.whl` from `dist/` as a release asset.

### 3. Update the TSB backend

In `backend/pyproject.toml`, update the wheel URL under `[tool.uv.sources]`:

```toml
[tool.uv.sources]
overture-maps = { url = "https://github.com/wiskani/overture-maps/releases/download/v0.1.3/overture_maps-0.1.3-py3-none-any.whl" }
```

Then run `uv sync` in the backend to install the new version.

## Overture Maps schema compatibility

This release (`0.1.3`) was built and tested against:

| Field            | Value          |
| ---------------- | -------------- |
| `data_release`   | `2024-11-13.0` |
| `schema_version` | `1.0.0`        |

## Updating for a new Overture release

1. Edit `overture.yaml`: update `data_release` and `schema_version`.
2. Delete cached parquet files (or re-download to a fresh `data/` directory).
3. Re-run `overture-load`.
4. Run `overture-health` to verify the new schema is compatible.
