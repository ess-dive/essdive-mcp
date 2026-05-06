#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
SOURCE_SKILLS_DIR="$ROOT_DIR/.agents/skills"

SKILLS=(
  essdive-datasets
  essdive-identifiers
  essdive-data-citations
  essdeepdive
)

for skill in "${SKILLS[@]}"; do
  if [[ ! -f "$SOURCE_SKILLS_DIR/$skill/SKILL.md" ]]; then
    echo "Missing SKILL.md for $skill at $SOURCE_SKILLS_DIR/$skill/SKILL.md" >&2
    exit 1
  fi
done

mkdir -p "$CODEX_SKILLS_DIR"

for skill in "${SKILLS[@]}"; do
  ln -sfn "$SOURCE_SKILLS_DIR/$skill" "$CODEX_SKILLS_DIR/$skill"
done

echo "Installed Codex skills into: $CODEX_SKILLS_DIR"
