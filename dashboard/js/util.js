// util.js — tiny DOM + formatting helpers shared by all tab modules.
"use strict";

const NpcUI = (() => {
  function el(id) {
    return document.getElementById(id);
  }
  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }
  // Create an element with text + attributes; escapes text via textContent.
  function make(tag, opts = {}) {
    const node = document.createElement(tag);
    if (opts.text != null) node.textContent = String(opts.text);
    if (opts.cls) node.className = opts.cls;
    if (opts.attrs) for (const [k, v] of Object.entries(opts.attrs)) node.setAttribute(k, v);
    if (opts.children) for (const c of opts.children) node.appendChild(c);
    return node;
  }

  let toastTimer = null;
  function toast(message, kind = "ok") {
    const t = el("toast");
    t.textContent = message;
    t.className = `toast show ${kind}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.className = "toast"), 3200);
  }

  // Wrap an async tab loader so failures surface as a toast instead of crashing.
  async function guard(promiseFactory, context) {
    try {
      return await promiseFactory();
    } catch (err) {
      toast(`${context}: ${err.message}`, "err");
      return null;
    }
  }

  function fmt(value) {
    if (value == null) return "—";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  return { el, clear, make, toast, guard, fmt };
})();

window.NpcUI = NpcUI;
