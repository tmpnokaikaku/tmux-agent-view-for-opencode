#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_MANAGER="$SCRIPT_DIR/agent_pane_manager.py"

has_spawn=0
for arg in "$@"; do
  if [[ "$arg" == "spawn" ]]; then
    has_spawn=1
    break
  fi
done

if [[ "$has_spawn" -eq 0 ]]; then
  exec python3 "$REAL_MANAGER" "$@"
fi

new_args=()
skip_next=0
for arg in "$@"; do
  if [[ "$skip_next" -eq 1 ]]; then
    skip_next=0
    continue
  fi
  if [[ "$arg" == "--cmd" ]]; then
    new_args+=("--cmd" "sleep 6")
    skip_next=1
    continue
  fi
  new_args+=("$arg")
done

exec python3 "$REAL_MANAGER" "${new_args[@]}"
