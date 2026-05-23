# overture-maps

Python library that loads Overture Maps data for a configured bounding box into PostGIS and exposes spatial query functions. Used by the TSB backend — installed as a `.whl`, no HTTP service.

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
# Edit overture.yaml with your city, bbox, data_release, and schema_version
```

## Loading data

### 1. Download GeoParquet files

Download each theme using the `overturemaps` CLI. Substitute the bbox and release for your city:

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
docker compose up -d overture_db_test   # or your own PostGIS instance
```

### 3. Run the load command

```bash
uv run overture-load --data-dir=data \
  --dsn=postgresql://overture:overture@localhost:7003/overture
```

The load script creates (or recreates) the `reference` schema and all tables, then inserts all rows from the downloaded parquet files. It is idempotent: re-running drops and reloads.

## CLI usage

All commands print JSON to stdout. Set `OVERTURE_DB_URL` to point at your database, or use the default (`postgresql+asyncpg://overture:overture@localhost:7002/overture`).

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

## Running tests

The test suite requires the `overture_db_test` container (port 7003) running:

```bash
docker compose up -d
uv run pytest tests/ -v
```

Parquet files are downloaded on the first run and cached in `tests/data/`. Subsequent runs are fast.

## Building the .whl

```bash
uv build
```

The wheel is written to `dist/overture_maps-<version>-py3-none-any.whl`.

## Overture Maps schema compatibility

This release (`0.1.0`) was built and tested against:

| Field            | Value          |
| ---------------- | -------------- |
| `data_release`   | `2024-11-13.0` |
| `schema_version` | `1.0.0`        |

When upgrading to a newer Overture release, update both values in `overture.yaml` and follow the steps below.

## Updating for a new Overture release

1. Edit `overture.yaml`: update `data_release` and `schema_version`.
2. Delete cached parquet files (or re-download to a fresh `data/` directory).
3. Re-run `overture-load`.
4. Run `overture-health` to verify the new schema is compatible.
