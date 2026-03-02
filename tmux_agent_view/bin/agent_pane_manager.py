#!/usr/bin/env python3
import argparse
import contextlib
import fcntl
import json
import os
import shlex
import time
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
APP_ROOT = SCRIPT_PATH.parent.parent
PROJECT_ROOT = APP_ROOT.parent
DEFAULT_CONFIG_PATH = APP_ROOT / "config" / "default.json"
STATE_FILE_NAME = "pane_state.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def generate_task_id() -> str:
    return f"task-{uuid.uuid4().hex[:12]}"


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


def default_state() -> dict:
    return {
        "parent_pane": None,
        "session_id": None,
        "window_id": None,
        "created_at": None,
        "updated_at": None,
        "tasks": {},
    }


def run_tmux(args: list[str], check: bool = True) -> str:
    proc = subprocess.run(
        ["tmux", *args],
        check=False,
        text=True,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"tmux command failed: {' '.join(args)}: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def in_tmux() -> bool:
    return bool(os.environ.get("TMUX"))


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def resolve_state_dir(config: dict) -> Path:
    raw = str(config.get("state_dir", "tmux_agent_view/state"))
    path = Path(raw)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def state_file_path(config: dict) -> Path:
    directory = resolve_state_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / STATE_FILE_NAME


def state_lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


@contextlib.contextmanager
def state_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def load_state(path: Path) -> dict:
    if not path.exists():
        return default_state()
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        broken = path.with_suffix(
            path.suffix + f".broken.{int(datetime.now().timestamp())}"
        )
        try:
            path.replace(broken)
        except OSError:
            pass
        print(
            f"warning: state file is broken and was reset: {path}",
            file=sys.stderr,
        )
        return default_state()


def save_state(path: Path, state: dict) -> None:
    state["updated_at"] = now_iso()
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=True, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp_path, path)


def pane_exists(pane_id: str) -> bool:
    if not pane_id:
        return False
    panes = run_tmux(["list-panes", "-a", "-F", "#{pane_id}"], check=False)
    if not panes:
        return False
    return pane_id in panes.splitlines()


def get_pane_meta(pane_id: str) -> dict | None:
    if not pane_id:
        return None
    out = run_tmux(
        [
            "display-message",
            "-p",
            "-t",
            pane_id,
            "#{session_id}\t#{window_id}\t#{pane_title}\t#{pane_current_command}",
        ],
        check=False,
    )
    if not out:
        return None
    parts = out.split("\t", 3)
    if len(parts) < 4:
        return None
    return {
        "session_id": parts[0],
        "window_id": parts[1],
        "pane_title": parts[2],
        "pane_current_command": parts[3],
    }


def can_kill_task_pane(state: dict, task: dict, pane_id: str) -> bool:
    meta = get_pane_meta(pane_id)
    if not meta:
        return False
    expected_session = str(state.get("session_id") or "")
    expected_window = str(state.get("window_id") or "")
    expected_title = str(task.get("title") or "")

    if expected_session and meta["session_id"] != expected_session:
        return False
    if expected_window and meta["window_id"] != expected_window:
        return False
    return True


def close_pane_gracefully(pane_id: str) -> bool:
    if not pane_exists(pane_id):
        return False
    run_tmux(["send-keys", "-t", pane_id, "C-c"], check=False)
    run_tmux(["kill-pane", "-t", pane_id], check=False)
    return True


def enforce_min_lifetime(task: dict, config: dict) -> None:
    raw = config.get("min_pane_lifetime_seconds", 0)
    try:
        min_seconds = float(raw)
    except (TypeError, ValueError):
        min_seconds = 0.0

    if min_seconds <= 0:
        return

    started_at = str(task.get("started_at") or "")
    if not started_at:
        return

    try:
        started = datetime.fromisoformat(started_at)
    except ValueError:
        return

    elapsed = (datetime.now(timezone.utc).astimezone() - started).total_seconds()
    remain = min_seconds - elapsed
    if remain > 0:
        time.sleep(remain)


def install_pane_exit_hook(state: dict, config_path: Path, config: dict) -> None:
    if not bool(config.get("install_pane_exit_hook", True)):
        return

    window_id = str(state.get("window_id") or "")
    if not window_id:
        return

    manager = shlex.quote(str(SCRIPT_PATH))
    safe_config = shlex.quote(str(config_path))
    hook_cmd = (
        f'run-shell "python3 {manager} --config {safe_config} reap >/dev/null 2>&1"'
    )
    run_tmux(["set-hook", "-t", window_id, "pane-exited", hook_cmd], check=False)


def clear_pane_exit_hook(state: dict) -> None:
    window_id = str(state.get("window_id") or "")
    if not window_id:
        return
    run_tmux(["set-hook", "-u", "-t", window_id, "pane-exited"], check=False)


def reap_finished_tasks(state: dict) -> list[dict]:
    reaped = []
    for task_id, task in list(state.get("tasks", {}).items()):
        if task.get("status") != "running":
            continue
        pane_id = str(task.get("pane_id") or "")
        if pane_id and pane_exists(pane_id):
            continue
        task["status"] = "done"
        task["finished_at"] = task.get("finished_at") or now_iso()
        reaped.append({"task_id": task_id, "pane_id": pane_id})
    return reaped


def apply_layout(state: dict, config: dict) -> None:
    window_id = state.get("window_id")
    if not window_id:
        return
    layout = str(config.get("layout", "main-vertical"))
    size = format_main_pane_size(config.get("main_pane_size", 60))

    if "vertical" in layout:
        run_tmux(
            ["set-window-option", "-t", window_id, "main-pane-width", size],
            check=False,
        )
    elif "horizontal" in layout:
        run_tmux(
            ["set-window-option", "-t", window_id, "main-pane-height", size],
            check=False,
        )

    run_tmux(["select-layout", "-t", window_id, layout], check=False)


def set_title(pane_id: str, title: str) -> None:
    safe_title = title.replace("\n", " ").strip()
    run_tmux(["select-pane", "-t", pane_id, "-T", safe_title], check=False)


def format_main_pane_size(raw: object) -> str:
    text = str(raw).strip()
    if text.endswith("%"):
        return text

    try:
        value = int(text)
    except ValueError:
        return "60%"

    if 1 <= value <= 100:
        return f"{value}%"
    return str(value)


def wrapped_cmd_for_auto_finish(cmd: str, task_id: str, config_path: Path) -> str:
    manager = SCRIPT_PATH
    safe_manager = shlex.quote(str(manager))
    safe_config = shlex.quote(str(config_path))
    safe_task_id = shlex.quote(task_id)

    return "bash -lc " + shlex.quote(
        "set +e; "
        + cmd
        + "; __exit=$?; "
        + "if [ $__exit -eq 0 ]; then __status=done; else __status=error; fi; "
        + "for __i in 1 2 3 4 5 6 7 8 9 10; do "
        + f"python3 {safe_manager} --config {safe_config} finish --task-id {safe_task_id} --status $__status >/dev/null 2>&1 && break; "
        + "sleep 0.2; "
        + "done; "
        + "exit $__exit"
    )


def cmd_init(state: dict, state_path: Path, config: dict, config_path: Path) -> int:
    if not in_tmux():
        print("TMUX外で実行されたため init は何もしません。")
        return 2

    parent = os.environ.get("TMUX_PANE") or run_tmux(
        ["display-message", "-p", "#{pane_id}"]
    )
    state["parent_pane"] = parent
    state["session_id"] = run_tmux(["display-message", "-p", "#{session_id}"])
    state["window_id"] = run_tmux(["display-message", "-p", "#{window_id}"])
    state["created_at"] = state.get("created_at") or now_iso()
    if "tasks" not in state:
        state["tasks"] = {}
    install_pane_exit_hook(state, config_path, config)
    save_state(state_path, state)
    print_json({"result": "ok", "parent_pane": parent, "state_file": str(state_path)})
    return 0


def resolve_split_mode(config: dict) -> str:
    mode = str(config.get("split", "auto"))
    if mode in {"right", "bottom"}:
        return mode

    layout = str(config.get("layout", "main-vertical"))
    return "right" if "vertical" in layout else "bottom"


def cmd_start(
    state: dict,
    state_path: Path,
    config: dict,
    config_path: Path,
    task_id: str,
    agent: str,
    cmd: str,
) -> int:
    if not in_tmux():
        print("TMUX外で実行されたため start は何もしません。")
        return 2
    if not bool(config.get("enabled", True)):
        print("tmux_agent_view is disabled by config.enabled=false")
        return 0

    if not state.get("parent_pane"):
        state["parent_pane"] = os.environ.get("TMUX_PANE") or run_tmux(
            ["display-message", "-p", "#{pane_id}"]
        )
    if not state.get("window_id"):
        state["window_id"] = run_tmux(["display-message", "-p", "#{window_id}"])
    if not state.get("session_id"):
        state["session_id"] = run_tmux(["display-message", "-p", "#{session_id}"])

    install_pane_exit_hook(state, config_path, config)

    reap_finished_tasks(state)

    existing = state.get("tasks", {}).get(task_id)
    if (
        existing
        and existing.get("status") == "running"
        and pane_exists(str(existing.get("pane_id") or ""))
    ):
        print_json(
            {"result": "conflict", "task_id": task_id, "reason": "task already running"}
        )
        return 1

    split_mode = resolve_split_mode(config)
    split_flag = "-h" if split_mode == "right" else "-v"
    pane_cmd = cmd
    if bool(config.get("auto_finish_hook", True)):
        pane_cmd = wrapped_cmd_for_auto_finish(cmd, task_id, config_path)

    pane_id = run_tmux(["split-window", split_flag, "-P", "-F", "#{pane_id}", pane_cmd])

    prefix = str(config.get("title_prefix", "agent"))
    task_title = f"{prefix}:{agent}:{task_id}"
    set_title(pane_id, task_title)

    apply_layout(state, config)
    if state.get("parent_pane") and pane_exists(str(state.get("parent_pane"))):
        run_tmux(["select-pane", "-t", str(state.get("parent_pane"))], check=False)

    state.setdefault("tasks", {})[task_id] = {
        "agent": agent,
        "cmd": cmd,
        "pane_id": pane_id,
        "title": task_title,
        "split": split_mode,
        "status": "running",
        "started_at": now_iso(),
        "finished_at": None,
    }
    save_state(state_path, state)
    print_json({"result": "ok", "task_id": task_id, "pane_id": pane_id})
    return 0


def cmd_spawn(
    state: dict,
    state_path: Path,
    config: dict,
    config_path: Path,
    agent: str,
    cmd: str,
    task_id: str | None,
) -> int:
    if not in_tmux():
        print("TMUX外で実行されたため spawn は何もしません。")
        return 2

    if not state.get("parent_pane"):
        state["parent_pane"] = os.environ.get("TMUX_PANE") or run_tmux(
            ["display-message", "-p", "#{pane_id}"]
        )
    if not state.get("window_id"):
        state["window_id"] = run_tmux(["display-message", "-p", "#{window_id}"])
    if not state.get("session_id"):
        state["session_id"] = run_tmux(["display-message", "-p", "#{session_id}"])
    if not state.get("created_at"):
        state["created_at"] = now_iso()
    if "tasks" not in state:
        state["tasks"] = {}

    save_state(state_path, state)

    effective_task_id = task_id or generate_task_id()
    return cmd_start(
        state,
        state_path,
        config,
        config_path,
        effective_task_id,
        agent,
        cmd,
    )


def cmd_finish(
    state: dict, state_path: Path, config: dict, task_id: str, status: str
) -> int:
    if not in_tmux():
        print("TMUX外で実行されたため finish は何もしません。")
        return 2

    task = state.get("tasks", {}).get(task_id)
    if not task:
        print_json({"result": "not_found", "task_id": task_id})
        return 1

    pane_id = task.get("pane_id")
    task["status"] = status
    task["finished_at"] = now_iso()

    killed = False
    kill_safe = True
    if bool(config.get("kill_on_finish", True)) and pane_exists(str(pane_id)):
        enforce_min_lifetime(task, config)
        if can_kill_task_pane(state, task, str(pane_id)):
            killed = close_pane_gracefully(str(pane_id))
        else:
            kill_safe = False

    if state.get("parent_pane") and pane_exists(str(state.get("parent_pane"))):
        run_tmux(["select-pane", "-t", str(state.get("parent_pane"))], check=False)
        apply_layout(state, config)

    save_state(state_path, state)
    print_json(
        {
            "result": "ok",
            "task_id": task_id,
            "killed": killed,
            "kill_safe": kill_safe,
            "status": status,
        }
    )
    return 0


def cmd_cleanup(state: dict, state_path: Path, config: dict) -> int:
    if not in_tmux():
        print("TMUX外で実行されたため cleanup は何もしません。")
        return 2

    killed = []
    skipped = []
    for task_id, task in list(state.get("tasks", {}).items()):
        pane_id = str(task.get("pane_id", ""))
        if pane_exists(pane_id):
            if can_kill_task_pane(state, task, pane_id):
                close_pane_gracefully(pane_id)
                killed.append({"task_id": task_id, "pane_id": pane_id})
            else:
                skipped.append(
                    {
                        "task_id": task_id,
                        "pane_id": pane_id,
                        "reason": "ownership_mismatch",
                    }
                )
        task["status"] = "cleaned"
        task["finished_at"] = now_iso()

    if state.get("parent_pane") and pane_exists(str(state.get("parent_pane"))):
        run_tmux(["select-pane", "-t", str(state.get("parent_pane"))], check=False)
        apply_layout(state, config)

    state["tasks"] = {}
    clear_pane_exit_hook(state)
    save_state(state_path, state)
    print_json({"result": "ok", "killed": killed, "skipped": skipped})
    return 0


def cmd_status(state: dict, state_path: Path, config: dict) -> int:
    reaped = []
    if in_tmux():
        reaped = reap_finished_tasks(state)
        if reaped:
            save_state(state_path, state)

    payload = {
        "config": config,
        "in_tmux": in_tmux(),
        "reaped": reaped,
        "state_file": str(state_path),
        "state": state,
    }
    print_json(payload)
    return 0


def cmd_reap(state: dict, state_path: Path) -> int:
    if not in_tmux():
        print("TMUX外で実行されたため reap は何もしません。")
        return 2

    reaped = reap_finished_tasks(state)
    if reaped:
        save_state(state_path, state)
    print_json({"result": "ok", "reaped": reaped})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="tmux pane manager for sub agents")
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG_PATH), help="path to config json"
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")

    p_start = sub.add_parser("start")
    p_start.add_argument("--task-id", required=True)
    p_start.add_argument("--agent", required=True)
    p_start.add_argument("--cmd", required=True)

    p_spawn = sub.add_parser("spawn")
    p_spawn.add_argument("--task-id", required=False)
    p_spawn.add_argument("--agent", required=True)
    p_spawn.add_argument("--cmd", required=True)

    p_finish = sub.add_parser("finish")
    p_finish.add_argument("--task-id", required=True)
    p_finish.add_argument("--status", choices=["done", "error"], default="done")

    sub.add_parser("cleanup")
    sub.add_parser("reap")
    sub.add_parser("status")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        print(f"config not found: {config_path}", file=sys.stderr)
        return 2

    config = load_config(config_path)
    state_path = state_file_path(config)
    lock_path = state_lock_path(state_path)

    try:
        if args.command == "status":
            state = load_state(state_path)
            return cmd_status(state, state_path, config)

        with state_lock(lock_path):
            state = load_state(state_path)
            if args.command == "init":
                return cmd_init(state, state_path, config, config_path)
            if args.command == "start":
                return cmd_start(
                    state,
                    state_path,
                    config,
                    config_path,
                    args.task_id,
                    args.agent,
                    args.cmd,
                )
            if args.command == "spawn":
                return cmd_spawn(
                    state,
                    state_path,
                    config,
                    config_path,
                    args.agent,
                    args.cmd,
                    args.task_id,
                )
            if args.command == "finish":
                return cmd_finish(state, state_path, config, args.task_id, args.status)
            if args.command == "cleanup":
                return cmd_cleanup(state, state_path, config)
            if args.command == "reap":
                return cmd_reap(state, state_path)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
