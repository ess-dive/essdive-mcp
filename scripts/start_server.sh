#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOKEN_FILE="${ESSDIVE_TOKEN_FILE:-$ROOT_DIR/essdivetoken}"

cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed or not on PATH." >&2
  echo "Run ./scripts/check_prereqs.sh for setup help." >&2
  exit 1
fi

if [[ ! -f "$TOKEN_FILE" ]] || [[ ! -s "$TOKEN_FILE" ]]; then
  echo "Token file not found at $TOKEN_FILE" >&2
  echo "Create one with ./scripts/save_token.sh or set ESSDIVE_TOKEN_FILE." >&2
  exit 1
fi

echo "Starting essdive-mcp using token file: $TOKEN_FILE"
echo "The server will wait for an MCP client connection. Press Ctrl+C to stop."
echo

exec uv run essdive-mcp --token-file "$TOKEN_FILE"
