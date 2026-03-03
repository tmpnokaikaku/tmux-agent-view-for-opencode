# tmux-agent-view-for-opencode

OpenCodeのサブエージェント実行をtmuxペーンで可視化するためのv1.0実装です。

## できること

- サブエージェント起動時にペーンを自動作成
- 親(Orchestrator)を主表示として維持
- サブエージェント完了時にペーンを自動終了
- JSON設定でレイアウトや挙動を調整

## 主要ファイル

- 本体: `tmux_agent_view/bin/agent_pane_manager.py`
- プラグイン: `tmux_agent_view/plugin/minimal_tmux_view_plugin.js`
- 設定: `tmux_agent_view/config/default.json`
- ドキュメント: `tmux_agent_view/README.md`
- プラグイン詳細: `tmux_agent_view/plugin/README.md`

## クイックスタート

1. プラグインを実配置へコピー

```bash
tmux_agent_view/bin/install_to_opencode_plugins.sh
```

2. 推奨ランチャーで起動

```bash
tmux_agent_view/bin/opencode_tmux.sh --port 4096 --session-name oc
```

3. Orchestratorで複数サブエージェントを同時起動するタスクを実行

## ライセンス

必要に応じてこのリポジトリに追加してください。
