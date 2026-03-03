# tmux-agent-view-for-opencode

OpenCodeのサブエージェント実行をtmuxペーンで可視化するためのv1.2実装です。

## できること

- サブエージェント起動時にペーンを自動作成
- 親(Orchestrator)を主表示として維持
- サブエージェント完了時にペーンを自動終了
- JSON設定でレイアウトや挙動を調整

## 主要ファイル

- 本体: `tmux_agent_view/bin/agent_pane_manager.py`
- プラグイン: `tmux_agent_view/minimal_tmux_view_plugin.js`
- 設定: `tmux_agent_view/config/default.json`
- プラグイン詳細: `tmux_agent_view/README.plugin.md`

## クイックスタート

1. OpenCodeをtmux内で起動し、ポートとURLを同期

```bash
export OPENCODE_PORT=4096
export TMUX_VIEW_SERVER_URL=http://127.0.0.1:4096
opencode --port 4096
```

2. `~/.config/opencode/plugins/` からプラグインが読み込まれる状態で、
   Orchestratorがサブエージェントを並列起動するタスクを実行

3. 追加の起動簡略化をしたい場合は、ローカル環境側で
   `~/bin/opencode-tmux` を用意して上記3コマンドをラップ

## 注意

- 複数インスタンスを同時運用する場合はポート競合に注意してください。
- `TMUX_VIEW_SERVER_URL` と `opencode --port` は同じポートに揃えてください。

## ライセンス

必要に応じてこのリポジトリに追加してください。
