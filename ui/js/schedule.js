/* Hydra Phase 10: Schedule — automatic runs, run history, tray / start-with-Windows. */
(function () {
  const { call, icon, esc, $, $$, toast, modal, fmtTime } = Hydra;
  const { head } = Pages.util;
  const canEdit = () => App.user && App.user.role !== "user";
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const MODE = { today: "Today", yesterday: "Yesterday", last_working: "Last working day" };
  const MODE_HINT = { today: "the same day it runs (for an evening run)", yesterday: "the day before it runs", last_working: "the day before, skipping Sunday — a Monday run reports Saturday" };
  const DELIV = {
    preview: ["eye", "Preview & approve", "Reports wait in Preview & Send; you check them and press Approve & Send."],
    send: ["send", "Send automatically", "Sent on WhatsApp straight away to each report's recipients — no approval."],
    save: ["save", "Save only", "Files are saved to the output folder; nothing is sent."],
  };
  const RCHIP = { done: "ok", partial: "warn", failed: "err", missed: "err", stopped: "", waiting: "warn", running: "warn" };
  const dayName = (iso) => new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
  function whenText(iso) {
    if (!iso) return "—";
    const d = new Date(iso), now = new Date();
    const t = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
    const days = Math.round((new Date(d.toDateString()) - new Date(now.toDateString())) / 86400000);
    return (days === 0 ? "Today" : days === 1 ? "Tomorrow" : d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" })) + " " + t;
  }
  let timer = null;

  async function schedulePage(main) {
    clearInterval(timer);
    const [r, ty] = await Promise.all([call("schedule_list"), call("reports_types")]);
    if (!r.ok) throw new Error(r.error);
    const types = ty.types || [], edit = canEdit(), st = r.status, bg = r.background;
    const tname = (id) => (types.find((t) => t.id === id) || {}).name || id;
    main.innerHTML = `${head("Delivery", "Schedule", "Hydra runs the reports by itself at these times — while Hydra is open or in the tray. If the day's data isn't in yet, it waits and tries again.",
        edit ? `<button class="btn btn-dark" id="spause">${icon(st.enabled ? "pause" : "play")}${st.enabled ? "Pause all" : "Resume"}</button><button class="btn btn-primary" id="snew">${icon("plus")}New schedule</button>` : "")}
      <div class="card sstatus ${st.state}" style="margin-bottom:16px"><div class="card-b row wrap" style="gap:22px">
        <div class="row"><span class="dot ${st.state === "on" || st.state === "running" ? "ok" : st.state === "paused" || st.state === "stopped" ? "err" : "warn"}"></span><b>${esc(st.label)}</b></div>
        <div><span class="faint">Next run</span> <b>${st.next ? esc(whenText(st.next.at)) + " — " + esc(st.next.name) : st.enabled ? "None scheduled" : "Paused"}</b></div>
        ${st.waiting ? `<div class="chip warn">${st.waiting} run(s) waiting for data</div>` : ""}
        <span class="spacer"></span><span class="faint" style="font-size:12px">Times are this PC's clock</span></div></div>
      ${r.schedules.length ? `<div class="sgrid">${r.schedules.map((s) => card(s, tname, edit)).join("")}</div>`
        : `<div class="card"><div class="empty"><img src="assets/img/hydra_logo_silver.png"><h3>No schedules yet</h3>Add one for each time the reports should go out — e.g. 08:30 every Mon–Sat for yesterday's reports.
            ${edit ? `<div style="margin-top:14px"><button class="btn btn-primary" id="snew2">${icon("plus")}New schedule</button></div>` : ""}</div></div>`}
      <div class="cards c2" style="grid-template-columns:2fr 1fr;align-items:start;margin-top:16px">
        <div class="card"><div class="card-h">${icon("history")}<h3>Runs</h3><span class="spacer"></span><span class="faint" style="font-size:12px">Manual and scheduled</span></div><div class="card-b">
          ${r.runs.length ? `<div class="table-wrap" style="max-height:420px"><table class="table"><thead><tr><th>Started</th><th>What</th><th>Report date</th><th>Status</th><th class="num">Reports</th><th>WhatsApp</th><th></th></tr></thead><tbody>
            ${r.runs.map((x) => `<tr><td class="faint">${fmtTime(x.started_at)}</td>
              <td><b>${esc(x.schedule_name || (x.trigger === "manual" ? "Run Center" : "Schedule"))}</b><br><small class="faint">${esc({ manual: "Manual", schedule: "On time", catch_up: "Caught up late" }[x.trigger] || x.trigger)} · ${esc({ preview: "Preview", send: "Auto-send", save: "Save only" }[x.delivery] || "")}</small></td>
              <td class="mono">${esc(x.report_date || "")}</td>
              <td><span class="chip ${RCHIP[x.status] || ""}">${esc(x.status)}</span>${x.message ? `<br><small class="faint" style="white-space:normal">${esc(x.message)}</small>` : ""}</td>
              <td class="num">${x.generated}${x.failed ? ` <span class="chip err">${x.failed} failed</span>` : ""}</td>
              <td class="muted">${x.wa ? Object.entries(x.wa).map(([k, v]) => `${v} ${k}`).join(", ") : ""}</td>
              <td>${x.generated ? `<button class="btn btn-ghost btn-sm" data-prev="${x.id}">${icon("eye")}Preview</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`
            : `<div class="faint">No runs yet.</div>`}</div></div>
        <div class="card"><div class="card-h">${icon("settings")}<h3>Keep running</h3></div><div class="card-b stack">
          <label class="row" style="gap:12px;align-items:flex-start"><span class="toggle"><input type="checkbox" id="btray" ${bg.close_to_tray ? "checked" : ""}><span></span></span>
            <span><b>Close to tray</b><br><small class="faint">Closing the window keeps Hydra running near the clock, so schedules still run. Quit from the tray icon.${bg.tray_supported ? "" : " (Needs Windows and the pystray package.)"}</small></span></label>
          <label class="row" style="gap:12px;align-items:flex-start"><span class="toggle"><input type="checkbox" id="bauto" ${bg.autostart ? "checked" : ""} ${bg.autostart_supported ? "" : "disabled"}><span></span></span>
            <span><b>Start with Windows</b><br><small class="faint">Hydra opens in the tray when you sign in to Windows${bg.autostart_supported ? "" : " (Windows only)"}.</small></span></label>
          <div class="alert info">${icon("info")}<div>Schedules only run while this PC is on and Hydra is running. A run missed by more than its catch-up window is shown as <b>missed</b>, with a notification.</div></div>
        </div></div>
      </div>`;

    const reload = () => schedulePage(main).then(() => Hydra.hydrateIcons(main));
    if ($("#snew")) $("#snew").onclick = () => dialog(null, types, reload);
    if ($("#snew2")) $("#snew2").onclick = () => dialog(null, types, reload);
    if ($("#spause")) $("#spause").onclick = async () => { await call("schedule_pause", st.enabled); toast(st.enabled ? "warning" : "success", st.enabled ? "Schedule paused" : "Schedule resumed"); App.refreshStatus(); reload(); };
    $$("[data-sedit]").forEach((b) => b.onclick = () => dialog(r.schedules.find((s) => s.id === +b.dataset.sedit), types, reload));
    $$("[data-sdel]").forEach((b) => b.onclick = async () => {
      const s = r.schedules.find((x) => x.id === +b.dataset.sdel);
      const ok = await modal({ title: `Delete ${s.name}?`, body: `<p class="muted">The ${s.time} schedule stops. Its past runs stay in the Runs list.</p>`, buttons: [{ label: "Cancel", value: false }, { label: "Delete", cls: "btn-danger", value: true }] });
      if (ok) { await call("schedule_delete", s.id); reload(); }
    });
    $$("[data-son]").forEach((c) => c.onchange = async () => { await call("schedule_active", +c.dataset.son, c.checked); App.refreshStatus(); reload(); });
    $$("[data-srun]").forEach((b) => b.onclick = async () => {
      const s = r.schedules.find((x) => x.id === +b.dataset.srun);
      const x = await call("schedule_run_now", s.id);
      if (!x.ok) return toast("error", "Cannot run now", x.error);
      toast("info", `${s.name} started`, `Reports for ${x.report_date} — ${DELIV[s.delivery][1].toLowerCase()}`);
      App.refreshStatus(); setTimeout(reload, 600);
    });
    $$("[data-prev]").forEach((b) => b.onclick = async () => {
      const x = await call("run_reports", +b.dataset.prev);
      x.ok && x.ids.length ? Pages.previewSend(x.ids) : toast("info", "No reports left to preview");
    });
    $("#btray").onchange = async (e) => { const x = await call("background_save", e.target.checked, null); x.ok ? toast("success", e.target.checked ? "Closing keeps Hydra in the tray" : "Closing quits Hydra") : toast("error", "Not saved", x.error); };
    $("#bauto").onchange = async (e) => { const x = await call("background_save", null, e.target.checked); if (!x.ok) { e.target.checked = !e.target.checked; return toast("error", "Not changed", x.error); } toast("success", x.autostart ? "Hydra starts with Windows" : "Hydra won't start with Windows"); };
    // refresh while something is running or waiting
    timer = setInterval(async () => {
      if (!document.body.contains($(".sstatus"))) return clearInterval(timer);
      const s2 = await call("status_bar");
      if (s2.ok && (s2.run.running || s2.worker.state !== st.state)) { clearInterval(timer); setTimeout(reload, s2.run.running ? 4000 : 0); }
    }, 5000);
  }

  function card(s, tname, edit) {
    const last = s.last_run;
    return `<div class="card scard ${s.active ? "" : "off"}"><div class="card-b stack" style="gap:10px">
      <div class="row"><div class="stime">${esc(s.time)}</div><div style="min-width:0"><b class="sname">${esc(s.name)}</b><div class="dpills">${DAYS.map((d, i) => `<span class="${s.days[i] === "1" ? "on" : ""}">${d[0]}</span>`).join("")}</div></div>
        <span class="spacer"></span>${edit ? `<label class="toggle" title="${s.active ? "On" : "Off"}"><input type="checkbox" data-son="${s.id}" ${s.active ? "checked" : ""}><span></span></label>` : ""}</div>
      <div class="sfacts">
        <span>Report date</span><b>${MODE[s.date_mode]}</b>
        <span>Reports</span><b>${s.report_types.length ? s.report_types.map(tname).map(esc).join(", ") : "All reports"}</b>
        <span>Then</span><b>${icon(DELIV[s.delivery][0])}${DELIV[s.delivery][1]}</b>
        <span>Next</span><b>${s.next_run ? esc(whenText(s.next_run)) + `<small class="faint"> · for ${esc(dayName(s.next_report_date))}</small>` : "—"}</b>
        <span>Last</span><b>${last ? `<span class="chip ${RCHIP[last.status] || ""}">${esc(last.status)}</span> <small class="faint">${fmtTime(last.started_at)}</small>` : `<span class="faint">never</span>`}</b>
      </div>
      ${last && last.message && last.status !== "done" ? `<div class="faint" style="font-size:12px">${esc(last.message)}</div>` : ""}
      <div class="row" style="gap:6px"><button class="btn btn-secondary btn-sm" data-srun="${s.id}">${icon("zap")}Run now</button><span class="spacer"></span>
        ${edit ? `<button class="iconbtn sm" data-sedit="${s.id}" title="Edit">${icon("edit")}</button><button class="iconbtn sm danger" data-sdel="${s.id}" title="Delete">${icon("trash")}</button>` : ""}</div>
    </div></div>`;
  }

  async function dialog(s, types, reload) {
    const d = s || { name: "", time: "08:30", days: "1111110", date_mode: "yesterday", report_types: [], formats: ["pdf", "png"], delivery: "preview", retry_min: 15, retry_max: 4, catch_up_min: 120, active: 1 };
    const all = !d.report_types.length;
    const isEdit = !!(s && s.id);
    const v = await modal({ title: isEdit ? `Edit ${s.name}` : "New schedule", wide: true, body: `<div class="stack sdlg">
        <div class="row" style="gap:12px;align-items:flex-end"><div class="field" style="width:140px"><label>Time</label><input class="input" type="time" id="dt" value="${esc(d.time)}"></div>
          <div class="field" style="flex:1"><label>Name</label><input class="input" id="dn" value="${esc(d.name)}" placeholder="e.g. Morning reports"></div></div>
        <div class="field"><label>Days</label><div class="dpills big" id="dd">${DAYS.map((x, i) => `<button type="button" class="${d.days[i] === "1" ? "on" : ""}">${x}</button>`).join("")}</div></div>
        <div class="field"><label>Report date</label><div class="seg" id="dm">${Object.entries(MODE).map(([k, l]) => `<button type="button" data-m="${k}" class="${k === d.date_mode ? "on" : ""}">${l}</button>`).join("")}</div><div class="hint" id="dmh"></div></div>
        <div class="field"><label>Reports</label><div class="row wrap" style="gap:6px 16px">${types.map((t) => `<label class="check"><input type="checkbox" class="dr" value="${t.id}" ${all || d.report_types.includes(t.id) ? "checked" : ""}> ${esc(t.name)}</label>`).join("")}</div></div>
        <div class="field"><label>Then</label><div class="dopts" id="dv">${Object.entries(DELIV).map(([k, [ic, l, h]]) => `<button type="button" data-v="${k}" class="${k === d.delivery ? "on" : ""}">${icon(ic)}<b>${l}</b><small>${h}</small></button>`).join("")}</div></div>
        <div class="field"><label>Files</label><div class="row" style="gap:16px"><label class="check"><input type="checkbox" id="fp" ${d.formats.includes("pdf") ? "checked" : ""}> PDF</label><label class="check"><input type="checkbox" id="fi" ${d.formats.includes("png") ? "checked" : ""}> WhatsApp images</label><span class="faint" style="font-size:12px">Excel is always made</span></div></div>
        <details ${s ? "" : ""}><summary class="faint" style="cursor:pointer">If the data isn't ready, or Hydra was closed</summary><div class="row wrap" style="gap:12px;margin-top:10px">
          <div class="field" style="width:170px"><label>Try again every (min)</label><input class="input" type="number" min="5" max="240" id="rm" value="${d.retry_min}"></div>
          <div class="field" style="width:150px"><label>Up to (times)</label><input class="input" type="number" min="0" max="24" id="rx" value="${d.retry_max}"></div>
          <div class="field" style="width:220px"><label>Still run if opened within (min)</label><input class="input" type="number" min="0" max="720" id="cu" value="${d.catch_up_min}"></div></div></details>
      </div>`,
      buttons: [{ label: "Cancel", value: null }, { label: isEdit ? "Save" : "Add schedule", cls: "btn-primary", value: (m) => {
        const days = $$("#dd button", m).map((b) => b.classList.contains("on") ? "1" : "0").join("");
        const picked = $$(".dr", m).filter((c) => c.checked).map((c) => c.value);
        return { id: isEdit ? s.id : null, active: isEdit ? !!s.active : true, name: $("#dn", m).value, time: $("#dt", m).value, days,
          date_mode: $("#dm .on", m).dataset.m, delivery: $("#dv .on", m).dataset.v,
          report_types: picked.length === types.length ? [] : picked,
          formats: [$("#fp", m).checked && "pdf", $("#fi", m).checked && "png"].filter(Boolean),
          retry_min: $("#rm", m).value, retry_max: $("#rx", m).value, catch_up_min: $("#cu", m).value };
      } }] , onOpen: (m) => {
        const hint = () => { const k = $("#dm .on", m).dataset.m; $("#dmh", m).textContent = "Reports for " + MODE_HINT[k] + "."; };
        $$("#dd button", m).forEach((b) => b.onclick = () => b.classList.toggle("on"));
        $$("#dm button", m).forEach((b) => b.onclick = () => { $$("#dm button", m).forEach((x) => x.classList.toggle("on", x === b)); hint(); });
        $$("#dv button", m).forEach((b) => b.onclick = () => $$("#dv button", m).forEach((x) => x.classList.toggle("on", x === b)));
        hint();
      } });
    if (!v) return;
    const x = await call("schedule_save", v);
    x.ok ? (toast("success", isEdit ? "Schedule saved" : "Schedule added", `${v.time} · ${MODE[v.date_mode]} · ${DELIV[v.delivery][1]}`), App.refreshStatus(), reload()) : (toast("error", "Not saved", x.error), dialog(Object.assign({}, s || {}, v, { id: isEdit ? s.id : null, name: v.name || (s && s.name) || "" }), types, reload));
  }

  Pages.schedule = schedulePage;
})();
