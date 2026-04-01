#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOKEN_FILE="${1:-$ROOT_DIR/essdivetoken}"

mkdir -p "$(dirname "$TOKEN_FILE")"

if [[ -f "$TOKEN_FILE" ]]; then
  read -r -p "Overwrite existing token file at $TOKEN_FILE? [y/N] " overwrite
  case "$overwrite" in
    y|Y|yes|YES) ;;
    *)
      echo "Aborted."
      exit 1
      ;;
  esac
fi

read -r -s -p "Paste your ESS-DIVE token, then press Enter: " token
echo

if [[ -z "$token" ]]; then
  echo "No token entered. Aborted." >&2
  exit 1
fi

printf '%s\n' "$token" > "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"

echo "Saved token to $TOKEN_FILE"
