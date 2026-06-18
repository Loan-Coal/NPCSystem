// drafts.js — S12.3 quest-draft approval queue over GET /v1/admin/quests/drafts
// and POST /v1/admin/quests/{id}/offer.
"use strict";

const NpcDrafts = (() => {
  const { el, make, toast, fmt } = NpcUI;

  function card(draft) {
    const c = make("div", { cls: "card" });
    const head = make("div", { cls: "row" });
    head.appendChild(make("h4", { text: draft.title || draft.id }));
    head.appendChild(make("span", { cls: "badge draft", text: draft.status || "draft" }));
    c.appendChild(head);
    c.appendChild(make("div", { cls: "muted", text: `giver: ${fmt(draft.quest_giver_id)}` }));
    if (draft.description) c.appendChild(make("div", { text: fmt(draft.description).slice(0, 160) }));

    const actions = make("div", { cls: "row" });
    const btn = make("button", { cls: "primary", text: "Approve & Offer" });
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await NpcApi.offerDraft(draft.id);
        toast(`Offered "${draft.id}"`, "ok");
        await load();
      } catch (err) {
        btn.disabled = false;
        toast(`Offer: ${err.message}`, "err");
      }
    });
    actions.appendChild(btn);
    c.appendChild(actions);
    return c;
  }

  async function load() {
    const list = el("drafts-list");
    list.replaceChildren(make("p", { cls: "muted", text: "Loading…" }));
    const data = await NpcApi.listDrafts();
    const drafts = (data && data.drafts) || [];
    list.replaceChildren(
      ...(drafts.length ? drafts.map(card) : [make("p", { cls: "muted", text: "No pending drafts." })])
    );
  }

  function init() {
    el("drafts-refresh").addEventListener("click", () => NpcUI.guard(load, "Drafts"));
  }

  return { init, load };
})();

window.NpcDrafts = NpcDrafts;
