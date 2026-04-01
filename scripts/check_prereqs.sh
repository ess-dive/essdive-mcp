#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

status_ok() {
  printf '[OK] %s\n' "$1"
}

status_warn() {
  printf '[MISSING] %s\n' "$1"
}

status_info() {
  printf '[INFO] %s\n' "$1"
}

check_python() {
  local python_cmd=""
  if has_cmd python3; then
    python_cmd="python3"
  elif has_cmd python; then
    python_cmd="python"
  fi

  if [[ -z "$python_cmd" ]]; then
    status_warn "Python 3.10+ is not installed or not on PATH."
    status_info "Install Python from https://www.python.org/downloads/ and reopen your terminal."
    return 1
  fi

  local version_output
  version_output="$("$python_cmd" --version 2>&1 || true)"
  local version
  version="$(printf '%s\n' "$version_output" | awk '{print $2}')"

  if "$python_cmd" - <<'PY' "$MIN_PYTHON_MAJOR" "$MIN_PYTHON_MINOR"
import sys
major = int(sys.argv[1])
minor = int(sys.argv[2])
sys.exit(0 if sys.version_info >= (major, minor) else 1)
PY
  then
    status_ok "Python detected: $version_output"
    return 0
  fi

  status_warn "Python is installed, but version $version is too old. Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ is required."
  status_info "Install a newer version from https://www.python.org/downloads/ and reopen your terminal."
  return 1
}

check_uv() {
  if has_cmd uv; then
    status_ok "uv detected: $(uv --version)"
    return 0
  fi

  status_warn "uv is not installed or not on PATH."
  status_info "Install uv from https://docs.astral.sh/uv/"
  status_info "macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh"
  status_info 'Windows PowerShell: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
  return 1
}

check_git() {
  if has_cmd git; then
    status_ok "git detected: $(git --version)"
    return 0
  fi

  status_warn "git is not installed or not on PATH."
  status_info "git is only needed if you want to clone the repository from the command line."
  status_info "You can also download the repository as a ZIP file from GitHub."
  return 1
}

check_token_file() {
  local token_file="$ROOT_DIR/essdivetoken"
  if [[ -f "$token_file" ]] && [[ -s "$token_file" ]]; then
    status_ok "Token file found at $token_file"
  else
    status_info "No token file found yet at $token_file"
    status_info "Create one later with ./scripts/save_token.sh"
  fi
}

main() {
  local failures=0

  printf 'Checking prerequisites for essdive-mcp in %s\n\n' "$ROOT_DIR"

  check_python || failures=$((failures + 1))
  check_uv || failures=$((failures + 1))
  check_git || true
  check_token_file

  printf '\n'
  if [[ "$failures" -eq 0 ]]; then
    status_ok "Required prerequisites look good."
  else
    status_warn "Some required prerequisites are missing."
    exit 1
  fi
}

main "$@"
