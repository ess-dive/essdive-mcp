---
name: essdive-datasets
description: Search ESS-DIVE datasets, fetch metadata/permissions, and parse FLMD via MCP tools.
---

# Setup (once)

Run the MCP server locally:

```bash
uv run python src/essdive_mcp/main.py --token YOUR_ESS_DIVE_TOKEN_HERE
```

Register with Claude Code (stdio transport):

```bash
claude mcp add --transport stdio essdive-mcp --env ESSDIVE_API_TOKEN=YOUR_ESS_DIVE_TOKEN_HERE -- uv run python ./src/essdive_mcp/main.py
```

# Tools

- `search-datasets`
- `get-dataset`
- `get-dataset-permissions`
- `parse-flmd-file`

## Usage examples

Search datasets by keyword:

```
search-datasets with query="soil carbon" and page_size=10
```

Filter by creator and provider:

```
search-datasets with creator="Smith" and provider_name="NGEE Arctic" and page_size=5
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

## Notes

- Use `format="summary"` for compact results, or `format="detailed"` for full metadata.
- `page_size` max is 100; `row_start` is 1-based.

## Fallback (no MCP server)

Search via the ESS-DIVE API:

```bash
curl -sG "https://api.ess-dive.lbl.gov/packages" \
  -H "Accept: application/json" \
  -H "User-Agent: Mozilla/5.0" \
  -H "Range: bytes=0-1000" \
  --data-urlencode "text=soil carbon" \
  --data-urlencode "page_size=10" \
  --data-urlencode "row_start=1" \
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
