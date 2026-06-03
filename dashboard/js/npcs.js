// npcs.js — S12.2 NPC authoring form over POST /v1/graph/nodes/Character.
"use strict";

const NpcNpcs = (() => {
  const { el, make, toast, fmt } = NpcUI;

  const INT_FIELDS = ["gossipy", "credulity", "honesty"];

  // Build the Character node property payload from the form, filling the
  // schema-required bookkeeping fields the engine expects.
  function buildProperties(form) {
    const now = new Date().toISOString();
    const data = new FormData(form);
    const props = {
      is_player: false,
      is_active: true,
      created_at: now,
      updated_at: now,
      last_graph_updated_at: now,
    };
    for (const [key, raw] of data.entries()) {
      const value = String(raw).trim();
      if (value === "") continue;
      props[key] = INT_FIELDS.includes(key) ? Number(value) : value;
    }
    for (const f of INT_FIELDS) if (props[f] == null) props[f] = 50;
    return props;
  }

  async function submit(event) {
    event.preventDefault();
    const form = event.target;
    const status = el("npc-form-status");
    status.textContent = "Creating…";
    try {
      const props = buildProperties(form);
      await NpcApi.createNode("Character", props);
      status.textContent = "";
      toast(`Created NPC "${props.id}"`, "ok");
      form.reset();
      await load();
    } catch (err) {
      status.textContent = "";
      toast(`Create NPC: ${err.message}`, "err");
    }
  }

  function card(npc) {
    const c = make("div", { cls: "card" });
    c.appendChild(make("h4", { text: npc.name || npc.id }));
    c.appendChild(make("div", { cls: "muted", text: `${npc.archetype || "—"} · ${npc.faction || "no faction"}` }));
    const bio = make("div", { cls: "row" });
    bio.appendChild(make("span", { text: fmt(npc.biography).slice(0, 90) }));
    c.appendChild(bio);
    return c;
  }

  async function load() {
    const list = el("npc-list");
    list.replaceChildren(make("p", { cls: "muted", text: "Loading…" }));
    const npcs = (await NpcApi.listNodes("Character")) || [];
    const authored = npcs.filter((n) => n.is_player !== true);
    list.replaceChildren(
      ...(authored.length ? authored.map(card) : [make("p", { cls: "muted", text: "No NPCs yet." })])
    );
  }

  function init() {
    el("npc-form").addEventListener("submit", submit);
    el("npc-list-refresh").addEventListener("click", () => NpcUI.guard(load, "NPCs"));
  }

  return { init, load };
})();

window.NpcNpcs = NpcNpcs;
