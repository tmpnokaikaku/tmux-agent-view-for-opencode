#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANAGER="$SCRIPT_DIR/agent_pane_manager.sh"

agent=""
task_id=""
config_path=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      agent="$2"
      shift 2
      ;;
    --task-id)
      task_id="$2"
      shift 2
      ;;
    --config)
      config_path="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [[ -z "$agent" ]]; then
  echo "error: --agent is required" >&2
  exit 2
fi

if [[ $# -eq 0 ]]; then
  echo "error: subagent command is required (use -- <cmd ...>)" >&2
  exit 2
fi

quoted_cmd=""
for part in "$@"; do
  if [[ -n "$quoted_cmd" ]]; then
    quoted_cmd+=" "
  fi
  quoted_cmd+="$(printf '%q' "$part")"
done

args=(spawn --agent "$agent" --cmd "$quoted_cmd")
if [[ -n "$task_id" ]]; then
  args+=(--task-id "$task_id")
fi
if [[ -n "$config_path" ]]; then
  args=(--config "$config_path" "${args[@]}")
fi

exec "$MANAGER" "${args[@]}"
