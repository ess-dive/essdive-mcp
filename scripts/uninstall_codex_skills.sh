#!/usr/bin/env bash
set -euo pipefail

CODEX_SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"

SKILLS=(
  essdive-datasets
  essdive-identifiers
  essdive-data-citations
  essdeepdive
)

for skill in "${SKILLS[@]}"; do
  rm -f "$CODEX_SKILLS_DIR/$skill"
done

echo "Removed Codex skill links from: $CODEX_SKILLS_DIR"
