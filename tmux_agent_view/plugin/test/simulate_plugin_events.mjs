import pluginFactory from "../minimal_tmux_view_plugin.js";

function created(sessionId, title) {
  return {
    event: {
      type: "session.created",
      properties: {
        info: { id: sessionId, parentID: "parent-1", title },
      },
    },
  };
}

function idle(sessionId) {
  return {
    event: {
      type: "session.status",
      properties: {
        sessionID: sessionId,
        status: { type: "idle" },
      },
    },
  };
}

const plugin = pluginFactory();

await Promise.all([
  plugin.event(created("sim-s1", "coder_a"), {}),
  plugin.event(created("sim-s2", "coder_b"), {}),
  plugin.event(created("sim-s3", "planner"), {}),
]);

await new Promise((r) => setTimeout(r, 1200));

await Promise.all([
  plugin.event(idle("sim-s1"), {}),
  plugin.event(idle("sim-s2"), {}),
  plugin.event(idle("sim-s3"), {}),
]);

await new Promise((r) => setTimeout(r, 500));

console.log("simulate_plugin_events: done");
