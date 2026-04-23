---
name: essdive-datasets
description: Search ESS-DIVE datasets, fetch metadata/version history/status/permissions, and parse FLMD via MCP tools.
---

# Setup (once)

Run the MCP server locally:

```bash
uv run python src/essdive_mcp/main.py
```

If you need authenticated/private-data access, provide a token explicitly:

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
claude mcp add --transport stdio essdive-mcp -- uv run python ./src/essdive_mcp/main.py
```

If you need authenticated/private-data access, add a token:

```bash
claude mcp add --transport stdio essdive-mcp --env ESSDIVE_API_TOKEN=YOUR_ESS_DIVE_TOKEN_HERE -- uv run python ./src/essdive_mcp/main.py
```

Token file alternative:

```bash
claude mcp add --transport stdio essdive-mcp -- uv run python ./src/essdive_mcp/main.py --token-file /path/to/token.txt
```

# Tools

- `search-datasets`
- `next-search-page`
- `previous-search-page`
- `get-dataset`
- `get-dataset-versions`
- `next-dataset-versions-page`
- `previous-dataset-versions-page`
- `get-dataset-status`
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

Sort results by one or more API-supported fields:

```
search-datasets with query="soil carbon" and sort="name:asc"
```

```
search-datasets with query="soil carbon" and sort="dateUploaded:desc,authorLastName:asc"
```

Follow a search cursor to the next page:

```
search-datasets with query="BIONTE" and sort="name:asc" and page_size=2
```

Then use the returned `nextCursor` or `previousCursor`:

```
search-datasets with query="BIONTE" and sort="name:asc" and cursor="PASTE_NEXT_OR_PREVIOUS_CURSOR_HERE"
```

For conversational pagination, prefer the stateful MCP wrapper instead of exposing cursors:

```
next-search-page
```

Or go back:

```
previous-search-page
```

If you need direct access to the raw pagination metadata, request raw form:

```
search-datasets with query="BIONTE" and sort="name:asc" and page_size=2 and format="raw"
```

Then summarize the page yourself, and if the user asks for the next page, rerun the same search with the returned `nextCursor` unchanged:

```
search-datasets with query="BIONTE" and sort="name:asc" and cursor="PASTE_NEXT_CURSOR_HERE" and format="raw"
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

Live-checked examples on April 2, 2026:

```
search-datasets with query="East River" and creator_affiliation="Lawrence Berkeley National Laboratory" and page_size=5
```

This narrowed the first page from 5 native results down to 3 local matches.

```
search-datasets with query="East River" and variable_measured="streamflow" and page_size=5
```

This narrowed the same first page down to 1 local match.

```
search-datasets with query="East River" and funder="NASA" and page_size=5
```

This also narrowed the same first page down to 1 local match.

Look up a project acronym and its portal details:

```
lookup-project-portal with query="CHESS"
```

Get detailed metadata for a dataset:

```
get-dataset with id="ess-dive-9ea5fe57db73c90-20241024T093714082510"
```

Return the raw dataset payload when you need exact top-level API fields such as
`isPublic`, `dateUploaded`, `dateModified`, `citation`, or `viewUrl`:

```
get-dataset with id="doi:10.15485/2529445" and format="raw"
```

Check publication/workflow status for a dataset:

```
get-dataset-status with id="ess-dive-f78cb03d11550da-20260309T160313214"
```

List version history from newest to oldest:

```
get-dataset-versions with id="doi:10.15485/2529445" and page_size=2
```

Follow a version-history cursor:

```
get-dataset-versions with id="doi:10.15485/2529445" and cursor="PASTE_NEXT_OR_PREVIOUS_CURSOR_HERE"
```

For conversational pagination through version history, prefer the stateful MCP wrappers:

```
next-dataset-versions-page
```

```
previous-dataset-versions-page
```

If you need direct access to the raw pagination metadata, prefer raw mode on the first call:

```
get-dataset-versions with id="doi:10.15485/2529445" and page_size=2 and format="raw"
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
- Use `get-dataset-status` when the user asks for dataset status. Do not infer status from `get-dataset`.
- If the user asks for the status of multiple datasets, call `get-dataset-status` once per dataset identifier and summarize the results.
- `get-dataset-status` may require an ESS-DIVE API token and dataset access. If an anonymous call fails, explain that status is auth-gated.
- `get-dataset` supports `format="raw"` when you need the exact response fields, including top-level `isPublic`.
- `page_size` max is 100.
- `cursor` is the preferred way to page through search results. `row_start` is still supported for compatibility but is legacy.
- Search and version responses include an integer `total` plus `nextCursor` and `previousCursor` when pagination is available.
- `next-search-page` and `previous-search-page` page through the most recent `search-datasets` request without requiring the caller to pass cursors.
- For cursor follow-up searches, omit `cursor` on the first request, then pass the returned `nextCursor` or `previousCursor` value unchanged on later requests. Reuse the same search filters and omit `page_size` unless you know it matches the cursor's encoded page size.
- For a conversational “show me the next page” flow, prefer the stateful next/previous page tools. Use raw mode only when you explicitly need to inspect or persist the API cursor values.
- `sort` accepts comma-separated `field:direction` clauses. Supported fields: `name`, `dateUploaded`, `authorLastName`. Supported directions: `asc`, `desc`.
- `get-dataset-versions` lists visible versions from newest to oldest and supports cursor pagination.
- `next-dataset-versions-page` and `previous-dataset-versions-page` page through the most recent `get-dataset-versions` request without requiring the caller to pass cursors.
- For `get-dataset-versions`, omit `page_size` on cursor follow-up calls unless you know it matches the cursor's encoded page size. As with search, pass returned cursor values unchanged.
- `bbox` uses `[min_lat, min_lon, max_lat, max_lon]` ordering and can also be passed as a comma-delimited string.
- Point search requires `lat`, `lon`, and `radius` together. Do not combine point search with `bbox`.
- Native ESS-DIVE `/packages` filters include `query`/`text`, `creator`, `provider_name`, `date_published`, `begin_date`, `end_date`, `keywords`, `sort`, `bbox`, and `lat`/`lon`/`radius`.
- Additional filters such as `creator_affiliation`, `variable_measured`, `measurement_technique`, `funder`, `license`, `alternate_name`, `editor`, `file_format`, `file_name`, and `file_url` are applied locally after the initial API search using full dataset metadata from `get-dataset`.
- If you need very precise filtering on those local-only fields, start with a narrower native search first, then apply the local metadata filters.
- Local metadata filtering only inspects the current API page, so increase `page_size` or adjust `row_start` if you want to scan more native matches.
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

Follow a dataset-search cursor directly against the API:

```bash
curl -sG "https://api.ess-dive.lbl.gov/packages" \
  -H "Accept: application/json" \
  --data-urlencode "text=BIONTE" \
  --data-urlencode "sort=name:asc" \
  --data-urlencode "cursor=PASTE_NEXT_OR_PREVIOUS_CURSOR_HERE" \
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

Fetch dataset version history by DOI or package ID:

```bash
curl -sG "https://api.ess-dive.lbl.gov/packages/doi%3A10.15485%2F2529445/versions" \
  -H "Accept: application/json" \
  --data-urlencode "pageSize=2"
```
