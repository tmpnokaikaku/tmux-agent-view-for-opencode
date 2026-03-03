# minimal_tmux_view_plugin (v1.2)

Orchestrator内部のイベントを受けて、`tmux_agent_view/bin/agent_pane_manager.py` を呼び出すプラグインです。
ユーザー手動コマンドなしで、子セッションのtmuxペーン起動と終了処理を行います。

## イベント対応表

| event | 条件 | 実行内容 |
| --- | --- | --- |
| `session.created` | `session.parentID` がある(子セッション) | `spawn --task-id <session.id> --agent <info.title or subagent> --cmd "opencode attach <serverUrl> --session <session.id>"` |
| `session.status` | `status.type === "idle"` かつ spawn済みsession | `finish --task-id <session.id> --status done` |
| `session.deleted` | spawn済みsession | `finish --task-id <session.id> --status done` を試行 |

補足:
- 重複起動防止のため、セッションIDごとの起動済み状態をメモリ内`Map`で保持します。
- プラグイン初期化時に `init` を1回呼びます。失敗しても処理は継続します。

## 環境変数

- `TMUX_VIEW_ENABLED` (default: `true`)
  - `false`/`0`/`off`/`no` の場合は無効化。
- `TMUX_VIEW_PYTHON` (default: `python3`)
  - Python実行バイナリ。
- `TMUX_VIEW_MANAGER` (default: `~/.config/opencode/plugins/tmux_agent_view/bin/agent_pane_manager.py`)
  - マネージャースクリプトのパス。
- `TMUX_VIEW_CONFIG` (optional)
  - 指定時のみ `--config <path>` を付与。
- `TMUX_VIEW_SERVER_URL` (optional)
  - `opencode attach` 先URLを明示指定する。ポート固定運用時に有効。
- `TMUX_VIEW_DEBUG` (optional)
  - `1`/`true` でデバッグログをstderrへ出力。

## 最小導入手順

1. `tmux_agent_view/minimal_tmux_view_plugin.js` を `~/.config/opencode/plugins/` 配下で読み込めるように配置する。
2. 実配置のマネージャーパスを `TMUX_VIEW_MANAGER` で指定する(例: `~/.config/opencode/plugins/tmux_agent_view/bin/agent_pane_manager.py`)。
3. `OPENCODE_PORT` と `TMUX_VIEW_SERVER_URL` を合わせて `opencode --port <port>` で起動する。
4. Orchestratorを再起動し、子セッション作成時にtmuxペーンが増えることを確認する。

## 制約

- 最小実装のため、起動済み判定`Map`はプロセス再起動で消失します。
- `serverUrl` がイベントから取得できない場合、`spawn` はスキップされます。
- 子セッションの `agent` 推定は `info.title` を優先し、未設定時は `subagent` 固定です。
- tmux分割は `TMUX` 環境変数がある実行環境でのみ有効です。tmux外では安全にスキップされます。
- `opencode` をランダムポートで起動すると attach先がずれて失敗する場合があります。`OPENCODE_PORT` と `--port` を一致させるか、`TMUX_VIEW_SERVER_URL` を設定してください。
