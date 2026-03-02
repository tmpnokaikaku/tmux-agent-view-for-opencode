# tmux_agent_view

tmuxの非プラグイン運用で、Orchestratorを主表示に維持しながらサブエージェント用ペーンを管理するMVPです。

## 設定

- 設定ファイル: `tmux_agent_view/config/default.json`
- 必要に応じて `--config /path/to/config.json` で上書きできます。

主要キー:

- `enabled`: 機能の有効/無効
- `layout`: `main-vertical` などのtmuxレイアウト
- `main_pane_size`: 主ペーンサイズ(`main-pane-width` または `main-pane-height`)
- `split`: `auto` / `right` / `bottom`
- `kill_on_finish`: `finish` 時に子ペーンをkillするか
- `min_pane_lifetime_seconds`: 生成から最低何秒はペーンを表示するか(短時間タスクでの見え消え防止)
- `auto_finish_hook`: `start` したコマンド完了時に `finish` を自動実行するか
- `install_pane_exit_hook`: `pane-exited` フックを設定して `reap` を自動実行するか
- `title_prefix`: 子ペーンタイトル先頭文字列
- `state_dir`: 状態JSONの保存先ディレクトリ

## 使い方(基本6コマンド)

```bash
# 1) 親ペーンを初期化
tmux_agent_view/bin/agent_pane_manager.sh init

# 2) サブエージェント開始(子ペーン作成)
tmux_agent_view/bin/agent_pane_manager.sh start --task-id task-001 --agent coder-a --cmd "sleep 30"

# 3) 状態確認(JSON表示)
tmux_agent_view/bin/agent_pane_manager.sh status

# 4) 終了済みペーンの再収穫(保険)
tmux_agent_view/bin/agent_pane_manager.sh reap

# 5) サブエージェント終了処理(設定で自動kill)
tmux_agent_view/bin/agent_pane_manager.sh finish --task-id task-001 --status done

# 6) 後始末(残り子ペーンkill + 状態掃除)
tmux_agent_view/bin/agent_pane_manager.sh cleanup
```

## Orchestrator連携(1箇所差し込み)

Orchestratorのサブエージェント起動点で、`start` の代わりに `spawn` を呼ぶと
`init` 相当を内包して起動できます。

```bash
tmux_agent_view/bin/agent_pane_manager.sh spawn \
  --agent coder-a \
  --cmd "sleep 5"
```

- `--task-id` 省略時は自動採番されます。
- `auto_finish_hook=true` と `install_pane_exit_hook=true` の場合、終了後の状態回収は自動で進みます。

既存コマンドを置き換える場合は `spawn_subagent.sh` が便利です。

```bash
tmux_agent_view/bin/spawn_subagent.sh --agent coder-a -- sleep 5
```

- 先頭の引数(`--agent`など)はラッパー用、`--` 以降が子ペーンで実行される実コマンドです。
- このラッパーをOrchestratorの起動点に1回差し込めば、ユーザーが `start/finish` を毎回手動実行する必要はありません。

さらに、tmux有無を自動判定して同一呼び出しを使いたい場合は `run_subagent.sh` を使います。

```bash
tmux_agent_view/bin/run_subagent.sh --agent coder-a --mode auto -- sleep 5
```

- `--mode auto`: tmux内なら分割実行、tmux外なら直接実行。
- `--mode tmux`: tmux分割を強制。
- `--mode direct`: 常に直接実行。

## 想定フロー

- Orchestrator起動直後に `init` を1回実行
- サブエージェント起動時に `start --task-id --agent --cmd` を呼ぶ
- サブエージェント完了通知を受けて `finish --task-id` を呼ぶ
- 通常は `pane-exited` フックで `reap` が自動実行される(必要なら手動 `reap` も可能)
- セッション終了前に `cleanup` で掃除する

`start/finish/cleanup` 後は、親ペーンを再選択し `layout` を再適用します。
`auto_finish_hook=true` の場合、`start` で起動したコマンドが終了すると `finish` が自動実行されます。

安全策:

- 状態ファイルは排他ロックとatomic保存で更新します。
- `finish/cleanup` の `kill-pane` は `session/window/title` の一致確認を通った場合のみ実行します。
- 同じ `task_id` が実行中の場合、`start` は `conflict` を返して二重起動を拒否します。

## 2台目PC展開手順(短縮版)

1. この `tmux_agent_view/` ディレクトリを同じ相対パスで配置する。
2. `python3` と `tmux` が使えることを確認する。
3. 必要なら `config/default.json` を編集する。
4. `python3 -m py_compile tmux_agent_view/bin/agent_pane_manager.py` を実行して検証する。
5. tmux内で `init` から動作確認する。

## プラグイン統合

Orchestrator内部の自動起動イベントにフックする最小プラグインを追加しました。

- プラグイン本体: `tmux_agent_view/plugin/minimal_tmux_view_plugin.js`
- プラグイン説明: `tmux_agent_view/plugin/README.md`
- 配置スクリプト: `tmux_agent_view/bin/install_to_opencode_plugins.sh`

このプラグインは、`session.created/status/deleted` を受けて
`agent_pane_manager.py` の `spawn/finish` を呼び出します。
初期化時には `init` を1回試行し、失敗しても継続します。

実運用では、`~/.config/opencode/plugins/tmux_agent_view/` へ配置して
`~/.config/opencode/plugins/tmux_agent_view/minimal_tmux_view_plugin.js` を読み込みます。
