/* Hydra Phase 9: WhatsApp screen — link by QR, recipients, which report goes to whom, send history. */
(function () {
  const { call, icon, esc, $, $$, toast, busy, modal, fmtTime } = Hydra;
  const { head } = Pages.util;
  const canEdit = () => App.user && App.user.role !== "user";
  const SCHIP = { queued: "", sending: "warn", sent: "ok", failed: "err", cancelled: "" };
  let poll = null;

  async function whatsappPage(main) {
    clearInterval(poll);
    const [st, rc, ty, hi] = await Promise.all([call("wa_state"), call("wa_recipients"), call("reports_types"), call("wa_history", 60)]);
    if (!st.ok) throw new Error(st.error);
    const edit = canEdit(), recips = rc.recipients || [], routes = rc.routes || {}, types = ty.types || [];
    main.innerHTML = `${head("Delivery", "WhatsApp", "Link Hydra to a WhatsApp number once, choose who gets each report, and every Approve &amp; Send goes out from here.")}
      <div class="cards c2" style="grid-template-columns:5fr 7fr;align-items:start">
        <div class="stack">
          <div class="card"><div class="card-h">${icon("message")}<h3>Link</h3><span class="spacer"></span><span id="wachip"></span></div><div class="card-b" id="walink"></div></div>
          ${edit ? `<div class="card"><div class="card-h">${icon("settings")}<h3>Sending options</h3></div><div class="card-b stack">
            <div class="row" style="gap:12px"><div class="field" style="flex:1"><label>Pause between messages (s)</label><input class="input" type="number" min="0" max="60" id="wgap" value="${st.settings.gap_s ?? 3}"></div>
              <div class="field" style="flex:1"><label>Give up on a message after (s)</label><input class="input" type="number" min="20" max="600" id="wto" value="${st.settings.send_timeout_s ?? 90}"></div></div>
            <label class="check"><input type="checkbox" id="wshow" ${st.settings.headless ? "" : "checked"}> Show the WhatsApp browser while sending (to watch or troubleshoot)</label>
            <details><summary class="faint" style="cursor:pointer">Advanced</summary><div class="field" style="margin-top:10px"><label>WhatsApp Web address</label><input class="input mono" id="wurl" value="${esc(st.settings.url || "")}"><div class="hint">Leave as https://web.whatsapp.com. Only change it for testing.</div></div></details>
            <div class="row"><span class="spacer"></span><button class="btn btn-secondary btn-sm" id="wsave">${icon("save")}Save options</button></div></div></div>` : ""}
        </div>
        <div class="stack">
          <div class="card"><div class="card-h">${icon("users")}<h3>Recipients</h3><span class="spacer"></span>${edit ? `<button class="btn btn-primary btn-sm" id="radd">${icon("plus")}Add recipient</button>` : ""}</div><div class="card-b">
            ${recips.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Name in WhatsApp</th><th>Type</th><th>Gets</th><th class="c">Active</th><th></th></tr></thead><tbody>
              ${recips.map((r) => `<tr class="${r.active ? "" : "muted"}"><td><b>${esc(r.name)}</b>${r.notes ? `<br><small class="faint">${esc(r.notes)}</small>` : ""}</td>
                <td>${r.kind === "group" ? `<span class="chip">${icon("users")}Group</span>` : `<span class="chip">${icon("user")}${esc(r.phone ? "+" + r.phone : "Contact")}</span>`}</td>
                <td class="muted" style="white-space:normal">${r.reports.length ? r.reports.map((t) => esc((types.find((x) => x.id === t) || {}).name || t)).join(", ") : `<span class="faint">nothing yet</span>`}</td>
                <td class="c">${r.active ? `<span class="chip ok">Yes</span>` : `<span class="chip">Paused</span>`}</td>
                <td><div class="row" style="gap:4px;justify-content:flex-end">${edit ? `<button class="btn btn-dark btn-sm" data-test="${r.id}" title="Send a short test message">${icon("send")}Test</button>
                  <button class="iconbtn sm" data-redit="${r.id}" title="Edit">${icon("edit")}</button><button class="iconbtn sm danger" data-rdel="${r.id}" title="Delete">${icon("trash")}</button>` : ""}</div></td></tr>`).join("")}
              </tbody></table></div>` : `<div class="empty" style="padding:24px"><h3>No recipients yet</h3>Add the WhatsApp groups (or people) that should receive reports. The name must match WhatsApp exactly.</div>`}
          </div></div>
          ${recips.length ? `<div class="card"><div class="card-h">${icon("send")}<h3>Who gets which report</h3><span class="spacer"></span>${edit ? `<button class="btn btn-secondary btn-sm" id="rsave" disabled>${icon("save")}Save</button>` : ""}</div><div class="card-b">
            <div class="table-wrap"><table class="table matrix"><thead><tr><th>Report</th>${recips.map((r) => `<th class="c" title="${esc(r.name)}">${esc(r.name)}</th>`).join("")}</tr></thead><tbody>
              ${types.map((t) => `<tr><td><b>${esc(t.name)}</b></td>${recips.map((r) => `<td class="c"><input type="checkbox" class="route" data-t="${t.id}" data-r="${r.id}" ${(routes[t.id] || []).includes(r.id) ? "checked" : ""} ${edit && r.active ? "" : "disabled"}></td>`).join("")}</tr>`).join("")}
            </tbody></table></div></div></div>` : ""}
        </div>
      </div>
      <div class="card" style="margin-top:16px"><div class="card-h">${icon("history")}<h3>Sent messages</h3><span class="spacer"></span><span class="faint" id="wpend"></span>
          ${st.pending ? `<button class="btn btn-dark btn-stop btn-sm" id="wcancel">${icon("stop")}Cancel waiting messages</button>` : ""}</div><div class="card-b">
        ${(hi.items || []).length ? `<div class="table-wrap" style="max-height:340px"><table class="table"><thead><tr><th>Time</th><th>To</th><th>Report</th><th>Files</th><th>Status</th></tr></thead><tbody>
          ${hi.items.map((x) => { const f = JSON.parse(x.files_json || "[]"); return `<tr><td class="faint">${fmtTime(x.sent_at || x.created_at)}</td><td><b>${esc(x.recipient)}</b></td>
            <td>${x.title ? esc(x.title) : `<span class="faint">${esc(x.caption || "")}</span>`}</td><td class="muted">${f.length ? f.length + " file" + (f.length > 1 ? "s" : "") + " · " + esc([...new Set(f.map((p) => p.split(".").pop().toUpperCase()))].join(" + ")) : "text"}</td>
            <td><span class="chip ${SCHIP[x.status]}" title="${esc(x.error || "")}">${esc(x.status)}</span>${x.error && x.status === "failed" ? `<br><small class="faint" style="white-space:normal">${esc(x.error)}</small>` : ""}</td></tr>`; }).join("")}
        </tbody></table></div>` : `<div class="faint">Nothing sent yet.</div>`}</div></div>`;

    drawLink(st);
    poll = setInterval(async () => {
      if (!document.body.contains($("#walink"))) return clearInterval(poll);
      const s = await call("wa_state");
      if (s.ok) drawLink(s);
    }, 1500);

    // ---- options
    if ($("#wsave")) $("#wsave").onclick = async () => {
      const s = await call("wa_settings_save", { url: $("#wurl").value, headless: !$("#wshow").checked, gap_s: $("#wgap").value, send_timeout_s: $("#wto").value });
      s.ok ? toast("success", "WhatsApp options saved") : toast("error", "Not saved", s.error);
    };
    const reload = () => whatsappPage(main).then(() => Hydra.hydrateIcons(main));
    // ---- recipients
    if ($("#radd")) $("#radd").onclick = () => recipientDialog(null, reload);
    $$("[data-redit]").forEach((b) => b.onclick = () => recipientDialog(recips.find((r) => r.id === +b.dataset.redit), reload));
    $$("[data-rdel]").forEach((b) => b.onclick = async () => {
      const r = recips.find((x) => x.id === +b.dataset.rdel);
      const ok = await modal({ title: `Delete ${r.name}?`, body: `<p class="muted">Hydra stops sending reports to this ${r.kind}. Past send history is kept.</p>`, buttons: [{ label: "Cancel", value: false }, { label: "Delete", cls: "btn-danger", value: true }] });
      if (!ok) return;
      const s = await call("wa_recipient_delete", r.id);
      s.ok ? reload() : toast("error", "Not deleted", s.error);
    });
    $$("[data-test]").forEach((b) => b.onclick = async () => {
      const s = await call("wa_test", +b.dataset.test);
      s.ok ? toast("info", "Test message queued", "Watch the Sent messages list below") : toast("error", "Not queued", s.error);
      setTimeout(reload, 400);
    });
    // ---- routes
    $$(".route").forEach((c) => c.onchange = () => { if ($("#rsave")) $("#rsave").disabled = false; });
    if ($("#rsave")) $("#rsave").onclick = async () => {
      const map = {};
      $$(".route").forEach((c) => { if (c.checked) (map[c.dataset.t] = map[c.dataset.t] || []).push(+c.dataset.r); });
      const s = await call("wa_routes_save", map);
      s.ok ? (toast("success", "Saved", "Approve & Send uses these recipients"), reload()) : toast("error", "Not saved", s.error);
    };
    if ($("#wcancel")) $("#wcancel").onclick = async () => { const s = await call("wa_cancel"); toast("warning", "Cancelled", `${s.cancelled || 0} waiting message(s)`); reload(); };
  }

  function drawLink(s) {
    const st = s.status, w = s.worker, edit = canEdit();
    const busyPhase = ["starting", "loading", "qr", "sending"].includes(w.phase);
    $("#wachip").innerHTML = st.linked ? `<span class="chip ok">Linked</span>` : w.phase === "qr" ? `<span class="chip warn">Waiting for scan</span>` : `<span class="chip">Not linked</span>`;
    let body;
    if (w.phase === "qr" && w.qr) {
      body = `<div class="qrbox"><img src="${w.qr}" alt="QR code"><ol>
          <li>Open <b>WhatsApp</b> on the phone that will send the reports</li>
          <li>Tap <b>⋮ / Settings → Linked devices → Link a device</b></li>
          <li>Point the phone at this code</li></ol>
          <div class="faint" style="font-size:12px">The code refreshes by itself. Hydra stays linked until you unlink it here or on the phone.</div></div>`;
    } else if (busyPhase) {
      body = `<div class="row" style="padding:10px 0"><span class="spinner"></span><span>${esc(w.message || "Working…")}</span></div>`;
    } else if (st.linked) {
      body = `<div class="linked"><div class="big">${icon("okcircle")}</div><div><b>${esc(st.number || "WhatsApp linked")}</b><div class="faint">Linked ${st.linked_at ? fmtTime(st.linked_at) : ""}</div>
          ${w.phase === "linked" && w.message ? `<div class="faint">${esc(w.message)}</div>` : ""}</div></div>`;
    } else {
      body = `<p class="muted" style="line-height:1.6;margin:0 0 12px">Hydra sends reports from WhatsApp Web, like a computer linked to the phone. Use a work number — every report goes out from it.</p>
        ${w.phase === "error" ? `<div class="alert err" style="margin-bottom:12px">${icon("error")}<div>${esc(w.message)}</div></div>` : ""}`;
    }
    const btns = !edit ? "" : busyPhase ? "" : st.linked
      ? `<button class="btn btn-dark btn-sm" id="wre">${icon("refresh")}Check link</button><button class="btn btn-ghost btn-sm" id="wun">Unlink</button>`
      : `<button class="btn btn-primary" id="wgo">${icon("link")}Link WhatsApp</button>`;
    const key = JSON.stringify([st.linked, w.phase, w.message, (w.qr || "").length, edit]);
    if ($("#walink").dataset.key === key) return;
    $("#walink").dataset.key = key;
    $("#walink").innerHTML = body + (btns ? `<div class="row" style="margin-top:12px">${btns}</div>` : "");
    Hydra.hydrateIcons($("#walink"));
    const go = async () => { const r = await call("wa_link"); if (!r.ok) toast("error", "Cannot start", r.error); };
    if ($("#wgo")) $("#wgo").onclick = go;
    if ($("#wre")) $("#wre").onclick = go;
    if ($("#wun")) $("#wun").onclick = async () => {
      const ok = await modal({ title: "Unlink WhatsApp?", body: `<p class="muted">Hydra logs out of WhatsApp Web on this PC. Reports can't be sent until you link again. (Also remove “Hydra” under Linked devices on the phone.)</p>`, buttons: [{ label: "Cancel", value: false }, { label: "Unlink", cls: "btn-danger", value: true }] });
      if (ok) { await call("wa_unlink"); toast("info", "Unlinking…"); }
    };
    App.refreshStatus();
  }

  async function recipientDialog(r, reload) {
    const d = r || { name: "", kind: "group", phone: "", notes: "", active: 1 };
    const v = await modal({ title: r ? `Edit ${r.name}` : "Add recipient", body: `<div class="stack">
        <div class="seg" id="rk"><button data-k="group" class="${d.kind === "group" ? "on" : ""}">Group</button><button data-k="contact" class="${d.kind === "contact" ? "on" : ""}">Person</button></div>
        <div class="field"><label>Name exactly as WhatsApp shows it</label><input class="input" id="rn" value="${esc(d.name)}" placeholder="e.g. Lakmee Management Reports"></div>
        <div class="field" id="rpf" style="${d.kind === "contact" ? "" : "display:none"}"><label>Mobile number</label><input class="input mono" id="rp" value="${esc(d.phone || "")}" placeholder="077 123 4567 or 94771234567">
          <div class="hint">With a number Hydra opens the chat directly — no need for the person to be saved in the phone's contacts.</div></div>
        <div class="field"><label>Note (optional)</label><input class="input" id="rno" value="${esc(d.notes || "")}" placeholder="e.g. NSM + RSMs"></div>
        <label class="check"><input type="checkbox" id="ra" ${d.active ? "checked" : ""}> Active — send reports to this ${d.kind === "group" ? "group" : "person"}</label></div>`,
      buttons: [{ label: "Cancel", value: null }, { label: r ? "Save" : "Add", cls: "btn-primary", value: (m) => ({ id: r && r.id, name: $("#rn", m).value, kind: $("#rk .on", m).dataset.k, phone: $("#rp", m).value, notes: $("#rno", m).value, active: $("#ra", m).checked }) }] });
    if (!v) return;
    const s = await call("wa_recipient_save", v);
    s.ok ? (toast("success", `${v.name} saved`, r ? "" : "Now tick the reports it should get"), reload()) : toast("error", "Not saved", s.error);
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("#rk button"); if (!b) return;
    $$("#rk button").forEach((x) => x.classList.toggle("on", x === b));
    $("#rpf").style.display = b.dataset.k === "contact" ? "" : "none";
  });

  Pages.whatsapp = whatsappPage;
})();
