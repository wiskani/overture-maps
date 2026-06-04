# overture-maps

Python library that loads Overture Maps data for a configured bounding box into PostGIS and exposes spatial query functions. Used by the TSB backend — installed via git tag, no HTTP service.

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

## Usage

### OvertureClient (recommended)

`OvertureClient` is the recommended way to use this library programmatically. It accepts a DSN string and manages the database connection internally — no SQLAlchemy imports required on the caller side.

```python
from overture_maps import OvertureClient

client = OvertureClient(dsn="postgresql+asyncpg://user:password@localhost:7003/overture")

# Find nearest addresses to a point
results = await client.nearby_addresses(lat=-17.389, lon=-66.157)
for r in results:
    print(r.address.street, r.distance_meters)

# Find nearest streets (for areas without address coverage)
results = await client.streets_near_place(lat=-17.389, lon=-66.157)

# Get administrative divisions containing a point
divisions = await client.divisions_containing_point(lat=-17.389, lon=-66.157)
```

Connection pool options (all optional):

```python
client = OvertureClient(
    dsn="postgresql+asyncpg://...",
    pool_size=5,
    max_overflow=2,
    pool_timeout=10,
    pool_recycle=1800,
    statement_timeout=5000,  # milliseconds
)
```

### Available methods

| Method                                          | Return type                  |
| ----------------------------------------------- | ---------------------------- |
| `nearby_addresses(lat, lon)`                    | `list[NearbyAddressResult]`  |
| `get_address_by_id(address_id)`                 | `OvertureAddress \| None`    |
| `street_at_point(lat, lon)`                     | `StreetAtPointResult`        |
| `streets_near_place(lat, lon)`                  | `list[NearbySegmentResult]`  |
| `search_streets(q)`                             | `list[OvertureSegment]`      |
| `get_segment_by_id(segment_id)`                 | `OvertureSegment \| None`    |
| `nearby_places(lat, lon)`                       | `list[NearbyPlaceResult]`    |
| `search_places(q)`                              | `list[OverturePlace]`        |
| `divisions_containing_point(lat, lon)`          | `list[OvertureDivisionArea]` |
| `search_divisions(q)`                           | `list[OvertureDivisionArea]` |
| `streets_in_division(division_id, q)`           | `list[OvertureSegment]`      |
| `health(config)`                                | `dict`                       |

All methods accept an optional `limit: int = 10` parameter where applicable.

### Low-level API (advanced)

If you need to manage session lifecycle yourself (e.g. to share a session across multiple queries in a transaction), the module-level functions are still available. They all require an `AsyncSession` connected to `overture_db`:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from overture_maps import nearby_addresses, divisions_containing_point

async with session_maker() as session:
    results = await nearby_addresses(session, lat=-17.389, lon=-66.157)
    divs = await divisions_containing_point(session, lat=-17.389, lon=-66.157)
```

### Return types

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
    OvertureClient,
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

## Releasing a new version

1. Bump `version` in `pyproject.toml` and commit.
2. Tag the commit and push:
   ```bash
   git tag v<version>
   git push origin master
   git push origin v<version>
   ```
3. Update the TSB backend — in `backend/pyproject.toml` under `[tool.uv.sources]`:
   ```toml
   overture-maps = { git = "https://github.com/wiskani/overture-maps", tag = "v<version>" }
   ```
4. Run `uv lock && uv sync` in the TSB backend.

## Overture Maps schema compatibility

This release (`0.1.5`) was built and tested against:

| Field            | Value          |
| ---------------- | -------------- |
| `data_release`   | `2024-11-13.0` |
| `schema_version` | `1.0.0`        |

## Updating for a new Overture release

1. Edit `overture.yaml`: update `data_release` and `schema_version`.
2. Delete cached parquet files (or re-download to a fresh `data/` directory).
3. Re-run `overture-load`.
4. Run `overture-health` to verify the new schema is compatible.
