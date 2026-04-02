---
name: essdive-datasets
description: Search ESS-DIVE datasets, fetch metadata/permissions, and parse FLMD via MCP tools.
---

# Setup (once)

Run the MCP server locally:

```bash
uv run python src/essdive_mcp/main.py --token YOUR_ESS_DIVE_TOKEN_HERE
```

Or provide the token via a file:

```bash
uv run python src/essdive_mcp/main.py --token-file /path/to/token.txt
```

Note: the environment variable name is `ESSDIVE_API_TOKEN` (no underscore
between ESS and DIVE).

Register with Claude Code (stdio transport):

```bash
claude mcp add --transport stdio essdive-mcp --env ESSDIVE_API_TOKEN=YOUR_ESS_DIVE_TOKEN_HERE -- uv run python ./src/essdive_mcp/main.py
```

Token file alternative:

```bash
claude mcp add --transport stdio essdive-mcp -- uv run python ./src/essdive_mcp/main.py --token-file /path/to/token.txt
```

# Tools

- `search-datasets`
- `get-dataset`
- `get-dataset-permissions`
- `parse-flmd-file`
- `lookup-project-portal`
- `coords-to-map-links`

## Usage examples

Search datasets by keyword:

```
search-datasets with query="soil carbon" and page_size=10
```

Filter by creator and provider:

```
search-datasets with creator="Smith" and provider_name="NGEE Arctic" and page_size=5
```

Filter by temporal coverage:

```
search-datasets with begin_date="2020" and end_date="2021-06" and format="detailed"
```

Filter by bounding box:

```
search-datasets with bbox=[34.0, -119.0, 35.0, -117.0]
```

Filter by nearby point search:

```
search-datasets with lat=37.7749 and lon=-122.4194 and radius=5000
```

Filter by metadata fields that are exposed on full dataset records but not as native
`/packages` API query parameters:

```
search-datasets with query="snowmelt" and creator_affiliation="Pennsylvania" and format="detailed"
```

```
search-datasets with provider_name="SPRUCE" and variable_measured=["temperature", "CO2"]
```

```
search-datasets with funder="Department of Energy" and file_format="csv"
```

Look up a project acronym and its portal details:

```
lookup-project-portal with query="CHESS"
```

Get detailed metadata for a dataset:

```
get-dataset with id="ess-dive-9ea5fe57db73c90-20241024T093714082510"
```

Check sharing permissions (requires token):

```
get-dataset-permissions with id="ess-dive-9ea5fe57db73c90-20241024T093714082510"
```

Parse a File Level Metadata CSV payload:

```
parse-flmd-file with content="filename,file_description\nfile1.csv,Soil moisture data\n"
```

Create map links for a point (geojson.io + Google Maps + Google Earth KML):

```
coords-to-map-links with points=[[38.9219, -106.9490]] and zoom=12
```

Create map links for a bounding box (geojson.io + OpenStreetMap + Google Earth KML):

```
coords-to-map-links with bbox=[38.9187, -106.9532, 38.9263, -106.9451]
```

## Notes

- Use `format="summary"` for compact results, or `format="detailed"` for full metadata.
- `page_size` max is 100; `row_start` is 1-based.
- `bbox` uses `[min_lat, min_lon, max_lat, max_lon]` ordering and can also be passed as a comma-delimited string.
- Point search requires `lat`, `lon`, and `radius` together. Do not combine point search with `bbox`.
- Native ESS-DIVE `/packages` filters include `query`/`text`, `creator`, `provider_name`, `date_published`, `begin_date`, `end_date`, `keywords`, `bbox`, and `lat`/`lon`/`radius`.
- Additional filters such as `creator_affiliation`, `variable_measured`, `measurement_technique`, `funder`, `license`, `alternate_name`, `editor`, `file_format`, `file_name`, and `file_url` are applied locally after the initial API search using full dataset metadata from `get-dataset`.
- If you need very precise filtering on those local-only fields, start with a narrower native search first, then apply the local metadata filters.
- For portal names, acronyms, and URLs, consult `../references/essdive_project_portals.yaml`.

## Fallback (no MCP server)

Search via the ESS-DIVE API:

```bash
curl -sG "https://api.ess-dive.lbl.gov/packages" \
  -H "Accept: application/json" \
  -H "User-Agent: Mozilla/5.0" \
  -H "Range: bytes=0-1000" \
  --data-urlencode "text=soil carbon" \
  --data-urlencode "pageSize=10" \
  --data-urlencode "rowStart=1" \
  --data-urlencode "isPublic=true"
```

Search by temporal coverage and geography directly against the API:

```bash
curl -sG "https://api.ess-dive.lbl.gov/packages" \
  -H "Accept: application/json" \
  --data-urlencode "beginDate=2020" \
  --data-urlencode "endDate=2021-06" \
  --data-urlencode "bbox=34.0,-119.0,35.0,-117.0" \
  --data-urlencode "isPublic=true"
```

Fetch a dataset record by package ID:

```bash
curl -sG "https://api.ess-dive.lbl.gov/packages/REPLACE_WITH_PACKAGE_ID" \
  -H "Accept: application/json" \
  -H "User-Agent: Mozilla/5.0" \
  -H "Range: bytes=0-1000" \
  --data-urlencode "isPublic=true"
```
