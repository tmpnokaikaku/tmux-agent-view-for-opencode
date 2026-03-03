import { spawn } from "child_process";
import { existsSync } from "fs";
import { homedir } from "os";

const HOME_DIR = process.env.HOME || homedir() || "";
const DEFAULT_PLUGIN_ROOT = `${HOME_DIR}/.config/opencode/plugins/tmux_agent_view`;
const DEFAULT_MANAGER = `${DEFAULT_PLUGIN_ROOT}/bin/agent_pane_manager.py`;
const DEFAULT_CONFIG = `${DEFAULT_PLUGIN_ROOT}/config/default.json`;

function parseEnabled(value) {
  if (value == null || value === "") {
    return true;
  }
  const normalized = String(value).trim().toLowerCase();
  return !["0", "false", "off", "no"].includes(normalized);
}

function firstNonEmpty(...values) {
  for (const value of values) {
    if (typeof value === "string" && value.trim() !== "") {
      return value.trim();
    }
  }
  return "";
}

function toEventData(input) {
  const event = input?.event && typeof input.event === "object" ? input.event : input;
  if (!event || typeof event !== "object") {
    return { type: "", event: {} };
  }
  const type = firstNonEmpty(event.type, event.event);
  return { type, event };
}

function getStatusType(event) {
  return firstNonEmpty(
    event?.properties?.status?.type,
    event?.status?.type,
  );
}

function getServerUrl(context) {
  const fallbackPort = process.env.OPENCODE_PORT || "4096";
  return firstNonEmpty(
    process.env.TMUX_VIEW_SERVER_URL,
    context?.serverUrl?.toString?.(),
    context?.serverUrl,
    context?.client?.serverUrl,
    process.env.OPENCODE_SERVER_URL,
    `http://127.0.0.1:${fallbackPort}`,
  );
}

function getConnectedServerUrl(event) {
  return firstNonEmpty(
    event?.properties?.url,
    event?.properties?.serverUrl,
    event?.url,
    event?.serverUrl,
  );
}

function getSessionId(event) {
  return firstNonEmpty(
    event?.properties?.sessionID,
    event?.properties?.info?.id,
    event?.sessionID,
    event?.session?.id,
  );
}

function getParentId(event) {
  return firstNonEmpty(
    event?.properties?.info?.parentID,
    event?.properties?.info?.parentId,
    event?.session?.parentID,
  );
}

function getAgentTitle(event) {
  return firstNonEmpty(event?.properties?.info?.title, event?.info?.title);
}

function buildRunner({ enabled, pythonBin, managerPath, configPath }) {
  const insideTmux = Boolean(process.env.TMUX);

  function runManager(managerArgs, label) {
    if (!enabled) {
      return Promise.resolve({ ok: true, skipped: true });
    }
    if (!insideTmux) {
      return Promise.resolve({ ok: true, skipped: true, reason: "not_in_tmux" });
    }
    return new Promise((resolve) => {
      const args = [managerPath];
      if (configPath) {
        args.push("--config", configPath);
      }
      args.push(...managerArgs);

      const child = spawn(pythonBin, args, {
        stdio: "ignore",
      });

      child.once("error", (error) => {
        console.warn(`[tmux-view] ${label} failed to start: ${error.message}`);
        resolve({ ok: false, error });
      });

      child.once("close", (code) => {
        if (code === 0) {
          resolve({ ok: true, code });
          return;
        }
        if (code === 2) {
          resolve({ ok: true, code, skipped: true });
          return;
        }
        console.warn(`[tmux-view] ${label} exited with code ${code}`);
        resolve({ ok: false, code });
      });
    });
  }

  return { runManager };
}

export default function minimalTmuxViewPlugin() {
  const enabled = parseEnabled(process.env.TMUX_VIEW_ENABLED);
  const debug = parseEnabled(process.env.TMUX_VIEW_DEBUG || "false");
  const pythonBin = process.env.TMUX_VIEW_PYTHON || "python3";
  const managerPath = process.env.TMUX_VIEW_MANAGER || DEFAULT_MANAGER;
  const configPath = firstNonEmpty(
    process.env.TMUX_VIEW_CONFIG,
    existsSync(DEFAULT_CONFIG) ? DEFAULT_CONFIG : "",
  );

  const { runManager } = buildRunner({
    enabled,
    pythonBin,
    managerPath,
    configPath,
  });

  const spawnedBySession = new Map();
  let runtimeServerUrl = "";

  if (enabled && !process.env.TMUX) {
    console.warn("[tmux-view] disabled at runtime: TMUX is not set. Run opencode inside tmux for pane split view.");
  }

  function logDebug(message, data = {}) {
    if (!debug) return;
    try {
      console.error(`[tmux-view] ${message} ${JSON.stringify(data)}`);
    } catch {
      console.error(`[tmux-view] ${message}`);
    }
  }

  runManager(["init"], "init").catch((error) => {
    console.warn(`[tmux-view] init error: ${error.message}`);
  });

  return {
    name: "minimal-tmux-view-plugin",
    async event(input, context) {
      if (!enabled) {
        return;
      }

      const { type, event } = toEventData(input);
      const sessionId = getSessionId(event);
      logDebug("event.received", { type, sessionId });

      if (type === "server.connected") {
        const connectedUrl = getConnectedServerUrl(event);
        if (connectedUrl) {
          runtimeServerUrl = connectedUrl;
          logDebug("server.connected", { runtimeServerUrl });
        }
        return;
      }

      if (!sessionId) {
        return;
      }

      if (type === "session.created") {
        if (!getParentId(event)) {
          return;
        }
        if (spawnedBySession.has(sessionId)) {
          return;
        }

        const agent = getAgentTitle(event) || "subagent";
        const serverUrl = firstNonEmpty(runtimeServerUrl, getServerUrl(context));
        if (!serverUrl) {
          console.warn(`[tmux-view] skip spawn: missing serverUrl for session ${sessionId}`);
          return;
        }

        const cmd = `opencode attach ${serverUrl} --session ${sessionId}`;
        const spawnResult = await runManager(
          ["spawn", "--task-id", sessionId, "--agent", agent, "--cmd", cmd],
          `spawn(${sessionId})`,
        );
        if (spawnResult?.ok) {
          spawnedBySession.set(sessionId, true);
        }
        return;
      }

      if (type === "session.status") {
        if (getStatusType(event) === "idle" && spawnedBySession.has(sessionId)) {
          await runManager(
            ["finish", "--task-id", sessionId, "--status", "done"],
            `finish-idle(${sessionId})`,
          );
          spawnedBySession.delete(sessionId);
        }
        return;
      }

      if (type === "session.deleted") {
        if (spawnedBySession.has(sessionId)) {
          await runManager(
            ["finish", "--task-id", sessionId, "--status", "done"],
            `finish-deleted(${sessionId})`,
          );
          spawnedBySession.delete(sessionId);
        }
      }
    },
  };
}
