# Hosted Streamable HTTP Setup

This guide covers the more technical deployment path for running `essdive-mcp` as a hosted MCP server over streamable HTTP.

Most users do not need this page. If you are using Goose Desktop, Codex, Claude Code, or VS Code locally, the `stdio` setup in the main [README](../README.md) is usually the right starting point.

Use this guide when you want to:

- run `essdive-mcp` in a container
- expose the MCP server from a hosted environment
- use streamable HTTP instead of local `stdio`

## Run Locally Over Streamable HTTP

Start the server with streamable HTTP transport:

```bash
uv run essdive-mcp --transport streamable-http --host 0.0.0.0 --port 8000 --path /mcp
```

## Transport Options

- `--transport stdio` keeps the default local-client workflow.
- `--transport streamable-http` enables hosted MCP over HTTP.
- `--host`, `--port`, and `--path` control the bind address and MCP endpoint path.
- `--json-response` enables JSON response mode for streamable HTTP.
- `--stateless-http` disables sessionful streamable HTTP behavior when each request should be handled independently.

## Environment Variables

The same settings can be supplied through environment variables:

```bash
ESSDIVE_MCP_TRANSPORT=streamable-http
ESSDIVE_MCP_HOST=0.0.0.0
ESSDIVE_MCP_PORT=8000
ESSDIVE_MCP_PATH=/mcp
ESSDIVE_MCP_JSON_RESPONSE=false
ESSDIVE_MCP_STATELESS_HTTP=false
```

## Docker

Build the image:

```bash
docker build -t essdive-mcp .
```

Run the container:

```bash
docker run --rm -p 8000:8000 \
  -e ESSDIVE_MCP_TRANSPORT=streamable-http \
  -e ESSDIVE_MCP_HOST=0.0.0.0 \
  -e ESSDIVE_MCP_PORT=8000 \
  essdive-mcp
```

## Notes

- The default container command already starts `essdive-mcp` with `streamable-http` on port `8000` and path `/mcp`.
- If you need authenticated/private-data access, also pass `ESSDIVE_API_TOKEN` into the container.
- Session-scoped pagination state is stored in memory. That works for a single server instance, but a future multi-replica deployment would still need shared state such as Redis.
