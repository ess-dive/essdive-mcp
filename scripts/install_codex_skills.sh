#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
SOURCE_SKILLS_DIR="$ROOT_DIR/.agents/skills"

for skill in essdive-datasets essdive-identifiers essdeepdive; do
  if [[ ! -f "$SOURCE_SKILLS_DIR/$skill/SKILL.md" ]]; then
    echo "Missing SKILL.md for $skill at $SOURCE_SKILLS_DIR/$skill/SKILL.md" >&2
    exit 1
  fi
done

mkdir -p "$CODEX_SKILLS_DIR"

ln -sfn "$SOURCE_SKILLS_DIR/essdive-datasets" "$CODEX_SKILLS_DIR/essdive-datasets"
ln -sfn "$SOURCE_SKILLS_DIR/essdive-identifiers" "$CODEX_SKILLS_DIR/essdive-identifiers"
ln -sfn "$SOURCE_SKILLS_DIR/essdeepdive" "$CODEX_SKILLS_DIR/essdeepdive"

echo "Installed Codex skills into: $CODEX_SKILLS_DIR"
