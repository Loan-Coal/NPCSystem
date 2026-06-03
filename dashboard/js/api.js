// api.js — thin fetch wrapper for the NPC Engine REST API.
// Handles Bearer auth, the {success,data,meta} envelope, idempotency/request
// headers on mutations, and surfaces errors as thrown Error objects.
"use strict";

const NpcApi = (() => {
  const V1 = "/v1";
  const ADMIN = "/v1/admin";
  const KEY_STORAGE = "npc_api_key";

  function getKey() {
    return localStorage.getItem(KEY_STORAGE) || "";
  }
  function setKey(value) {
    localStorage.setItem(KEY_STORAGE, value || "");
  }

  // RFC 4122 v4 UUID — required by the engine's idempotency header validator.
  function uuid4() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
      (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
    );
  }

  function headers(mutating) {
    const h = { Authorization: `Bearer ${getKey()}`, "X-Request-ID": uuid4() };
    if (mutating) {
      h["Content-Type"] = "application/json";
      h["X-Idempotency-Key"] = uuid4();
      h["X-Idempotency-Request-Hash"] = uuid4().replace(/-/g, "");
    }
    return h;
  }

  async function unwrap(res) {
    let body = null;
    try {
      body = await res.json();
    } catch {
      /* empty body */
    }
    if (!res.ok) {
      const msg =
        (body && (body.message || body.detail || body.error)) ||
        `${res.status} ${res.statusText}`;
      const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
      err.status = res.status;
      throw err;
    }
    // Engine envelope is {success, data, meta}; fall back to the raw body.
    return body && Object.prototype.hasOwnProperty.call(body, "data") ? body.data : body;
  }

  async function get(path) {
    const res = await fetch(path, { headers: headers(false) });
    return unwrap(res);
  }
  async function post(path, payload) {
    const res = await fetch(path, {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify(payload || {}),
    });
    return unwrap(res);
  }

  // --- Typed endpoint helpers ---------------------------------------------
  const listNodes = (type, limit = 200) => get(`${V1}/graph/nodes/${type}?limit=${limit}`);
  const listEdges = (type, limit = 500) => get(`${V1}/graph/edges/${type}?limit=${limit}`);
  const createNode = (type, properties) => post(`${V1}/graph/nodes/${type}`, { properties });

  const listDrafts = () => get(`${ADMIN}/quests/drafts`);
  const offerDraft = (questId) => post(`${ADMIN}/quests/${encodeURIComponent(questId)}/offer`, {});

  const engineStatus = () => get(`${V1}/system/engines`);
  const runtimeConfig = () => get(`${V1}/system/config`);
  const metrics = () => get(`${V1}/system/metrics`);
  const recentEvents = (limit = 25) => get(`${V1}/system/events?limit=${limit}`);

  async function ping() {
    // Cheap authenticated probe used by the Connect button.
    await engineStatus();
    return true;
  }

  return {
    getKey, setKey, ping,
    listNodes, listEdges, createNode,
    listDrafts, offerDraft,
    engineStatus, runtimeConfig, metrics, recentEvents,
  };
})();

window.NpcApi = NpcApi;
