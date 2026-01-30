#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"

for skill in essdive-datasets essdive-identifiers essdeepdive; do
  if [[ ! -f "$ROOT_DIR/skills/$skill/SKILL.md" ]]; then
    echo "Missing SKILL.md for $skill at $ROOT_DIR/skills/$skill/SKILL.md" >&2
    exit 1
  fi
done

mkdir -p "$CODEX_SKILLS_DIR"

ln -sfn "$ROOT_DIR/skills/essdive-datasets" "$CODEX_SKILLS_DIR/essdive-datasets"
ln -sfn "$ROOT_DIR/skills/essdive-identifiers" "$CODEX_SKILLS_DIR/essdive-identifiers"
ln -sfn "$ROOT_DIR/skills/essdeepdive" "$CODEX_SKILLS_DIR/essdeepdive"

echo "Installed Codex skills into: $CODEX_SKILLS_DIR"
