// graph.js — S12.1 live graph viewer (read-only) over /v1/graph/*.
// Renders Character/Location/Faction/Event nodes and the relationships between
// them using Cytoscape. No engine code; pure REST reads.
"use strict";

const NpcGraph = (() => {
  const { el, toast, make, fmt } = NpcUI;

  const NODE_TYPES = ["Character", "Location", "Faction", "Event"];
  // Relationship types whose endpoints are among the four node types above.
  const EDGE_TYPES = [
    "MEMBER_OF", "LOCATED_AT", "KNOWS_ABOUT", "STANDS_WITH",
    "OPPOSES", "PART_OF", "CONTROLS", "OCCUPIES", "PARTICIPATED_IN",
  ];
  const COLORS = {
    Character: "#4ea1ff", Location: "#43c59e", Faction: "#f0a35e", Event: "#c77dff",
  };

  let cy = null;

  function enabledTypes() {
    return Array.from(document.querySelectorAll(".node-filter"))
      .filter((c) => c.checked)
      .map((c) => c.value);
  }

  async function fetchNodes(types) {
    const ids = new Set();
    const elements = [];
    for (const type of types) {
      const items = (await NpcApi.listNodes(type)) || [];
      for (const node of items) {
        if (!node.id || ids.has(node.id)) continue;
        ids.add(node.id);
        elements.push({
          data: {
            id: node.id,
            label: node.name || node.title || node.id,
            ntype: type,
            props: node,
          },
        });
      }
    }
    return { ids, elements };
  }

  async function fetchEdges(ids) {
    const elements = [];
    for (const type of EDGE_TYPES) {
      let items = [];
      try {
        items = (await NpcApi.listEdges(type)) || [];
      } catch {
        continue; // edge type not registered in this world — skip silently
      }
      for (const edge of items) {
        if (!ids.has(edge.src_id) || !ids.has(edge.dst_id)) continue;
        elements.push({
          data: {
            id: `${type}:${edge.src_id}->${edge.dst_id}`,
            source: edge.src_id,
            target: edge.dst_id,
            label: type,
            props: edge,
          },
        });
      }
    }
    return elements;
  }

  function styles() {
    return [
      {
        selector: "node",
        style: {
          "background-color": (e) => COLORS[e.data("ntype")] || "#888",
          label: "data(label)",
          color: "#e6edf3",
          "font-size": 9,
          "text-valign": "bottom",
          "text-margin-y": 3,
          width: 22,
          height: 22,
        },
      },
      {
        selector: "edge",
        style: {
          width: 1.2,
          "line-color": "#39465a",
          "target-arrow-color": "#39465a",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "font-size": 7,
          color: "#8b97a6",
          label: "data(label)",
          "text-rotation": "autorotate",
        },
      },
      { selector: ".sel", style: { "border-width": 3, "border-color": "#fff", "line-color": "#fff" } },
    ];
  }

  function inspect(data) {
    const box = el("graph-inspector");
    box.replaceChildren();
    box.appendChild(make("h4", { text: data.label || data.id }));
    const dl = make("dl");
    const props = data.props || {};
    for (const [k, v] of Object.entries(props)) {
      if (k === "props") continue;
      dl.appendChild(make("dt", { text: k }));
      dl.appendChild(make("dd", { text: fmt(v) }));
    }
    box.appendChild(dl);
  }

  function render(elements) {
    if (!window.cytoscape) {
      toast("Cytoscape failed to load (offline?)", "err");
      return;
    }
    cy = cytoscape({
      container: el("cy"),
      elements,
      style: styles(),
      layout: { name: "cose", animate: false, nodeRepulsion: 6000, idealEdgeLength: 90 },
    });
    cy.on("tap", "node, edge", (evt) => {
      cy.elements().removeClass("sel");
      evt.target.addClass("sel");
      inspect(evt.target.data());
    });
  }

  async function load() {
    const types = enabledTypes();
    if (types.length === 0) {
      toast("Select at least one node type", "err");
      return;
    }
    const { ids, elements: nodeEls } = await fetchNodes(types);
    const edgeEls = await fetchEdges(ids);
    render([...nodeEls, ...edgeEls]);
    toast(`Loaded ${nodeEls.length} nodes, ${edgeEls.length} edges`, "ok");
  }

  function init() {
    el("graph-refresh").addEventListener("click", () => NpcUI.guard(load, "Graph"));
    document.querySelectorAll(".node-filter").forEach((c) =>
      c.addEventListener("change", () => NpcUI.guard(load, "Graph"))
    );
  }

  return { init, load };
})();

window.NpcGraph = NpcGraph;
