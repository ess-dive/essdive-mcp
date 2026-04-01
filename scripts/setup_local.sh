#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

./scripts/check_prereqs.sh

echo
echo "Installing project dependencies with uv..."
uv sync

echo
echo "Setup complete."
echo "Next steps:"
echo "  1. Save your ESS-DIVE token with ./scripts/save_token.sh"
echo "  2. Start the server with ./scripts/start_server.sh"
