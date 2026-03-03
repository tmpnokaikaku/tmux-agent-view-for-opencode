#!/usr/bin/env bash
set -euo pipefail

PORT="${OPENCODE_PORT:-4096}"
SESSION_NAME="opencode-tmux"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --session-name)
      SESSION_NAME="$2"
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

if ! command -v tmux >/dev/null 2>&1; then
  echo "error: tmux is not installed" >&2
  exit 2
fi

export OPENCODE_PORT="$PORT"
export TMUX_VIEW_SERVER_URL="${TMUX_VIEW_SERVER_URL:-http://127.0.0.1:${PORT}}"

if [[ -n "${TMUX:-}" ]]; then
  exec opencode --port "$PORT" "$@"
fi

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  exec tmux attach -t "$SESSION_NAME"
fi

CMD="OPENCODE_PORT=$PORT TMUX_VIEW_SERVER_URL=$TMUX_VIEW_SERVER_URL opencode --port $PORT"
if [[ $# -gt 0 ]]; then
  for arg in "$@"; do
    CMD+=" $(printf '%q' "$arg")"
  done
fi

tmux new-session -d -s "$SESSION_NAME" "$CMD"
exec tmux attach -t "$SESSION_NAME"
