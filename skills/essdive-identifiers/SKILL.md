---
name: essdive-identifiers
description: Convert between ESS-DIVE dataset IDs and DOIs via MCP tools.
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

- `doi-to-essdive-id`
- `essdive-id-to-doi`
- `coords-to-map-links`

## Usage examples

Convert a DOI to an ESS-DIVE ID:

```
doi-to-essdive-id with doi="10.15485/2453885"
```

Convert an ESS-DIVE ID to a DOI:

```
essdive-id-to-doi with essdive_id="ess-dive-9ea5fe57db73c90-20241024T093714082510"
```

Create map links for a point (geojson.io + Google Maps + Google Earth KML):

```
coords-to-map-links with points=[[38.9219, -106.9490]] and zoom=12
```

## Notes

- DOI inputs can include prefixes or URLs (e.g., `doi:10.15485/...` or `https://doi.org/...`).
- Outputs return a normalized DOI format.

## Fallback (no MCP server)

If the MCP server is unavailable, resolve identifiers by first fetching dataset metadata from the ESS-DIVE API and extracting the DOI field:

```bash
curl -sG "https://api.ess-dive.lbl.gov/packages/REPLACE_WITH_PACKAGE_ID" \
  -H "Accept: application/json" \
  -H "User-Agent: Mozilla/5.0" \
  -H "Range: bytes=0-1000" \
  --data-urlencode "isPublic=true"
```
