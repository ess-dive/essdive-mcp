---
name: essdive-data-citations
description: Generate consistent ESS-DIVE data citations with repository, project/provider, DOI, and MCP/API access details from dataset IDs, DOIs, or metadata; warn and use Crossref fallback for non-ESS-DIVE DOIs.
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

# Tools

- `generate-data-citation`
- `get-dataset`
- `doi-to-essdive-id`
- `essdive-id-to-doi`

The Crossref fallback is internal to `generate-data-citation`; there is no
separate Crossref MCP tool to call.

## Usage examples

Generate a citation from a DOI:

```
generate-data-citation with id="doi:10.15485/3014404"
```

Generate a reproducible citation with an explicit access date:

```
generate-data-citation with id="doi:10.15485/3014404" and access_date="2026-05-06"
```

Override the default access method when the citation should describe another
workflow:

```
generate-data-citation with id="doi:10.15485/3014404" and access_date="2026-05-06" and access_method="custom export workflow"
```

Use already-fetched metadata instead of requesting the dataset again:

```
get-dataset with id="doi:10.15485/3014404" and format="raw"
generate-data-citation with dataset_metadata=PASTE_RAW_DATASET_METADATA and access_date="2026-05-06"
```

Generate a warning-backed citation for a non-ESS-DIVE DOI:

```
generate-data-citation with id="doi:10.1038/nature12373" and access_date="2026-05-06"
```

## Expected output shape

The citation should follow this shape:

```text
Creator Family Initials ; Creator Family Initials (YEAR): Dataset title. Provider, ESS-DIVE repository. Dataset. doi:10.xxxx/xxxx accessed via ESS-DIVE API over ESS-DIVE MCP on YYYY-MM-DD
```

Example:

```text
Breckheimer I ; Carroll E ; Chadwick K D ; Falco N ; Henderson A ; Lovegreen P ; O'Ryan D ; Todorov S ; Villa A ; Williams C ; Worsham H M ; Xu H (2026): CHESS 2025: Field-collected vegetation attributes and site photos. Watershed Function SFA, ESS-DIVE repository. Dataset. doi:10.15485/3014404 accessed via ESS-DIVE API over ESS-DIVE MCP on 2026-05-06
```

If the DOI is not an ESS-DIVE DOI, the output should start with a warning and
then use Crossref metadata:

```text
WARNING: doi:10.1038/nature12373 is not an ESS-DIVE DOI; citation was generated from Crossref metadata and may not describe an ESS-DIVE dataset.

Kucsko G ; Maurer P C ; Yao N Y ; Kubo M ; Noh H J ; Lo P K ; Park H ; Lukin M D (2013): Nanometre-scale thermometry in a living cell. Nature. Journal article. doi:10.1038/nature12373 accessed via Crossref API over ESS-DIVE MCP on 2026-05-06
```

## Notes

- Prefer `generate-data-citation` whenever the user asks how to cite an ESS-DIVE dataset or when an export/report should include a dataset citation.
- Pass `access_date` when the output needs to be reproducible. Otherwise the tool uses the MCP server's current date.
- The default access phrase is `ESS-DIVE API over ESS-DIVE MCP`.
- `id` may be an ESS-DIVE package ID or a DOI in common DOI forms.
- If another workflow already has the raw `get-dataset` payload, pass it as `dataset_metadata` to avoid an extra API request.
- Use `doi-to-essdive-id` or `essdive-id-to-doi` first only when the user explicitly needs identifier conversion; `generate-data-citation` can fetch citation metadata directly from either a package ID or DOI.
- For non-ESS-DIVE DOIs, preserve the warning in the final answer so the user can notice that a non-ESS-DIVE reference is present.
- Invalid or unknown DOIs should return an error rather than a fabricated citation.

## Fallback (no MCP server)

If the MCP server is unavailable, fetch the dataset metadata from the ESS-DIVE
API and construct the same citation shape from `dataset.creator`,
`dataset.datePublished`, `dataset.name`, `dataset.provider.name`, and
`dataset.@id`:

```bash
curl -sG "https://api.ess-dive.lbl.gov/packages/doi%3A10.15485%2F3014404" \
  -H "Accept: application/json" \
  -H "User-Agent: Mozilla/5.0" \
  -H "Range: bytes=0-1000" \
  --data-urlencode "isPublic=true"
```
