#!/usr/bin/env bash
set -euo pipefail

CODEX_SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"

rm -f "$CODEX_SKILLS_DIR/essdive-datasets"
rm -f "$CODEX_SKILLS_DIR/essdive-identifiers"
rm -f "$CODEX_SKILLS_DIR/essdeepdive"

echo "Removed Codex skill links from: $CODEX_SKILLS_DIR"
