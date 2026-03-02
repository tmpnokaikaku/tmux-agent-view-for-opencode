#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEST_ROOT="${HOME}/.config/opencode/plugins/tmux_agent_view"
TOP_LEVEL_PLUGIN="${HOME}/.config/opencode/plugins/minimal_tmux_view_plugin.js"

mkdir -p "$DEST_ROOT/bin" "$DEST_ROOT/config"

cp "$APP_ROOT/plugin/minimal_tmux_view_plugin.js" "$DEST_ROOT/minimal_tmux_view_plugin.js"
cp "$APP_ROOT/plugin/minimal_tmux_view_plugin.js" "$TOP_LEVEL_PLUGIN"
cp "$APP_ROOT/plugin/README.md" "$DEST_ROOT/README.plugin.md"
cp "$APP_ROOT/bin/agent_pane_manager.py" "$DEST_ROOT/bin/agent_pane_manager.py"
cp "$APP_ROOT/config/default.json" "$DEST_ROOT/config/default.json"

chmod +x "$DEST_ROOT/bin/agent_pane_manager.py"

printf 'installed: %s\n' "$DEST_ROOT"
printf 'plugin: %s\n' "$DEST_ROOT/minimal_tmux_view_plugin.js"
printf 'top-level-plugin: %s\n' "$TOP_LEVEL_PLUGIN"
printf 'manager: %s\n' "$DEST_ROOT/bin/agent_pane_manager.py"
