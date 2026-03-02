#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPAWNER="$SCRIPT_DIR/spawn_subagent.sh"

agent=""
task_id=""
config_path=""
mode="auto"

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
    --mode)
      mode="$2"
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

if [[ "$mode" != "auto" && "$mode" != "tmux" && "$mode" != "direct" ]]; then
  echo "error: --mode must be one of auto|tmux|direct" >&2
  exit 2
fi

if [[ "$mode" == "direct" || ("$mode" == "auto" && -z "${TMUX:-}") ]]; then
  exec "$@"
fi

spawner_args=(--agent "$agent")
if [[ -n "$task_id" ]]; then
  spawner_args+=(--task-id "$task_id")
fi
if [[ -n "$config_path" ]]; then
  spawner_args+=(--config "$config_path")
fi

exec "$SPAWNER" "${spawner_args[@]}" -- "$@"
