const $ = (s) => document.querySelector(s);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
  );
const labelDrafts = new Map();
let refreshRequest = null;
async function action(path, data = {}) {
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error("request failed");
    await load();
    $("#server").dataset.status = "Action completed";
  } catch (error) {
    $("#server").textContent = `Admin action failed: ${error.message}`;
  }
}
function render(state) {
  $("#count").textContent = state.devices.length;
  $("#runtime").textContent = state.server.admin;
  $("#phone-url").textContent = state.server.phone_url;
  $("#server").textContent = JSON.stringify(state.server, null, 2);
  const active = document.activeElement;
  if (active?.matches("[data-label]")) return;
  $("#devices").innerHTML = state.devices.length
    ? state.devices
        .map(
          (d) =>
            `<article class="card ${d.connected ? "device-connected" : "device-offline"}"><h3>${esc(d.label || `Device ${d.player || "unknown"}`)}</h3><div class="meta"><b class="device-status">${d.physical ? "Physical controller" : d.connected ? "Connected" : "Offline"}</b>${d.player ? ` · Player ${d.player}` : ""}${d.connected && d.remote ? ` · ${esc(d.remote)}` : ""}<br>${d.physical ? esc(d.path || "") : d.connected_at ? `Connected ${new Date(d.connected_at * 1000).toLocaleString()}` : "Not currently connected"}</div>${d.physical ? "" : `<input data-label="${esc(d.id)}" value="${esc(labelDrafts.get(d.id) ?? d.label ?? "")}" placeholder="Device label">`}<div class="actions">${d.physical ? "" : `<button data-save="${esc(d.id)}">Save label</button>`}<select data-player="${esc(d.id)}">${Array.from({ length: 8 }, (_, i) => `<option ${d.player === i + 1 ? "selected" : ""}>${i + 1}</option>`).join("")}</select><button data-assign="${esc(d.id)}">Assign</button>${!d.physical && d.connected ? `<button data-disconnect="${esc(d.id)}">Disconnect</button>` : ""}${!d.physical ? `<button class="danger" data-delete="${esc(d.id)}">Delete data</button>` : ""}</div></article>`,
        )
        .join("")
    : '<p class="meta">No phones connected.</p>';
}
async function load() {
  const refresh = $("#refresh");
  if (refreshRequest) return refreshRequest;
  if (refresh) refresh.disabled = true;
  refreshRequest = (async () => {
    try {
      const response = await fetch(`/api/state?_=${Date.now()}`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error("request failed");
      render(await response.json());
    } catch (e) {
      $("#server").textContent = `Admin server unavailable: ${e.message}`;
    } finally {
      if (refresh) refresh.disabled = false;
      refreshRequest = null;
    }
  })();
  return refreshRequest;
}
document.addEventListener("input", (e) => {
  const t = e.target;
  if (t.matches("[data-label]")) labelDrafts.set(t.dataset.label, t.value);
});
document.addEventListener("click", (e) => {
  const t = e.target;
  if (t.id === "refresh") {
    void load();
    return;
  }
  if (t.id === "reset" && confirm("Reset every controller?"))
    action("/api/reset");
  if (t.dataset.save) {
    const input = document.querySelector(
      `[data-label="${CSS.escape(t.dataset.save)}"]`,
    );
    labelDrafts.delete(t.dataset.save);
    action("/api/rename", { id: t.dataset.save, label: input.value });
  }
  if (t.dataset.assign)
    action("/api/assign", {
      id: t.dataset.assign,
      player: Number(
        document.querySelector(
          `[data-player="${CSS.escape(t.dataset.assign)}"]`,
        ).value,
      ),
    });
  if (t.dataset.disconnect && confirm("Disconnect this device?"))
    action("/api/disconnect", { id: t.dataset.disconnect });
  if (
    t.dataset.delete &&
    confirm("Delete this device's saved label, layout, and settings?")
  )
    action("/api/delete", { id: t.dataset.delete });
});
load();
setInterval(load, 3000);
