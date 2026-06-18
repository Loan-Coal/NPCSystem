// engines.js — S12.4 engine cadence + cost inspector over /v1/admin/system/config and
// /v1/admin/system/engines. Read-only: live mutation of cadence/budget is deferred
// (see ISSUES.md) because it requires runtime settings mutation.
"use strict";

const NpcEngines = (() => {
  const { el, make } = NpcUI;

  function configTable(config) {
    const table = el("config-table");
    table.replaceChildren();
    for (const [key, value] of Object.entries(config || {})) {
      const tr = make("tr");
      tr.appendChild(make("td", { text: key }));
      tr.appendChild(make("td", { text: NpcUI.fmt(value) }));
      table.appendChild(tr);
    }
  }

  function statusTable(records) {
    const table = el("engine-status-table");
    table.replaceChildren();
    const header = make("tr", {
      children: ["Engine", "Last tick", "Errors", "Last error"].map((t) => make("th", { text: t })),
    });
    table.appendChild(header);
    for (const rec of records || []) {
      const tr = make("tr");
      tr.appendChild(make("td", { text: rec.engine_name }));
      tr.appendChild(make("td", { text: NpcUI.fmt(rec.last_tick_id) }));
      tr.appendChild(make("td", { cls: rec.error_count ? "err" : "ok", text: rec.error_count }));
      tr.appendChild(make("td", { cls: rec.last_error ? "err" : "", text: NpcUI.fmt(rec.last_error) }));
      table.appendChild(tr);
    }
  }

  async function load() {
    const [config, records] = await Promise.all([NpcApi.runtimeConfig(), NpcApi.engineStatus()]);
    configTable(config);
    statusTable(records);
  }

  function init() {
    el("engines-refresh").addEventListener("click", () => NpcUI.guard(load, "Engines"));
  }

  return { init, load };
})();

window.NpcEngines = NpcEngines;
