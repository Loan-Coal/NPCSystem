// analytics.js — S12.5 designer analytics over /v1/system/metrics (request +
// degradation counters) and /v1/system/events (recent world activity).
"use strict";

const NpcAnalytics = (() => {
  const { el, make, fmt } = NpcUI;

  function metricsTable(snapshot) {
    const table = el("metrics-table");
    table.replaceChildren();
    table.appendChild(
      make("tr", { children: ["Metric", "Value"].map((t) => make("th", { text: t })) })
    );
    const counters = (snapshot && snapshot.counters) || {};
    const observations = (snapshot && snapshot.observations) || {};
    const rows = { ...counters };
    for (const [k, v] of Object.entries(observations)) {
      rows[k] = v && typeof v === "object" ? v.count ?? fmt(v) : v;
    }
    const keys = Object.keys(rows).sort();
    if (keys.length === 0) {
      table.appendChild(make("tr", { children: [make("td", { cls: "muted", attrs: { colspan: "2" }, text: "No metrics recorded yet." })] }));
      return;
    }
    for (const key of keys) {
      const tr = make("tr");
      tr.appendChild(make("td", { text: key }));
      tr.appendChild(make("td", { text: fmt(rows[key]) }));
      table.appendChild(tr);
    }
  }

  function eventsTable(events) {
    const table = el("events-table");
    table.replaceChildren();
    table.appendChild(
      make("tr", { children: ["Tick", "Type", "Description"].map((t) => make("th", { text: t })) })
    );
    for (const ev of events || []) {
      const tr = make("tr");
      tr.appendChild(make("td", { text: fmt(ev.tick ?? ev.occurred_at_tick) }));
      tr.appendChild(make("td", { text: fmt(ev.event_type ?? ev.type) }));
      tr.appendChild(make("td", { text: fmt(ev.description ?? ev.summary ?? ev.name) }));
      table.appendChild(tr);
    }
  }

  async function load() {
    const [snapshot, events] = await Promise.all([
      NpcApi.metrics(),
      NpcApi.recentEvents().catch(() => []),
    ]);
    metricsTable(snapshot);
    eventsTable(events);
  }

  function init() {
    el("analytics-refresh").addEventListener("click", () => NpcUI.guard(load, "Analytics"));
  }

  return { init, load };
})();

window.NpcAnalytics = NpcAnalytics;
