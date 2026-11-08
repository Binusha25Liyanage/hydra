/* Hydra Phase 5: Hierarchy & Targets (viewer + editor), Competition Calendar, Aliases & Labels. */
(function () {
  const { call, icon, esc, $, $$, toast, busy, modal } = Hydra;
  const { head, money } = Pages.util;
  const LV = ["National", "Region", "RSM", "ASM", "DTM", "ASE", "Territory"];
  const canEdit = () => App.user && App.user.role !== "user";
  const monthLabel = (s) => new Date(s + "-01T00:00:00").toLocaleString("en-GB", { month: "long", year: "numeric" });
  const thisMonth = () => new Date().toISOString().slice(0, 7);
  const addMonths = (m, k) => { const [y, mo] = m.split("-").map(Number); const d = new Date(y, mo - 1 + k, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; };
  const confirmBox = (title, text, ok = "Continue", cls = "btn-primary") =>
    modal({ title, body: `<p class="muted" style="line-height:1.6">${text}</p>`, buttons: [{ label: "Cancel", value: false }, { label: ok, cls, value: true }] });
  const ask = (title, label, value = "", hint = "") =>
    modal({ title, body: `<div class="field"><label>${esc(label)}</label><input class="input" id="askv" value="${esc(value)}">${hint ? `<div class="hint">${hint}</div>` : ""}</div>`,
      buttons: [{ label: "Cancel", value: null }, { label: "Save", cls: "btn-primary", value: (m) => $("#askv", m).value.trim() }] });

  // =================================================================================== Hierarchy & Targets
  async function targetsPage(main, _p, opts) {
    opts = typeof opts === "string" ? { month: opts } : (opts || {});
    const r = await call("targets_month", opts.month || "");
    if (!r.ok) throw new Error(r.error);
    if (!r.month) {
      main.innerHTML = `${head("Targets", "Hierarchy & Targets", "", buttons(null))}<div class="card"><div class="empty"><img src="assets/img/hydra_logo_silver.png"><h3>No targets yet</h3>
        Import a Target vs Achievement Excel with <b>Import targets…</b>, or import from Famulus on the <a href="#" id="tgo">SFA Data</a> screen.</div></div>`;
      $("#tgo").onclick = (e) => { e.preventDefault(); App.go("data"); };
      bind(main, null, r);
      return;
    }
    const m = r.month, locked = m.status === "locked";
    const editing = !!opts.edit && canEdit() && !locked;
    // flat list in display order + parent links, so totals can be recomputed live while editing
    const nodes = [], byId = {};
    (function walk(n, depth, parent) {
      n.depth = depth; n.parent = parent; nodes.push(n); byId[n.id] = n;
      n.children.forEach((k) => walk(k, depth + 1, n));
    })(r.tree[0] || { children: [], level: 0, label: "", id: 0 }, 0, null);
    const pending = {};   // id -> {field: value}

    main.innerHTML = `${head("Targets", "Hierarchy & Targets", editing
        ? "Editing — change targets and flags, then <b>Save changes</b>. Totals update as you type. Adding, moving, renaming and deleting rows save straight away."
        : "Monthly hierarchy and targets used by every report. Import them from a Target vs Achievement Excel or Famulus, or edit them here.",
        `<select class="input select" id="tmonth" style="width:180px" ${editing ? "disabled" : ""}>${r.months.map((x) => `<option value="${x}" ${x === m.month ? "selected" : ""}>${monthLabel(x)}</option>`).join("")}</select>` + buttons(m, editing))}
      ${locked ? `<div class="alert info" style="margin-bottom:14px">${icon("lock")}<div><b>${monthLabel(m.month)} is locked</b>Targets are final for this month and can't be edited. ${canEdit() ? "Unlock it to make changes." : ""}</div></div>` : ""}
      <div class="cards c4" style="margin-bottom:16px">
        <div class="card stat"><div class="k">${icon("tree")}National target</div><div class="v" id="st-nat"></div><div class="s" id="st-split"></div></div>
        <div class="card stat"><div class="k">${icon("calendar")}Working days (NOWD)</div><div class="row"><div class="v">${m.nowd ?? "—"}</div><span class="spacer"></span>${canEdit() && !locked ? `<button class="btn btn-ghost btn-sm" id="tnowd">${icon("settings")}Set</button>` : ""}</div><div class="s">${m.nowd ? (m.nowd_manual ? "Set manually" : "From calendar") : "Not set — the Day Report needs it"}</div></div>
        <div class="card stat"><div class="k">${icon("map")}Territories</div><div class="v" id="st-terr"></div><div class="s" id="st-terr2"></div></div>
        <div class="card stat"><div class="k">${icon("file")}Source · ${locked ? `<span class="chip">Locked</span>` : `<span class="chip ok">Draft</span>`}</div><div class="v" style="font-size:16px">${esc(m.source || "—")}</div><div class="s" title="${esc(m.source_file || "")}">${esc(m.source_file || "")}</div></div></div>
      <div class="card"><div class="card-h"><div class="search" style="flex:1;max-width:340px">${icon("search")}<input class="input" id="tfind" placeholder="Find a territory, ASE, ASM…"></div><span class="spacer"></span>
          <span class="faint" id="tfcount"></span></div>
        <div class="card-b"><div class="table-wrap" style="max-height:calc(100vh - ${editing ? 420 : 380}px)"><table class="table ttable ${editing ? "editing" : ""}"><thead><tr><th>Hierarchy</th><th>Level</th>
          ${editing ? `<th class="num" style="width:150px">Target</th><th class="c">SMMT</th><th class="c">Vacant</th><th class="c">Red</th>` : ""}
          <th class="num">GT target</th><th class="num">SMMT target</th>${editing ? `<th style="width:120px"></th>` : `<th>Distributor</th><th>CSR</th><th>SFA name</th>`}</tr></thead><tbody id="tbody">
          ${nodes.map((n) => rowHtml(n, editing)).join("")}</tbody></table></div></div></div>
      ${editing ? `<div class="savebar" id="savebar"><span id="sbtext">No changes</span><span class="spacer"></span>
          <button class="btn btn-dark" id="tdiscard">Discard</button><button class="btn btn-primary" id="tsave" disabled>${icon("save")}Save changes</button></div>` : ""}`;

    function totals() {
      (function sum(n) {
        if (n.level === 6) { const t = Number(n.target) || 0; n.gt = n.is_smmt ? 0 : t; n.smmt = n.is_smmt ? t : 0; }
        else { n.gt = 0; n.smmt = 0; n.children.forEach((k) => { sum(k); n.gt += k.gt; n.smmt += k.smmt; }); }
      })(nodes[0]);
      nodes.forEach((n) => {
        const tr = $(`#tbody tr[data-id="${n.id}"]`); if (!tr) return;
        tr.querySelector(".gt").textContent = n.gt ? money(n.gt) : "—";
        tr.querySelector(".sm").textContent = n.smmt ? money(n.smmt) : "—";
      });
      const nat = nodes[0], terr = nodes.filter((n) => n.level === 6);
      $("#st-nat").textContent = money(nat.gt + nat.smmt);
      $("#st-split").textContent = `GT ${money(nat.gt)} · SMMT ${money(nat.smmt)}`;
      $("#st-terr").textContent = terr.length;
      $("#st-terr2").textContent = `${terr.filter((n) => n.is_operating === 0).length} vacant · ${nodes.filter((n) => n.flagged_red).length} flagged red`;
      const n = Object.keys(pending).length;
      if ($("#savebar")) { $("#sbtext").innerHTML = n ? `<b>${n}</b> row${n > 1 ? "s" : ""} changed — not saved yet` : "No changes"; $("#tsave").disabled = !n; $("#savebar").classList.toggle("dirty", !!n); }
    }
    totals();

    // ---- search
    $("#tfind").oninput = (e) => {
      const q = e.target.value.trim().toLowerCase();
      const show = new Set();
      if (q) nodes.forEach((n) => { if (n.label.toLowerCase().includes(q) || (n.sfa_territory || "").toLowerCase().includes(q)) { let p = n; while (p) { show.add(p.id); p = p.parent; } } });
      $$("#tbody tr").forEach((tr) => { tr.classList.toggle("hidden", !!q && !show.has(+tr.dataset.id)); tr.classList.toggle("hit", !!q && nodes.find((n) => n.id === +tr.dataset.id)?.label.toLowerCase().includes(q)); });
      $("#tfcount").textContent = q ? `${[...show].filter((id) => byId[id].level === 6).length} territories` : "";
    };

    // ---- editing
    function change(id, field, value) {
      const n = byId[id];
      n[field] = value;
      pending[id] = Object.assign(pending[id] || {}, { [field]: value });
      $(`#tbody tr[data-id="${id}"]`).classList.add("changed");
      if (field === "is_operating") $(`#tbody tr[data-id="${id}"] .vac`).classList.toggle("hidden", value !== 0);
      if (field === "is_smmt") $(`#tbody tr[data-id="${id}"] .smc`).classList.toggle("hidden", !value);
      if (field === "flagged_red") $(`#tbody tr[data-id="${id}"] td.lbl`).classList.toggle("red", !!value);
      totals();
    }
    async function savePending(quiet) {
      const changes = Object.entries(pending).map(([id, f]) => Object.assign({ id: +id }, f));
      if (!changes.length) return true;
      const s = await call("targets_update", changes);
      if (!s.ok) { toast("error", "Not saved", s.error); return false; }
      Object.keys(pending).forEach((k) => delete pending[k]);
      if (!quiet) toast("success", "Targets saved", `${s.result} row(s) updated`);
      return true;
    }
    const reload = (o) => targetsPage(main, _p, Object.assign({ month: m.month }, o)).then(() => Hydra.hydrateIcons(main));
    if (editing) {
      $$("#tbody input.tgt").forEach((inp) => {
        inp.oninput = () => change(+inp.closest("tr").dataset.id, "target", Number(inp.value.replace(/,/g, "")) || 0);
        inp.onblur = () => { const v = Number(inp.value.replace(/,/g, "")) || 0; inp.value = v ? money(v) : ""; };
        inp.onfocus = () => { inp.value = inp.value.replace(/,/g, ""); inp.select(); };
        inp.onkeydown = (e) => { if (e.key === "Enter" || e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); const all = $$("#tbody tr:not(.hidden) input.tgt"); const i = all.indexOf(inp) + (e.key === "ArrowUp" ? -1 : 1); if (all[i]) all[i].focus(); } };
      });
      $$("#tbody input.flag").forEach((c) => c.onchange = () => {
        const f = c.dataset.f; change(+c.closest("tr").dataset.id, f, f === "is_operating" ? (c.checked ? 0 : 1) : (c.checked ? 1 : 0));
      });
      $("#tdiscard").onclick = async () => { if (!Object.keys(pending).length || await confirmBox("Discard changes?", "Your unsaved target changes will be lost.", "Discard", "btn-danger")) reload({ edit: false }); };
      $("#tsave").onclick = async () => { busy($("#tsave"), true, "Saving…"); const ok = await savePending(); busy($("#tsave"), false); if (ok) reload({ edit: true }); };
      $$("#tbody [data-act]").forEach((b) => b.onclick = async () => {
        const n = byId[+b.closest("tr").dataset.id];
        if (!(await savePending(true))) return;
        const act = b.dataset.act;
        if (act === "rename") {
          const v = await ask(`Rename ${LV[n.level]}`, "Name", n.label, n.level === 6 ? "The name shown on every report. If SFA spells it differently, set the SFA name on Aliases &amp; Labels." : "");
          if (!v || v === n.label) return;
          const s = await call("targets_update", [{ id: n.id, label: v }]);
          s.ok ? reload({ edit: true }) : toast("error", "Not renamed", s.error);
        } else if (act === "add") {
          const child = LV[n.level + 1];
          const v = await modal({ title: `Add ${child} under ${n.label}`, body: `<div class="stack"><div class="field"><label>${child} name</label><input class="input" id="an"></div>
              ${n.level === 5 ? `<div class="field"><label>Monthly target</label><input class="input" id="at" type="number" min="0" value="0"></div><label class="check"><input type="checkbox" id="as"> SMMT territory</label>` : ""}</div>`,
            buttons: [{ label: "Cancel", value: null }, { label: "Add", cls: "btn-primary", value: (mm) => ({ label: $("#an", mm).value.trim(), target: $("#at", mm) ? $("#at", mm).value : 0, smmt: $("#as", mm) ? $("#as", mm).checked : false }) }] });
          if (!v || !v.label) return;
          const s = await call("targets_add", n.id, v.label, v.target, v.smmt);
          s.ok ? (toast("success", `${v.label} added`), reload({ edit: true })) : toast("error", "Not added", s.error);
        } else if (act === "move") {
          const p = await call("targets_parents", m.month, n.level);
          if (!p.ok) return toast("error", "Cannot move", p.error);
          const v = await modal({ title: `Move ${n.label}`, body: `<div class="field"><label>New ${LV[n.level - 1]}</label><select class="input select" id="mp">${p.parents.map((x) => `<option value="${x.id}" ${x.id === n.parent.id ? "selected" : ""}>${esc(x.path)}</option>`).join("")}</select>
              <div class="hint">Its target and flags move with it; every total above updates.</div></div>`,
            buttons: [{ label: "Cancel", value: null }, { label: "Move", cls: "btn-primary", value: (mm) => +$("#mp", mm).value }] });
          if (!v || v === n.parent.id) return;
          const s = await call("targets_move", n.id, v);
          s.ok ? (toast("success", `${n.label} moved`), reload({ edit: true })) : toast("error", "Not moved", s.error);
        } else if (act === "delete") {
          if (!(await confirmBox(`Delete ${n.label}?`, `${LV[n.level]} <b>${esc(n.label)}</b> is removed from ${monthLabel(m.month)} only. Other months are not changed.`, "Delete", "btn-danger"))) return;
          const s = await call("targets_delete", n.id);
          s.ok ? (toast("success", `${n.label} deleted`), reload({ edit: true })) : toast("error", "Not deleted", s.error);
        }
      });
      // warn before leaving the page with unsaved edits
      $$("#nav a").forEach((a) => a.addEventListener("click", (e) => {
        if (Object.keys(pending).length && document.body.contains($("#savebar")) && !window.confirm("You have unsaved target changes. Leave without saving?")) { e.stopImmediatePropagation(); e.preventDefault(); }
      }, { capture: true, once: true }));
    }
    $("#tmonth").onchange = (e) => targetsPage(main, _p, { month: e.target.value }).then(() => Hydra.hydrateIcons(main));
    bind(main, m, r, reload);
  }

  function rowHtml(n, editing) {
    const terr = n.level === 6;
    const lbl = `<td class="lbl ${n.flagged_red ? "red" : ""}" style="padding-left:${12 + n.depth * 18}px;${terr ? "" : "font-weight:600"}">${esc(n.label)}
      <span class="chip cherry smc ${n.is_smmt && terr ? "" : "hidden"}" style="height:18px">SMMT</span><span class="chip warn vac ${terr && n.is_operating === 0 ? "" : "hidden"}" style="height:18px">Vacant</span></td>`;
    const cells = `<td class="num gt"></td><td class="num sm"></td>`;
    if (!editing) {
      return `<tr data-id="${n.id}" class="${terr ? "" : "sub"}">${lbl}<td class="faint">${LV[n.level]}</td>${cells}
        <td class="muted">${terr ? esc(n.distributor || "") : ""}</td><td class="muted">${terr ? esc(n.csr || "") : ""}</td><td class="muted">${terr && n.sfa_territory ? esc(n.sfa_territory) : ""}</td></tr>`;
    }
    const chk = (f, on) => `<td class="c">${terr || f === "flagged_red" ? `<input type="checkbox" class="flag" data-f="${f}" ${on ? "checked" : ""}>` : ""}</td>`;
    const acts = [
      `<button class="iconbtn sm" data-act="rename" title="Rename">${icon("edit")}</button>`,
      n.level < 6 ? `<button class="iconbtn sm" data-act="add" title="Add ${LV[n.level + 1]} under this">${icon("plus")}</button>` : "",
      n.level > 1 ? `<button class="iconbtn sm" data-act="move" title="Move under another ${LV[n.level - 1]}">${icon("move")}</button>` : "",
      n.level > 0 && !n.children.length ? `<button class="iconbtn sm danger" data-act="delete" title="Delete">${icon("trash")}</button>` : "",
    ].join("");
    return `<tr data-id="${n.id}" class="${terr ? "" : "sub"}">${lbl}<td class="faint">${LV[n.level]}</td>
      <td class="num">${terr ? `<input class="input tgt" inputmode="decimal" value="${n.target ? money(n.target) : ""}" placeholder="0">` : ""}</td>
      ${chk("is_smmt", n.is_smmt)}${chk("is_operating", n.is_operating === 0)}${chk("flagged_red", n.flagged_red)}${cells}<td><div class="row" style="gap:4px;justify-content:flex-end">${acts}</div></td></tr>`;
  }

  function buttons(m, editing) {
    if (!canEdit()) return "";
    if (editing) return "";
    const b = [];
    if (m) {
      b.push(m.status === "locked"
        ? `<button class="btn btn-dark" id="tlock">${icon("unlock")}Unlock</button>`
        : `<button class="btn btn-dark" id="tlock">${icon("lock")}Lock month</button><button class="btn btn-secondary" id="tedit">${icon("edit")}Edit targets</button>`);
      b.push(`<button class="btn btn-secondary" id="tnew">${icon("plus")}New month…</button>`);
    }
    b.push(`<button class="btn btn-primary" id="timport">${icon("download")}Import targets…</button>`);
    return b.join("");
  }

  function bind(main, m, r, reload) {
    reload = reload || ((o) => targetsPage(main, null, o).then(() => Hydra.hydrateIcons(main)));
    const month = m && m.month;
    if ($("#tedit")) $("#tedit").onclick = () => reload({ month, edit: true });
    if ($("#tlock")) $("#tlock").onclick = async () => {
      const lock = m.status !== "locked";
      if (lock && !(await confirmBox(`Lock ${monthLabel(month)}?`, "Locking marks the targets as final. Nobody can edit them until an admin unlocks the month. Reports keep working as normal.", "Lock month"))) return;
      const s = await call("targets_lock", month, lock);
      s.ok ? (toast("success", lock ? "Month locked" : "Month unlocked"), reload({ month })) : toast("error", "Not changed", s.error);
    };
    if ($("#tnew")) $("#tnew").onclick = async () => {
      const next = addMonths(r.months[0], 1);
      const v = await modal({ title: "Start a new month", body: `<div class="stack">
          <p class="muted" style="line-height:1.6">Copies the hierarchy (regions, managers, territories, SMMT and vacant flags, SFA names) from an existing month. Then edit the targets the NSM sends.</p>
          <div class="row" style="gap:12px"><div class="field" style="flex:1"><label>New month</label><input class="input" type="month" id="nm" value="${next}"></div>
          <div class="field" style="flex:1"><label>Copy from</label><select class="input select" id="nf">${r.months.map((x) => `<option value="${x}">${monthLabel(x)}</option>`).join("")}</select></div></div>
          <label class="check"><input type="checkbox" id="nk"> Keep the old targets as a starting point (otherwise every target starts at 0)</label></div>`,
        buttons: [{ label: "Cancel", value: null }, { label: "Create month", cls: "btn-primary", value: (mm) => ({ dst: $("#nm", mm).value, src: $("#nf", mm).value, keep: $("#nk", mm).checked }) }] });
      if (!v || !v.dst) return;
      const s = await call("targets_copy_month", v.src, v.dst, v.keep);
      s.ok ? (toast("success", `${monthLabel(v.dst)} created`, `${s.result} rows copied — now enter the targets`), reload({ month: v.dst, edit: true })) : toast("error", "Not created", s.error);
    };
    if ($("#tnowd")) $("#tnowd").onclick = async () => {
      const v = await modal({ title: "Working days (NOWD)", body: `<div class="field"><label>Working days in ${esc(monthLabel(month))}</label><input class="input" type="number" min="1" max="31" id="nw" value="${esc(m.nowd ?? "")}">
          <div class="hint">From the NSM's competition calendar (e.g. November 2026 = 24: 30 days − 5 Sundays − Poya).</div></div>`,
        buttons: [{ label: "Cancel", value: null }, { label: "Save", cls: "btn-primary", value: (mm) => $("#nw", mm).value }] });
      if (!v) return;
      const s = await call("targets_set_nowd", month, v);
      s.ok ? (toast("success", "NOWD saved"), reload({ month })) : toast("error", "Not saved", s.error);
    };
    if ($("#timport")) $("#timport").onclick = async () => {
      const pick = await call("targets_choose_file");
      if (!pick.ok || !pick.path) return;
      const f = await call("targets_inspect", pick.path);
      if (!f.ok) return toast("error", "Cannot read targets", f.error);
      const v = await modal({ title: "Import targets", body: `<div class="stack">
          <div><b>${esc(f.file_name)}</b></div>
          <div class="row wrap" style="gap:18px"><span><span class="faint">Territories</span> <b>${f.territories}</b></span><span><span class="faint">GT</span> <b>${money(f.gt_total)}</b></span><span><span class="faint">SMMT</span> <b>${money(f.smmt_total)}</b></span><span><span class="faint">National</span> <b>${money(f.total)}</b></span></div>
          ${f.warnings.length ? `<div class="alert warn">${icon("warn")}<div>${f.warnings.map(esc).join("<br>")}</div></div>` : `<div class="alert ok">${icon("okcircle")}<div>Every subtotal adds up.</div></div>`}
          <div class="field"><label>Targets are for month</label><input class="input" type="month" id="tm" value="${esc(f.month || "")}"></div>
          ${f.exists ? `<label class="check"><input type="checkbox" id="tov"> Replace the targets already saved for this month</label>` : ""}</div>`,
        buttons: [{ label: "Cancel", value: null }, { label: "Import", cls: "btn-primary", value: (mm) => ({ month: $("#tm", mm).value, over: $("#tov", mm) ? $("#tov", mm).checked : false }) }] });
      if (!v) return;
      const s = await call("targets_import", pick.path, v.month, v.over);
      s.ok ? (toast("success", `Targets imported for ${v.month}`, `${s.territories} territories`), reload({ month: v.month })) : toast("error", "Not imported", s.error);
    };
  }

  // =================================================================================== Competition Calendar
  const PALETTE = ["#B3172F", "#2E7D5B", "#2F6DB5", "#C27C0E", "#7B3FA0", "#0E8A8A", "#B04A7A", "#5E6B78"];

  async function calendarPage(main, _p, opts) {
    const month = (opts && opts.month) || (calendarPage.last || thisMonth());
    calendarPage.last = month;
    const r = await call("competition_month", month);
    if (!r.ok) throw new Error(r.error);
    const edit = canEdit();
    const rounds = r.rounds, byId = Object.fromEntries(rounds.map((x) => [x.id, x]));
    const assign = {};                 // date -> round id
    rounds.forEach((x) => x.days.forEach((d) => assign[d] = x.id));
    const saved = JSON.stringify(assign);
    let brush = rounds.length ? rounds[0].id : 0, anchor = null;
    const [y, mo] = month.split("-").map(Number);
    const first = new Date(y, mo - 1, 1), lead = (first.getDay() + 6) % 7;      // Monday first
    const iso = (d) => `${month}-${String(d).padStart(2, "0")}`;
    const today = new Date().toISOString().slice(0, 10);
    const D = (lim) => `${money(lim[0])} / ${lim[1]} bills`;

    main.innerHTML = `${head("Delivery", "Competition Calendar", "The NSM's competition rounds for Daily Winners. Each round has its own Van and Pre-Selling winner limits; a day that belongs to no round has no Daily Winners report.",
        `<button class="btn btn-ghost" id="cprev" title="Previous month">${icon("left")}</button><input class="input" type="month" id="cmonth" value="${month}" style="width:170px"><button class="btn btn-ghost" id="cnext" title="Next month">${icon("right")}</button>
         ${edit ? `<button class="btn btn-secondary" id="ccopy" ${rounds.length ? "disabled" : ""}>${icon("copy")}Copy rounds from ${monthLabel(addMonths(month, -1)).split(" ")[0]}</button><button class="btn btn-primary" id="cnew">${icon("plus")}New round</button>` : ""}`)}
      ${rounds.length ? "" : `<div class="alert info" style="margin-bottom:14px">${icon("info")}<div><b>No rounds for ${monthLabel(month)}</b>Until rounds are added, Daily Winners runs every day with the default limits — Van ${D(r.defaults.van)}, Pre-Selling ${D(r.defaults.pre)}.</div></div>`}
      <div class="calwrap">
        <div class="stack">
          <div class="card"><div class="card-h">${icon("flag")}<h3>Rounds</h3><span class="spacer"></span>${edit && rounds.length ? `<span class="faint" style="font-size:12px">Pick one, then click days</span>` : ""}</div><div class="card-b stack" id="rounds">
            ${rounds.map((x) => `<div class="round ${x.id === brush ? "on" : ""}" data-id="${x.id}" style="--rc:${esc(x.colour || "#B3172F")}">
                <div class="row"><span class="sw"></span><b>${esc(x.name)}</b><span class="spacer"></span><span class="chip" data-count="${x.id}"></span>
                ${edit ? `<button class="iconbtn sm" data-edit="${x.id}" title="Edit round">${icon("edit")}</button><button class="iconbtn sm danger" data-del="${x.id}" title="Delete round">${icon("trash")}</button>` : ""}</div>
                <div class="lim"><span>Van</span><b>${D([x.van_sale_limit, x.van_bill_limit])}</b><span>Pre</span><b>${D([x.pre_sale_limit, x.pre_bill_limit])}</b></div></div>`).join("")
              || `<div class="faint">No rounds yet.${edit ? " Press <b>New round</b> and enter the name and limits from the NSM's calendar." : ""}</div>`}
            ${edit && rounds.length ? `<div class="round eraser ${brush === 0 ? "on" : ""}" data-id="0"><div class="row"><span class="sw"></span><b>No round</b><span class="spacer"></span><span class="faint" style="font-size:12px">clears days</span></div></div>` : ""}
          </div></div>
          <div class="card"><div class="card-b stack" style="gap:8px" id="csum"></div></div>
        </div>
        <div class="card"><div class="card-h">${icon("calendar")}<h3>${monthLabel(month)}</h3><span class="spacer"></span>
            ${edit && rounds.length ? `<button class="btn btn-ghost btn-sm" id="cfill">${icon("zap")}Fill Mon–Sat</button><button class="btn btn-ghost btn-sm" id="cclear">Clear month</button>` : ""}</div>
          <div class="card-b"><div class="cal" id="cal">
            ${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => `<div class="dow">${d}</div>`).join("")}
            ${Array.from({ length: lead }, () => `<div class="day pad"></div>`).join("")}
            ${Array.from({ length: r.days_in_month }, (_, i) => { const ds = iso(i + 1), sun = new Date(y, mo - 1, i + 1).getDay() === 0;
              return `<div class="day ${sun ? "sun" : ""} ${ds === today ? "today" : ""}" data-d="${ds}"><span class="n">${i + 1}</span><span class="tag"></span>${r.winners[ds] ? `<span class="wdot" title="Daily Winners: ${esc(r.winners[ds])}"></span>` : ""}</div>`; }).join("")}
          </div>
          ${edit && rounds.length ? `<div class="hint" style="margin-top:10px">Click a day to give it the selected round (click again to clear). Shift-click to fill a range — Sundays are skipped. ● = Daily Winners already generated.</div>` : ""}</div>
          ${edit && rounds.length ? `<div class="savebar inline" id="csave"><span id="cstext"></span><span class="spacer"></span><button class="btn btn-dark" id="cundo">Undo changes</button><button class="btn btn-primary" id="cok" disabled>${icon("save")}Save calendar</button></div>` : ""}
        </div>
      </div>`;

    function paint() {
      $$("#cal .day[data-d]").forEach((el) => {
        const rid = assign[el.dataset.d], x = byId[rid];
        el.style.setProperty("--rc", x ? x.colour || "#B3172F" : "transparent");
        el.classList.toggle("in", !!x);
        el.querySelector(".tag").textContent = x ? x.name : "";
      });
      const count = {}; Object.values(assign).forEach((id) => count[id] = (count[id] || 0) + 1);
      $$("[data-count]").forEach((c) => c.textContent = `${count[c.dataset.count] || 0} days`);
      const comp = Object.keys(assign).length, work = r.days_in_month - r.sundays;
      $("#csum").innerHTML = `
        <div class="row"><span class="faint">Competition days</span><span class="spacer"></span><b>${rounds.length ? comp : "Every day"}</b></div>
        <div class="row"><span class="faint">Days in month · Sundays</span><span class="spacer"></span><b>${r.days_in_month} · ${r.sundays}</b></div>
        <div class="row"><span class="faint">Mon–Sat</span><span class="spacer"></span><b>${work}</b></div>
        <div class="row"><span class="faint">NOWD (Hierarchy &amp; Targets)</span><span class="spacer"></span><b>${r.nowd ?? "not set"}</b></div>
        ${r.nowd && rounds.length && comp && comp !== r.nowd ? `<div class="alert warn" style="margin-top:4px">${icon("warn")}<div>${comp} competition days but NOWD is ${r.nowd}. That's fine if some working days aren't in a round — otherwise check the calendar or NOWD.</div></div>` : ""}`;
      Hydra.hydrateIcons($("#csum"));
      if ($("#csave")) {
        const dirty = JSON.stringify(sorted(assign)) !== JSON.stringify(sorted(JSON.parse(saved)));
        $("#cok").disabled = !dirty; $("#cundo").disabled = !dirty;
        $("#cstext").innerHTML = dirty ? "<b>Calendar changed</b> — not saved yet" : "All changes saved";
        $("#csave").classList.toggle("dirty", dirty);
      }
    }
    const sorted = (o) => Object.fromEntries(Object.entries(o).sort());
    paint();

    // round selection / edit / delete
    $$("#rounds .round").forEach((el) => el.onclick = (e) => {
      if (e.target.closest("[data-edit],[data-del]")) return;
      brush = +el.dataset.id;
      $$("#rounds .round").forEach((y2) => y2.classList.toggle("on", y2 === el));
    });
    const reload = (o) => calendarPage(main, _p, Object.assign({ month }, o)).then(() => Hydra.hydrateIcons(main));
    if (edit) {
      $$("#cal .day[data-d]").forEach((el) => el.onclick = (e) => {
        if (!rounds.length) return toast("info", "Add a round first", "Press New round and enter the NSM's limits.");
        const ds = el.dataset.d;
        if (e.shiftKey && anchor) {
          const [a, b] = [anchor, ds].sort();
          $$("#cal .day[data-d]").forEach((x) => { const d = x.dataset.d; if (d >= a && d <= b && !x.classList.contains("sun")) brush ? assign[d] = brush : delete assign[d]; });
        } else if (brush && assign[ds] === brush) delete assign[ds];
        else brush ? assign[ds] = brush : delete assign[ds];
        anchor = ds; paint();
      });
      if ($("#cfill")) $("#cfill").onclick = () => { if (!brush) return toast("info", "Pick a round first"); $$("#cal .day[data-d]:not(.sun)").forEach((x) => { if (!assign[x.dataset.d]) assign[x.dataset.d] = brush; }); paint(); };
      if ($("#cclear")) $("#cclear").onclick = () => { Object.keys(assign).forEach((k) => delete assign[k]); paint(); };
      if ($("#cundo")) $("#cundo").onclick = () => reload();
      if ($("#cok")) $("#cok").onclick = async () => {
        busy($("#cok"), true, "Saving…");
        const s = await call("competition_save_days", month, assign);
        busy($("#cok"), false);
        s.ok ? (toast("success", "Calendar saved", `${s.result} competition day(s)`), reload()) : toast("error", "Not saved", s.error);
      };
      $("#cnew").onclick = () => roundDialog(month, null, rounds.length, reload);
      $$("[data-edit]").forEach((b) => b.onclick = () => roundDialog(month, byId[+b.dataset.edit], 0, reload));
      $$("[data-del]").forEach((b) => b.onclick = async () => {
        const x = byId[+b.dataset.del];
        if (!(await confirmBox(`Delete ${x.name}?`, `The round and its ${x.days.length} day(s) are removed from ${monthLabel(month)}.`, "Delete", "btn-danger"))) return;
        const s = await call("competition_delete_round", x.id);
        s.ok ? reload() : toast("error", "Not deleted", s.error);
      });
      if ($("#ccopy")) $("#ccopy").onclick = async () => {
        const s = await call("competition_copy", addMonths(month, -1), month);
        s.ok ? (toast("success", `${s.result} round(s) copied`, "Names and limits only — now click the days"), reload()) : toast("error", "Nothing copied", s.error);
      };
    }
    const go = (mm) => { if (mm) calendarPage(main, _p, { month: mm }).then(() => Hydra.hydrateIcons(main)); };
    $("#cmonth").onchange = (e) => go(e.target.value);
    $("#cprev").onclick = () => go(addMonths(month, -1));
    $("#cnext").onclick = () => go(addMonths(month, 1));
  }

  async function roundDialog(month, x, n, reload) {
    const d = x || { name: `Round ${n + 1}`, colour: PALETTE[n % PALETTE.length], van_sale_limit: 100000, van_bill_limit: 20, pre_sale_limit: 125000, pre_bill_limit: 30 };
    const v = await modal({ title: x ? `Edit ${x.name}` : "New round", body: `<div class="stack">
        <div class="row" style="gap:12px;align-items:flex-end"><div class="field" style="flex:1"><label>Name</label><input class="input" id="rn" value="${esc(d.name)}"></div>
          <div class="field"><label>Colour</label><div class="swatches">${PALETTE.map((c) => `<button type="button" class="swb ${c === d.colour ? "on" : ""}" data-c="${c}" style="background:${c}"></button>`).join("")}</div></div></div>
        <div class="limgrid"><span></span><b>Sale limit (Rs.)</b><b>Bill limit</b>
          <span>Van Selling</span><input class="input" id="vs" type="number" min="0" value="${d.van_sale_limit}"><input class="input" id="vb" type="number" min="0" value="${d.van_bill_limit}">
          <span>Pre-Selling</span><input class="input" id="ps" type="number" min="0" value="${d.pre_sale_limit}"><input class="input" id="pb" type="number" min="0" value="${d.pre_bill_limit}"></div>
        <div class="hint">A territory wins on a competition day when its sale and its bill count both reach its selling mode's limits.</div></div>`,
      buttons: [{ label: "Cancel", value: null }, { label: x ? "Save" : "Add round", cls: "btn-primary", value: (mm) => ({ id: x && x.id, name: $("#rn", mm).value, colour: ($(".swb.on", mm) || {}).dataset?.c,
        van_sale_limit: $("#vs", mm).value, van_bill_limit: $("#vb", mm).value, pre_sale_limit: $("#ps", mm).value, pre_bill_limit: $("#pb", mm).value }) }] });
    if (!v) return;
    const s = await call("competition_save_round", month, v);
    s.ok ? (toast("success", `${v.name} saved`), reload()) : toast("error", "Not saved", s.error);
  }
  // colour swatches inside the round dialog
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".swb"); if (!b) return;
    b.parentElement.querySelectorAll(".swb").forEach((x) => x.classList.toggle("on", x === b));
  });

  // =================================================================================== Aliases & Labels
  async function aliasesPage(main, _p, opts) {
    const t = await call("targets_month", "");
    const months = (t.ok && t.months) || [];
    const month = (opts && opts.month) || months[0] || thisMonth();
    const [a, o] = await Promise.all([call("aliases_month", month), call("outlets_list", month)]);
    if (!a.ok) throw new Error(a.error);
    const edit = canEdit();
    const opt = (sel) => `<option value="">— choose territory —</option>` + a.territories.map((x) => `<option value="${x.id}" ${x.id === sel ? "selected" : ""}>${esc(x.label)}${x.sfa_territory ? ` (now: ${esc(x.sfa_territory)})` : ""}</option>`).join("");
    main.innerHTML = `${head("Data", "Aliases & Labels", "Make SFA names match the hierarchy, and choose which outlet categories count for the Daily Winners competition.",
        `<select class="input select" id="amonth" style="width:180px">${(months.length ? months : [month]).map((x) => `<option value="${x}" ${x === month ? "selected" : ""}>${monthLabel(x)}</option>`).join("")}</select>`)}
      ${!a.has_targets ? `<div class="alert warn" style="margin-bottom:14px">${icon("warn")}<div><b>No hierarchy for ${monthLabel(month)}</b>Import or create the month's targets first, then match the SFA names here.</div></div>` : ""}
      <div class="cards c2" style="align-items:start">
        <div class="stack">
          <div class="card"><div class="card-h">${icon("tag")}<h3>SFA names not in the hierarchy</h3><span class="spacer"></span><span class="chip ${a.unmatched.length ? "warn" : "ok"}">${a.unmatched.length}</span></div><div class="card-b">
            ${a.unmatched.length ? `<p class="muted" style="margin:0 0 10px">These SFA territories had sales in ${monthLabel(month)} but match no territory, so the reports put them under <b>Unmatched Territories</b>. Pick the territory each one belongs to.</p>
              <div class="table-wrap"><table class="table"><thead><tr><th>SFA name</th><th class="num">Days</th><th class="num">Sales</th><th>Is territory</th><th></th></tr></thead><tbody>
              ${a.unmatched.map((u, i) => `<tr><td><b>${esc(u.name)}</b>${u.suggest ? ` <span class="chip" title="Closest name in the hierarchy">suggested</span>` : ""}</td><td class="num">${u.days}</td><td class="num">${money(Math.round(u.value))}</td>
                <td><select class="input select sm" id="as${i}" ${edit ? "" : "disabled"}>${opt(u.suggest)}</select></td>
                <td>${edit ? `<button class="btn btn-primary btn-sm" data-match="${i}">Match</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`
            : `<div class="alert ok">${icon("okcircle")}<div><b>Every SFA territory matches</b>${a.sales_names ? `${a.sales_names} SFA territory names with sales in ${monthLabel(month)}.` : `No SKU sales imported for ${monthLabel(month)} yet.`}</div></div>`}
          </div></div>
          <div class="card"><div class="card-h">${icon("link")}<h3>SFA names in use</h3><span class="spacer"></span><span class="chip">${a.aliases.length}</span></div><div class="card-b">
            ${a.aliases.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Territory (reports)</th><th>SFA name</th><th></th></tr></thead><tbody>
              ${a.aliases.map((x) => `<tr><td><b>${esc(x.label)}</b></td><td class="mono">${esc(x.sfa_territory)}</td><td>${edit ? `<button class="btn btn-ghost btn-sm" data-unalias="${x.id}">Remove</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`
              : `<div class="faint">None — every territory uses the same name as SFA.</div>`}
            <div class="hint" style="margin-top:10px">Matching ignores capitals, spaces and brackets, so “Anuradhapura (SMMT)” and “anuradhapura smmt” already match. New months copy these names.</div></div></div>
        </div>
        <div class="stack">
          <div class="card"><div class="card-h">${icon("store")}<h3>Outlet categories</h3></div><div class="card-b">
            <p class="muted" style="margin:0 0 10px">Sales to a category that is switched off are left out of <b>Sale Value</b> in Daily Winners (shown as SMMT Outlet Sale instead). Every other report counts all outlets.</p>
            ${(o.outlets || []).length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Category</th><th class="num">Sales (${esc(monthLabel(month).split(" ")[0])})</th><th class="c">Counts for winners</th></tr></thead><tbody>
              ${o.outlets.map((x) => `<tr><td><b>${esc(x.label)}</b>${x.new ? ` <span class="chip warn">new</span>` : ""}</td><td class="num">${money(Math.round(x.value))}</td>
                <td class="c"><label class="toggle"><input type="checkbox" data-oc="${esc(x.category_key)}" data-ol="${esc(x.label)}" ${x.include_in_competition ? "checked" : ""} ${edit ? "" : "disabled"}><span></span></label></td></tr>`).join("")}</tbody></table></div>`
              : `<div class="faint">No outlet categories yet — they appear when SKU sales are imported.</div>`}
          </div></div>
          ${a.no_sales.length ? `<div class="card"><div class="card-h">${icon("info")}<h3>Territories with no sales this month</h3><span class="spacer"></span><span class="chip">${a.no_sales.length}</span></div><div class="card-b">
            <p class="muted" style="margin:0 0 10px">Usually vacant territories. If one of them is named differently in SFA, match it on the left.</p>
            <div class="row wrap" style="gap:6px">${a.no_sales.map((x) => `<span class="chip">${esc(x.label)}</span>`).join("")}</div></div></div>` : ""}
        </div>
      </div>`;
    const reload = () => aliasesPage(main, _p, { month }).then(() => Hydra.hydrateIcons(main));
    $("#amonth").onchange = (e) => aliasesPage(main, _p, { month: e.target.value }).then(() => Hydra.hydrateIcons(main));
    $$("[data-match]").forEach((b) => b.onclick = async () => {
      const i = +b.dataset.match, id = +$("#as" + i).value, u = a.unmatched[i];
      if (!id) return toast("warning", "Choose the territory first");
      const terr = a.territories.find((x) => x.id === id);
      if (terr.sfa_territory && !(await confirmBox("Replace SFA name?", `${esc(terr.label)} is already matched to “${esc(terr.sfa_territory)}”. Match it to “${esc(u.name)}” instead?`, "Replace"))) return;
      const s = await call("aliases_set", id, u.name);
      s.ok ? (toast("success", `${u.name} → ${terr.label}`), reload()) : toast("error", "Not saved", s.error);
    });
    $$("[data-unalias]").forEach((b) => b.onclick = async () => {
      const s = await call("aliases_set", +b.dataset.unalias, null);
      s.ok ? reload() : toast("error", "Not removed", s.error);
    });
    $$("[data-oc]").forEach((c) => c.onchange = async () => {
      const s = await call("outlets_set", c.dataset.oc, c.dataset.ol, c.checked);
      s.ok ? toast("success", c.dataset.ol, c.checked ? "Counts for Daily Winners" : "Left out of Daily Winners sale value") : (toast("error", "Not saved", s.error), c.checked = !c.checked);
    });
  }

  Object.assign(window.Pages, { targets: targetsPage, calendar: calendarPage, aliases: aliasesPage });
})();
