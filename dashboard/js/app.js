// app.js — bootstrap: tab navigation, connection handling, lazy tab loading.
"use strict";

(() => {
  const { el, toast } = NpcUI;

  const TABS = {
    graph: NpcGraph,
    npcs: NpcNpcs,
    drafts: NpcDrafts,
    engines: NpcEngines,
    analytics: NpcAnalytics,
  };
  const loaded = new Set();

  function activate(name) {
    document.querySelectorAll(".tab").forEach((t) =>
      t.classList.toggle("is-active", t.dataset.tab === name)
    );
    document.querySelectorAll(".panel").forEach((p) =>
      p.classList.toggle("is-active", p.id === `panel-${name}`)
    );
    if (!NpcApi.getKey()) return;
    if (!loaded.has(name)) {
      loaded.add(name);
      NpcUI.guard(() => TABS[name].load(), name);
    }
  }

  function setConn(state, text) {
    const node = el("conn-status");
    node.className = `conn-status conn-${state}`;
    node.textContent = text;
  }

  async function connect() {
    const key = el("api-key").value.trim();
    if (!key) {
      toast("Enter an API key", "err");
      return;
    }
    NpcApi.setKey(key);
    setConn("unknown", "connecting…");
    try {
      await NpcApi.ping();
      setConn("ok", "connected");
      toast("Connected", "ok");
      loaded.clear();
      const active = document.querySelector(".tab.is-active");
      activate(active ? active.dataset.tab : "graph");
    } catch (err) {
      setConn("bad", "auth failed");
      toast(`Connect: ${err.message}`, "err");
    }
  }

  function init() {
    Object.values(TABS).forEach((m) => m.init());
    document.querySelectorAll(".tab").forEach((t) =>
      t.addEventListener("click", () => activate(t.dataset.tab))
    );
    el("api-key-save").addEventListener("click", connect);
    el("api-key").addEventListener("keydown", (e) => {
      if (e.key === "Enter") connect();
    });

    const existing = NpcApi.getKey();
    if (existing) {
      el("api-key").value = existing;
      connect();
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
