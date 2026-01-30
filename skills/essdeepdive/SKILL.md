---
name: essdeepdive
description: Query the ESS-DeepDive fusion database for fields and file metadata via MCP tools.
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

- `search-ess-deepdive`
- `get-ess-deepdive-dataset`
- `get-ess-deepdive-file`

## Usage examples

Search for fields named "temperature" with at least 100 records:

```
search-ess-deepdive with field_name="temperature" and record_count_min=100
```

Filter by DOI and field definition text:

```
search-ess-deepdive with doi="10.15485/2453885" and field_definition="soil" and page_size=25
```

Get detailed field metadata for a dataset file:

```
get-ess-deepdive-dataset with doi="10.15485/2453885" and file_path="dataset.zip/data.csv"
```

Get full file metadata and download info:

```
get-ess-deepdive-file with doi="doi:10.15485/2453885" and file_path="dataset.zip/data.csv"
```

## Notes

- `row_start` is 1-based. Use `max_pages` for automatic pagination.
- `doi` may be provided as `10.xxxx/...` or `doi:10.xxxx/...`.
