/* Hydra pages (Phase 1): Dashboard, Notifications, Logs, Settings, About + phase placeholders. */
(function () {
  const { call, icon, esc, $, $$, toast, fmtTime, fmtAgo, busy, modal } = Hydra;

  const head = (eyebrow, title, text, right) => `<div class="page-h"><div><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1>${text ? `<p>${text}</p>` : ""}</div><span class="spacer"></span>${right || ""}</div>`;
  const stIcon = (s) => ({ ok: "check", warning: "warn", error: "warn", skipped: "skip", running: "clock", pending: "clock" }[s] || "info");

  // =============================================================== Dashboard
  async function dashboard(main) {
    const [d, s] = await Promise.all([call("dashboard_summary"), call("status_bar")]);
    if (!d.ok) throw new Error(d.error);
    const sfa = s.sfa, wa = s.whatsapp, st = d.startup;
    const todo = d.checklist.filter((c) => !c.done && c.phase <= d.phase);
    const card = (k, ic, v, sub, cls) => `<div class="card stat"><div class="k">${icon(ic)}${k}</div><div class="v ${cls || ""}">${v}</div><div class="s">${sub}</div></div>`;
    main.innerHTML = `
      ${head("Operations console", "Dashboard", "What Hydra checked when it opened, and what is still to set up.",
        `<button class="btn btn-secondary" id="recheck">${icon("refresh")}Run startup check again</button>`)}
      ${todo.length ? `<div class="alert warn" style="margin-bottom:16px">${icon("warn")}<div><b>Setup not finished</b>${todo.map((t) => esc(t.title)).join(", ")} — <a href="wizard.html">open the setup wizard</a></div></div>` : ""}
      ${sfa.logged_in === false && sfa.ts ? `<div class="alert err" style="margin-bottom:16px">${icon("error")}<div><b>SFA sign-in failed at startup</b>${esc(sfa.message)} — check <a href="wizard.html?step=sfa">SFA Connection</a>.</div></div>` : ""}
      <div class="cards c5">
        ${card("SFA connection", "server", sfa.logged_in ? "Connected" : (sfa.reachable === false ? "Unreachable" : "Not signed in"),
          sfa.logged_in ? `Signed in${sfa.display_name ? " as " + esc(sfa.display_name) : ""} · ${fmtAgo(sfa.ts)}` : esc(sfa.message || "Checked at every startup"))}
        ${card("WhatsApp", "message", wa.linked ? "Linked" : "Not linked", wa.linked ? esc(wa.number) : "Link it on the WhatsApp screen")}
        ${card("Next run", "clock", s.next_run ? fmtTime(s.next_run) : "—", "Scheduler arrives in Phase 10")}
        ${card("Last run", "history", "—", "Report runs arrive in Phase 6")}
        ${card("Data used", "gauge", s.data_today_mb.toFixed(1) + " MB", "Today · meter in Phase 11")}
      </div>
      <div class="cards c2" style="margin-top:16px;grid-template-columns:3fr 2fr">
        <div class="card"><div class="card-h">${icon("activity")}<h3>Startup check</h3><span class="spacer"></span>
          ${st ? `<span class="chip ${st.result === "ok" ? "ok" : st.result === "fatal" ? "err" : "warn"}">${st.result === "ok" ? "All clear" : st.result === "fatal" ? "Failed" : "Needs attention"}</span>` : ""}</div>
          <div class="card-b">${st ? `<div class="faint" style="margin-bottom:8px">${fmtTime(st.ts)} · ${st.mode === "daily" ? "daily check" : "first-run"} · ${(st.duration_ms / 1000).toFixed(1)} s</div>
            <div class="tl">${st.steps.map((x) => `<div class="t ${x.state}">${icon(stIcon(x.state))}<b>${esc(x.label)}</b><span class="d" title="${esc(x.detail)}">${esc(x.detail || x.state)}</span><span class="ms">${x.ms ? (x.ms / 1000).toFixed(1) + "s" : ""}</span></div>`).join("")}</div>`
            : `<div class="empty">No startup recorded yet.</div>`}</div></div>
        <div class="card"><div class="card-h">${icon("check")}<h3>Setup checklist</h3></div>
          <div class="card-b checklist">${d.checklist.map((c) => `<div class="c ${c.done ? "done" : "todo"}">${icon(c.done ? "okcircle" : "clock")}<span>${esc(c.title)}</span>
            <span class="chip ${c.done ? "ok" : c.phase <= d.phase ? "warn" : ""}">${c.done ? "Done" : c.phase <= d.phase ? "To do" : "Phase " + c.phase}</span></div>`).join("")}</div></div>
      </div>`;
    $("#recheck").onclick = () => location.href = "splash.html";
  }

  // =============================================================== Notifications
  function notifItem(n) {
    const ic = { success: "okcircle", warning: "warn", error: "error", info: "info" }[n.level] || "info";
    return `<div class="nitem ${n.level} ${n.read ? "" : "unread"}" data-id="${n.id}">${icon(ic)}<div style="flex:1"><b>${esc(n.title)}</b>${n.body ? `<small>${esc(n.body)}</small>` : ""}<time>${fmtAgo(n.ts)}</time></div></div>`;
  }
  async function notifications(main) {
    let filter = "";
    async function draw() {
      const r = await call("notifications_list", filter === "unread", "");
      let items = r.items || [];
      if (filter && filter !== "unread") items = items.filter((n) => n.level === filter);
      $("#nbody").innerHTML = items.length ? items.map(notifItem).join("") : `<div class="empty"><img src="assets/img/hydra_logo_silver.png"><h3>All quiet</h3>No notifications match this filter.</div>`;
    }
    main.innerHTML = `${head("Alert centre", "Notifications", "Startup problems, setup steps and (from later phases) run results, approvals and WhatsApp sends.",
      `<button class="btn btn-secondary" id="nread">${icon("check")}Mark all as read</button>`)}
      <div class="seg" id="nseg" style="margin-bottom:14px">${[["", "All"], ["unread", "Unread"], ["error", "Errors"], ["warning", "Warnings"], ["success", "Success"], ["info", "Info"]].map(([k, l]) => `<button data-f="${k}" class="${k === "" ? "on" : ""}">${l}</button>`).join("")}</div>
      <div class="card" id="nbody"></div>`;
    $$("#nseg button").forEach((b) => b.onclick = () => { $$("#nseg button").forEach((x) => x.classList.remove("on")); b.classList.add("on"); filter = b.dataset.f; draw(); });
    $("#nread").onclick = async () => { await call("notifications_mark_read", null); await draw(); App.refreshStatus(); };
    await draw();
  }

  // =============================================================== Logs
  async function logs(main) {
    let level = "", rows = [], auto = true, timer = null;
    main.innerHTML = `${head("Telemetry", "Logs", "Everything Hydra does is written here and to <span class='mono'>logs\\hydra.log</span> in the data folder.")}
      <div class="row wrap" style="margin-bottom:12px">
        <div class="seg" id="lseg">${[["", "All"], ["INFO", "Info+"], ["WARNING", "Warnings"], ["ERROR", "Errors"]].map(([k, l]) => `<button data-l="${k}" class="${k === "" ? "on" : ""}">${l}</button>`).join("")}</div>
        <div class="input-wrap" style="width:320px">${icon("search")}<input class="input" id="lsearch" placeholder="Search messages…"></div>
        <label class="check"><input type="checkbox" id="lauto" checked> Live</label>
        <span class="spacer"></span>
        <button class="btn btn-primary" id="lcopy">${icon("copy")}Copy Log</button>
        <button class="btn btn-dark" id="lexport">${icon("download")}Export .txt</button>
        <button class="btn btn-ghost" id="lfolder">${icon("folder")}Open logs folder</button>
      </div>
      <div class="logview" id="lview"></div>
      <div class="faint" id="lcount" style="margin-top:8px"></div>`;
    const text = () => rows.map((r) => `${r.ts}  ${r.level.padEnd(7)}  ${r.source.padEnd(10)}  ${r.message}`).join("\n");
    async function load() {
      const r = await call("logs_query", level, $("#lsearch").value, 1000, null);
      if (!r.ok) return;
      rows = r.rows;
      const v = $("#lview");
      const atBottom = v.scrollHeight - v.scrollTop - v.clientHeight < 40;
      v.innerHTML = rows.map((x) => `<div class="l ${x.level}"><span class="ts">${esc(x.ts.replace("T", " "))}</span><span class="lv">${x.level}</span><span class="src">${esc(x.source)}</span><span class="msg">${esc(x.message)}</span></div>`).join("") || `<div class="l"><span></span><span></span><span></span><span class="faint">No log lines match.</span></div>`;
      if (atBottom || !v.dataset.init) { v.scrollTop = v.scrollHeight; v.dataset.init = "1"; }
      $("#lcount").textContent = `${rows.length} line(s) shown`;
    }
    $$("#lseg button").forEach((b) => b.onclick = () => { $$("#lseg button").forEach((x) => x.classList.remove("on")); b.classList.add("on"); level = b.dataset.l; load(); });
    let deb; $("#lsearch").oninput = () => { clearTimeout(deb); deb = setTimeout(load, 250); };
    $("#lauto").onchange = (e) => auto = e.target.checked;
    $("#lcopy").onclick = async () => { const r = await call("copy_text", text()); r.ok ? toast("success", "Copied!", `${rows.length} log lines copied to the clipboard`) : toast("error", "Copy failed", r.error); };
    $("#lexport").onclick = async () => { const r = await call("logs_export", text()); if (r.ok && r.saved) toast("success", "Log exported", r.saved); };
    $("#lfolder").onclick = () => call("open_folder", "logs");
    await load();
    timer = setInterval(() => { if (!document.body.contains($("#lview"))) return clearInterval(timer); if (auto) load(); }, 3000);
  }

  // =============================================================== Settings
  async function settingsPage(main) {
    const S = await call("settings_get");
    if (!S.ok) throw new Error(S.error);
    const isSuper = S.user.role === "superadmin", isAdmin = S.user.role !== "user";
    const sections = [["general", "General", "settings"], ["sfa", "SFA Connection", "server"], ["pages", "Pages & URLs", "link"],
      ["output", "Save Location", "folder"], ["startup", "Startup", "zap"], ["reports", "Reports", "file"],
      ["notifications", "Notifications", "bell"], ...(isSuper ? [["users", "Users & Roles", "users"]] : []), ["account", "My Account", "user"]];
    main.innerHTML = `${head("Configuration", "Settings", "Changes apply immediately. Sections from later phases (filters, schedule, WhatsApp, data meter) appear as they are delivered.")}
      <div class="subnav" id="sub">${sections.map(([k, l, ic]) => `<button data-s="${k}">${icon(ic)}${l}</button>`).join("")}</div>
      <div id="sbody"></div>`;
    const tog = (id, title, sub, on) => `<div class="toggle-row"><div class="t"><b>${title}</b><small>${sub}</small></div><label class="toggle"><input type="checkbox" id="${id}" ${on ? "checked" : ""} ${isAdmin ? "" : "disabled"}><span></span></label></div>`;
    const saveBtn = isAdmin ? `<div class="row" style="margin-top:6px"><button class="btn btn-primary" id="ssave">${icon("check")}Save changes</button></div>` : `<div class="faint">Only admins can change settings.</div>`;
    const R = {
      general: () => `<div class="card"><div class="card-h">${icon("settings")}<h3>General</h3></div><div class="card-b stack">
          <div class="field"><label>Theme</label><div class="seg" id="theme"><button data-v="dark" class="on">Black &amp; Cherry</button><button data-v="full_dark" disabled title="Coming later">Full dark</button></div></div>
          <div class="field"><label>Window title bar</label><div class="seg" id="titlebar">
            <button data-v="black" class="${S.general.titlebar === "black" ? "on" : ""}">Black · red title</button>
            <button data-v="red" class="${S.general.titlebar === "red" ? "on" : ""}">Red · white title</button></div>
            <div class="hint">Windows 11 colours the title bar; minimise, maximise and close stay as normal Windows buttons.</div></div>
          <div class="faint">Start with Windows and minimise-to-tray arrive with the background worker in Phase 10.</div></div></div>`,
      sfa: () => { const f = S.sfa, t = f.last_test || {};
        return `<div class="card"><div class="card-h">${icon("server")}<h3>SFA Connection</h3><span class="spacer"></span><a class="btn btn-secondary btn-sm" href="wizard.html?step=sfa">${icon("settings")}Edit &amp; test</a></div><div class="card-b">
          <table class="table"><tbody>
            <tr><td class="faint" style="width:220px">SFA URL</td><td class="mono">${esc(f.base_url)}</td></tr>
            <tr><td class="faint">Username</td><td>${esc(f.username || "—")}</td></tr>
            <tr><td class="faint">Password</td><td>${f.has_password ? `<span class="chip ok">${icon("lock")}Saved in Windows Credential Manager</span>` : `<span class="chip err">Not saved</span>`}</td></tr>
            <tr><td class="faint">Browser</td><td>${esc({ chromium: "Chromium (built in)", msedge: "Microsoft Edge", chrome: "Google Chrome" }[f.browser] || f.browser)} · ${f.headless ? "hidden" : "visible"}</td></tr>
            <tr><td class="faint">Timeout</td><td>${esc(f.timeout_s)} s</td></tr>
            <tr><td class="faint">Last test</td><td>${t.message ? `<span class="chip ${t.ok ? "ok" : "err"}">${t.ok ? "OK" : "Failed"}</span> ${esc(t.message)} · ${fmtTime(t.ts)}` : "—"}</td></tr>
          </tbody></table></div></div>`; },
      pages: () => `<div class="card"><div class="card-h">${icon("link")}<h3>Pages &amp; URLs</h3><span class="spacer"></span><a class="btn btn-secondary btn-sm" href="wizard.html?step=pages">${icon("settings")}Edit &amp; test</a></div><div class="card-b">
          <div class="table-wrap"><table class="table"><thead><tr><th>Page</th><th>Address</th></tr></thead><tbody>
          ${S.pages.map((p) => `<tr><td><b>${esc(p.name)}</b></td><td class="mono">${p.full_url ? esc(p.full_url) : `<span class="chip warn">Not set</span>`}</td></tr>`).join("")}</tbody></table></div>
          <div class="faint" style="margin-top:10px">Filters for each page are set up in Phase 2.</div></div></div>`,
      output: () => `<div class="card"><div class="card-h">${icon("folder")}<h3>Save Location</h3><span class="spacer"></span><a class="btn btn-secondary btn-sm" href="wizard.html?step=output">${icon("settings")}Change</a></div><div class="card-b stack">
          <div class="mono">${esc(S.output.root || "Not set")}</div><div class="row"><button class="btn btn-dark btn-sm" id="openout">${icon("folder")}Open folder</button></div></div></div>`,
      startup: () => `<div class="card"><div class="card-h">${icon("zap")}<h3>Startup checks</h3></div><div class="card-b stack">
          ${tog("check_sfa_login", "Sign in to SFA at startup", "The splash bar waits for a live SFA sign-in and saves the session for the day's runs.", S.startup.check_sfa_login)}
          ${tog("check_whatsapp", "Check the WhatsApp link at startup", "Warns on the Dashboard when WhatsApp needs to be linked again.", S.startup.check_whatsapp)}
          <div class="field" style="max-width:260px"><label>SFA timeout (seconds)</label><input class="input" type="number" id="sfa_timeout_s" min="15" max="180" value="${esc(S.startup.sfa_timeout_s)}" ${isAdmin ? "" : "disabled"}></div>
          ${saveBtn}</div></div>`,
      reports: () => `<div class="card"><div class="card-h">${icon("file")}<h3>Reports</h3></div><div class="card-b stack">
          <div class="field" style="max-width:420px"><label>Title prefix (optional)</label><input class="input" id="title_prefix" value="${esc(S.reports.title_prefix)}" placeholder="Empty = “Day Report — 2026-11-03”" ${isAdmin ? "" : "disabled"}>
          <div class="hint">e.g. “Hydra” gives “Hydra — Day Report — 2026-11-03”.</div></div>
          <div class="faint">Report names, winner limits and outlet categories arrive with the reports in Phase 6.</div>${saveBtn}</div></div>`,
      notifications: () => `<div class="card"><div class="card-h">${icon("bell")}<h3>Notifications</h3></div><div class="card-b stack">
          ${tog("windows_toasts", "Windows notifications", "Show a Windows toast for run results and approvals (from Phase 11).", S.notifications.windows_toasts)}
          ${tog("sound", "Sound", "Play a short sound with important notifications.", S.notifications.sound)}${saveBtn}</div></div>`,
      users: () => `<div class="card"><div class="card-h">${icon("users")}<h3>Users &amp; Roles</h3><span class="spacer"></span><button class="btn btn-primary btn-sm" id="uadd">${icon("plus")}Add user</button></div><div class="card-b" id="ulist"><span class="spinner"></span></div></div>`,
      account: () => `<div class="card"><div class="card-h">${icon("user")}<h3>My Account</h3></div><div class="card-b stack">
          <div><b>${esc(S.user.display_name)}</b> <span class="faint">(${esc(S.user.username)})</span> <span class="chip cherry">${esc(S.user.role)}</span></div>
          <div class="faint">Last sign-in ${fmtTime(S.user.last_login)}</div>
          <div class="row"><button class="btn btn-secondary" id="chpw">${icon("key")}Change password</button></div></div></div>`,
    };
    const SAVE = {
      startup: () => ({ check_sfa_login: $("#check_sfa_login").checked, check_whatsapp: $("#check_whatsapp").checked, sfa_timeout_s: +$("#sfa_timeout_s").value || 45 }),
      reports: () => ({ title_prefix: $("#title_prefix").value }),
      notifications: () => ({ windows_toasts: $("#windows_toasts").checked, sound: $("#sound").checked }),
    };
    async function show(k) {
      $$("#sub button").forEach((b) => b.classList.toggle("on", b.dataset.s === k));
      $("#sbody").innerHTML = R[k]();
      if ($("#ssave")) $("#ssave").onclick = async () => {
        const data = SAVE[k]();
        const r = await call("settings_save", k, data);
        if (r.ok) { Object.assign(S[k], data); toast("success", "Settings saved"); } else toast("error", "Not saved", r.error);
      };
      if ($("#openout")) $("#openout").onclick = () => call("open_folder", "output");
      $$("#titlebar button").forEach((b) => b.onclick = async () => {
        if (!isAdmin) return;
        const r = await call("settings_save", "general", { titlebar: b.dataset.v });
        if (!r.ok) return toast("error", "Not saved", r.error);
        S.general.titlebar = b.dataset.v;
        $$("#titlebar button").forEach((x) => x.classList.toggle("on", x === b));
        toast("success", "Title bar updated");
      });
      if ($("#chpw")) $("#chpw").onclick = changePassword;
      if (k === "users") await usersSection();
    }
    $$("#sub button").forEach((b) => b.onclick = () => show(b.dataset.s));
    show("general");
  }

  async function usersSection() {
    const r = await call("users_list");
    if (!r.ok) { $("#ulist").innerHTML = `<div class="alert err">${esc(r.error)}</div>`; return; }
    $("#ulist").innerHTML = `<div class="table-wrap"><table class="table"><thead><tr><th>Username</th><th>Display name</th><th>Role</th><th>Status</th><th>Last sign-in</th><th></th></tr></thead><tbody>
      ${r.users.map((u) => `<tr data-id="${u.id}"><td class="mono">${esc(u.username)}</td><td><input class="input" value="${esc(u.display_name)}" data-f="display_name"></td>
        <td><select class="input select" data-f="role">${r.roles.map((x) => `<option ${x === u.role ? "selected" : ""}>${x}</option>`).join("")}</select></td>
        <td><label class="toggle"><input type="checkbox" data-f="active" ${u.active ? "checked" : ""}><span></span></label></td>
        <td class="faint">${fmtTime(u.last_login)}</td>
        <td><div class="row"><button class="btn btn-dark btn-sm" data-a="save">Save</button><button class="btn btn-ghost btn-sm" data-a="reset">Reset password</button></div></td></tr>`).join("")}
      </tbody></table></div><div class="faint" style="margin-top:10px">superadmin — everything incl. users · admin — settings, targets, schedules, approve &amp; send · user — view reports, Generate Now</div>`;
    $$("#ulist tr[data-id]").forEach((tr) => {
      const id = tr.dataset.id, f = (n) => $(`[data-f="${n}"]`, tr);
      $('[data-a="save"]', tr).onclick = async () => {
        const res = await call("users_update", { id, role: f("role").value, active: f("active").checked, display_name: f("display_name").value });
        res.ok ? toast("success", "User updated") : toast("error", "Not saved", res.error);
      };
      $('[data-a="reset"]', tr).onclick = async () => {
        const v = await modal({ title: "Reset password", body: `<div class="field"><label>New password</label><input class="input" type="password" id="np"></div>`,
          buttons: [{ label: "Cancel", value: null }, { label: "Reset", cls: "btn-primary", value: (m) => $("#np", m).value }] });
        if (!v) return;
        const res = await call("users_reset_password", id, v);
        res.ok ? toast("success", "Password reset") : toast("error", "Not reset", res.error);
      };
    });
    $("#uadd").onclick = async () => {
      const v = await modal({ title: "Add user", body: `<div class="stack"><div class="grid-2"><div class="field"><label>Username</label><input class="input" id="nu"></div>
          <div class="field"><label>Display name</label><input class="input" id="nn"></div></div>
          <div class="grid-2"><div class="field"><label>Role</label><select class="input select" id="nr"><option>user</option><option>admin</option><option>superadmin</option></select></div>
          <div class="field"><label>Password</label><input class="input" type="password" id="npw"></div></div></div>`,
        buttons: [{ label: "Cancel", value: null }, { label: "Create user", cls: "btn-primary", value: (m) => ({ username: $("#nu", m).value, display_name: $("#nn", m).value, role: $("#nr", m).value, password: $("#npw", m).value }) }] });
      if (!v) return;
      const res = await call("users_create", v);
      if (res.ok) { toast("success", "User created", v.username); usersSection(); } else toast("error", "Not created", res.error);
    };
  }

  async function changePassword() {
    const v = await modal({ title: "Change password", body: `<div class="stack">
        <div class="field"><label>Current password</label><input class="input" type="password" id="op"></div>
        <div class="field"><label>New password</label><input class="input" type="password" id="np1"></div>
        <div class="field"><label>Confirm new password</label><input class="input" type="password" id="np2"></div></div>`,
      buttons: [{ label: "Cancel", value: null }, { label: "Change password", cls: "btn-primary", value: (m) => [$("#op", m).value, $("#np1", m).value, $("#np2", m).value] }] });
    if (!v) return;
    const r = await call("auth_change_password", ...v);
    r.ok ? toast("success", "Password changed") : toast("error", "Not changed", r.error);
  }

  // =============================================================== About
  async function about(main) {
    const a = await call("about");
    if (!a.ok) throw new Error(a.error);
    main.innerHTML = `<div style="max-width:820px;margin:10px auto">
      <div class="card" style="overflow:hidden"><div style="background:linear-gradient(180deg,#16171A,#0B0C0E);padding:36px;text-align:center;border-bottom:1px solid var(--black-700)">
        <img src="assets/img/hydra_logo_silver.png" style="width:190px"><div class="wordmark" style="font-size:52px;margin-top:14px;padding-left:.32em">HYDRA</div>
        <div class="overline" style="letter-spacing:.42em">Work Automation Suite</div></div>
        <div class="card-b"><div class="grid-2">
          <table class="table"><tbody>
            <tr><td class="faint">Version</td><td><b>v${esc(a.version)}</b> · ${esc(a.phase)}</td></tr>
            <tr><td class="faint">Build date</td><td>${esc(a.build_date)}</td></tr>
            <tr><td class="faint">Python / Playwright</td><td>${esc(a.python)} / ${esc(a.playwright)}</td></tr>
            <tr><td class="faint">System</td><td>${esc(a.platform)}</td></tr></tbody></table>
          <table class="table"><tbody>
            <tr><td class="faint">Database</td><td>${esc(a.db_size_mb)} MB · schema v${esc(a.schema)}</td></tr>
            <tr><td class="faint">Data folder</td><td class="mono" style="font-size:11.5px;word-break:break-all">${esc(a.data_folder)}</td></tr>
            <tr><td colspan="2"><button class="btn btn-dark btn-sm" id="odata">${icon("folder")}Open data folder</button></td></tr></tbody></table>
        </div>
        <div style="margin-top:18px;padding-top:16px;border-top:1px solid var(--black-700)" class="row wrap">
          <div><b>Developed by Binusha Liyanage</b><div class="faint">IT Department, Lakmee Exports Lanka</div></div><span class="spacer"></span>
          <span class="faint serif" style="font-style:italic;font-size:16px">Hydra — the many-headed serpent: one body, many heads. One engine, every role’s work.</span></div>
        </div></div></div>`;
    $("#odata").onclick = () => call("open_folder", "data");
  }

  // =============================================================== Placeholders
  const PLAN = {
    reconciliation: [7, "Reconciliation", ["Hydra achievement vs SFA Rep Performance per territory", "Tolerance highlight and possible causes"]],
    activity: [11, "Activity Monitor", ["Run history and data-burning meter", "Activity Reports for any period (Excel / PDF / WhatsApp)", "Health of SFA, WhatsApp, database and disk"]],
  };
  function placeholder(main, page) {
    const [ph, title, items] = PLAN[page] || [0, page, []];
    main.innerHTML = `<div class="card phase-card"><img src="assets/img/hydra_logo_silver.png" alt=""><h2>${esc(title)} arrives in Phase ${ph}</h2>
      <p class="muted">This screen is part of the approved design and is switched on when Phase ${ph} is delivered.</p>
      <ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul></div>`;
  }

  // =============================================================== Colleagues (Super Admin)
  function colleagues(main) {
    const sample = [
      ["Sales Admin Coordinator", "Management sales reports", "v0.1.2", "online", "5 / 5 runs OK"],
      ["Sales Admin Coordinator 2", "Different sales processes", "v0.1.2", "online", "3 / 4 runs · 1 failed"],
      ["IT Assistant", "IT processes", "v0.1.1", "update", "2 / 2 runs OK"],
      ["Human Resource Assistant", "HR processes", "v0.1.2", "offline", "Last seen yesterday"],
      ["Finance Executive", "Finance reports", "v0.1.2", "online", "1 / 1 runs OK"],
      ["Finance & Administrative Manager", "Finance & admin reports", "v0.1.2", "online", "Waiting for 14:00 run"],
    ];
    const chip = { online: '<span class="chip ok">Online</span>', offline: '<span class="chip">Offline</span>', update: '<span class="chip warn">Update available</span>' };
    main.innerHTML = `${head("Team · Super Admin", "Colleagues", "See and manage every colleague's Hydra from here — their dashboard, runs, reports, schedule and logs. Only the Super Admin sees this screen.")}
      <div class="alert info" style="margin-bottom:16px">${icon("info")}<div><b>Preview — switches on with the Hydra Cloud phase</b>Colleagues' Hydra apps connect only through the Super Admin's Google Sheet and Drive, so this view is refreshed on every sync (a few minutes), not live screen sharing. The rows below are sample roles.</div></div>
      <div class="table-wrap"><table class="table"><thead><tr><th>Colleague role</th><th>Services</th><th>Hydra version</th><th>Status</th><th>Today</th><th></th></tr></thead><tbody>
        ${sample.map(([r, s, v, st, t]) => `<tr><td><b>${esc(r)}</b></td><td class="muted">${esc(s)}</td><td class="mono">${v}</td><td>${chip[st]}</td><td class="muted">${esc(t)}</td>
          <td><button class="btn btn-dark btn-sm" disabled>${icon("eye")}Open their Hydra</button></td></tr>`).join("")}
      </tbody></table></div>
      <div class="cards c3" style="margin-top:16px">
        <div class="card"><div class="card-h">${icon("eye")}<h3>Open their Hydra</h3></div><div class="card-b muted">A read-only copy of that person's Hydra: their dashboard, startup checks, runs, generated reports (from their Drive folder), schedule and logs.</div></div>
        <div class="card"><div class="card-h">${icon("settings")}<h3>Manage remotely</h3></div><div class="card-b muted">Assign role and services, change their schedule, reset their Hydra password, push a new version. Changes reach them on their next sync.</div></div>
        <div class="card"><div class="card-h">${icon("zap")}<h3>Send commands</h3></div><div class="card-b muted">“Run now”, “Sync now”, “Upload logs”, “Re-check SFA” — queued in the Sheet and picked up by their Hydra within minutes.</div></div>
      </div>`;
  }

  // =============================================================== SFA Data (imports)
  const KIND = { sku: ["SKU Sales", "file"], callage: ["Callage", "activity"], sales_order: ["Pre-Selling Orders", "history"], rep_performance: ["Rep Performance", "users"] };
  const money = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 }));

  async function dataPage(main) {
    const canDelete = App.user && App.user.role !== "user";
    main.innerHTML = `${head("SFA data", "SFA Data", "Every SFA Excel file Hydra has read. Numbers stored as text are converted, the totals row is removed and checked against SFA's own total. From Phase 2 Hydra downloads these automatically; until then you can import files you downloaded yourself.",
        `${canDelete ? `<button class="btn btn-secondary btn-lg" id="dfam">${icon("database")}Import from Famulus…</button>` : ""}<button class="btn btn-primary btn-lg" id="dimport">${icon("download")}Import SFA Excel files…</button>`)}
      <div id="dinspect"></div>
      <div class="cards c4" id="dcov" style="margin-bottom:16px"></div>
      <div class="card"><div class="card-h">${icon("database")}<h3>Import history</h3><span class="spacer"></span>
        <div class="seg" id="dseg"><button data-k="" class="on">All</button>${Object.entries(KIND).map(([k, [l]]) => `<button data-k="${k}">${l}</button>`).join("")}</div></div>
        <div class="card-b" id="dlist"><span class="spinner"></span></div></div>`;
    let kind = "";
    async function load() {
      const r = await call("data_imports", kind);
      if (!r.ok) throw new Error(r.error);
      const today = new Date();
      const days = [...Array(14)].map((_, i) => { const d = new Date(today); d.setDate(d.getDate() - 13 + i); return d.toISOString().slice(0, 10); });
      $("#dcov").innerHTML = r.coverage.map((c) => {
        const have = new Set(c.days.map((d) => d.date));
        const strip = c.kind === "rep_performance" ? `<div class="faint">${c.days.length ? esc(c.days[0].date) : "No periods yet"}</div>`
          : `<div class="row" style="gap:3px">${days.map((d) => `<span title="${d}${have.has(d) ? " · data" : " · no data"}" style="width:12px;height:22px;border-radius:2px;background:${have.has(d) ? "var(--cherry-400)" : "var(--black-650)"}"></span>`).join("")}</div>`;
        return `<div class="card stat"><div class="k">${icon(KIND[c.kind][1])}${esc(KIND[c.kind][0])}</div>${strip}
          <div class="s">${c.last_import ? "Last import " + fmtAgo(c.last_import) : "Nothing imported yet"}</div></div>`;
      }).join("");
      $("#dlist").innerHTML = r.imports.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>#</th><th>Type</th><th>File</th><th>Period</th><th class="num">Rows</th><th class="num">Check total</th><th>Imported</th><th>Status</th><th></th></tr></thead><tbody>
        ${r.imports.map((i) => {
          const chk = i.file_total == null ? `<span class="faint" title="SFA printed no totals row">${money(i.check_total)}</span>`
            : `<span title="SFA total ${money(i.file_total)}">${money(i.check_total)} ${Math.abs(i.check_total - i.file_total) < 0.01 ? `<span class="chip ok" style="height:20px">✓</span>` : `<span class="chip err" style="height:20px">≠</span>`}</span>`;
          return `<tr><td class="mono faint">${i.id}</td><td><span class="chip">${esc(KIND[i.kind] ? KIND[i.kind][0] : i.kind)}</span></td>
            <td title="${esc(i.file_name)}" style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(i.file_name)}</td>
            <td class="mono">${esc(i.period_from || "—")}${i.period_to && i.period_to !== i.period_from ? " → " + esc(i.period_to) : ""}</td>
            <td class="num">${i.rows.toLocaleString()}</td><td class="num">${chk}</td>
            <td class="faint">${fmtTime(i.imported_at)}<br>${esc(i.source)} · ${esc(i.imported_by || "")}</td>
            <td>${i.status === "active" ? `<span class="chip ok">Active</span>` : `<span class="chip">Replaced</span>`}${i.warnings.length ? ` <span class="chip warn" title="${esc(i.warnings.join("\n"))}">${icon("warn")}${i.warnings.length}</span>` : ""}</td>
            <td>${canDelete ? `<button class="btn btn-ghost btn-sm" data-del="${i.id}">Delete</button>` : ""}</td></tr>`; }).join("")}
        </tbody></table></div>` : `<div class="empty"><img src="assets/img/hydra_logo_silver.png"><h3>No SFA data yet</h3>Import an Outlet Wise SKU, Callage, Sales Order or Rep Performance Excel to start.</div>`;
      $$("[data-del]").forEach((b) => b.onclick = async () => {
        const ok = await modal({ title: "Delete import", body: `<p>Delete import #${b.dataset.del} and all its rows? Reports for those dates will have no data until it is imported again.</p>`,
          buttons: [{ label: "Cancel", value: false }, { label: "Delete", cls: "btn-primary", value: true }] });
        if (!ok) return;
        const d = await call("data_delete", b.dataset.del);
        d.ok ? (toast("success", "Import deleted"), load()) : toast("error", "Not deleted", d.error);
      });
    }
    $$("#dseg button").forEach((b) => b.onclick = () => { $$("#dseg button").forEach((x) => x.classList.remove("on")); b.classList.add("on"); kind = b.dataset.k; load(); });

    $("#dimport").onclick = async () => {
      const pick = await call("data_choose_files");
      if (!pick.ok || !pick.paths.length) return;
      busy($("#dimport"), true, "Reading files…");
      const r = await call("data_inspect", pick.paths);
      busy($("#dimport"), false);
      if (!r.ok) return toast("error", "Could not read files", r.error);
      showInspection(r.files);
    };

    if ($("#dfam")) $("#dfam").onclick = async () => {
      const pick = await call("famulus_choose");
      if (!pick.ok || !pick.path) return;
      busy($("#dfam"), true, "Reading Famulus…");
      const f = await call("famulus_inspect", pick.path);
      busy($("#dfam"), false);
      if (!f.ok) return toast("error", "Cannot read this file", f.error);
      const range = (d) => d && d.count ? `${d.count} days · ${esc(d.first)} → ${esc(d.last)}${d.already_in_hydra.length ? ` <span class="chip warn">${d.already_in_hydra.length} already in Hydra</span>` : ""}` : "none";
      const part = (k, title, detail, on = true) => `<label class="toggle-row" style="margin-bottom:8px"><div class="t"><b>${title}</b><small>${detail}</small></div><input type="checkbox" class="fpart" value="${k}" ${on ? "checked" : ""} style="width:18px;height:18px;accent-color:var(--cherry-500)"></label>`;
      const body = `<div class="stack" style="gap:0">
        ${part("targets", "Targets &amp; hierarchy", f.months.map((m) => `${m.month}: ${m.territories} territories · ${money(m.total)}${m.exists ? " (already in Hydra)" : ""}`).join("<br>") || "none")}
        ${part("nowd", "Working days (NOWD)", f.months.map((m) => `${m.month}: ${m.nowd ?? "—"}`).join(" · "))}
        ${part("sales", "Daily SKU sales history", range(f.sales) + (f.sales.total_value ? ` · ${money(f.sales.total_value)}` : ""))}
        ${part("callage", "Prepared daily callage", range(f.callage))}
        ${f.pending ? part("pending", "Pending pre-selling orders", range(f.pending)) : ""}
        ${part("modes", "Van / Pre selling modes", `${f.modes} territories`)}
        ${part("outlets", "Outlet categories (competition eligibility)", `${f.outlets} categories`)}
        ${f.competition ? part("competition", "Competition limits", `Van ${money(f.competition.van_sale_limit)} / ${f.competition.van_bill_limit} bills · Pre ${money(f.competition.pre_sale_limit)} / ${f.competition.pre_bill_limit} bills · ${esc(f.competition.start_date)} → ${esc(f.competition.end_date)}`) : ""}
        <label class="check" style="margin-top:10px"><input type="checkbox" id="fover"> Overwrite days / months Hydra already has</label>
        <div class="faint" style="margin-top:8px">Famulus is only read, never changed. Its users and licence are not copied.</div></div>`;
      const go = await modal({ title: "Import from Famulus", body, buttons: [{ label: "Cancel", value: null },
        { label: "Import", cls: "btn-primary", value: (m) => ({ parts: $$(".fpart", m).filter((x) => x.checked).map((x) => x.value), over: $("#fover", m).checked }) }] });
      if (!go || !go.parts.length) return;
      busy($("#dfam"), true, "Importing…");
      const r = await call("famulus_import", pick.path, go.parts, go.over);
      busy($("#dfam"), false);
      if (!r.ok) return toast("error", "Famulus import failed", r.error);
      await modal({ title: "Famulus import finished", body: `<table class="table"><tbody>${Object.entries(r.report).map(([k, v]) => `<tr><td class="faint" style="width:120px">${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")}</tbody></table>` });
      load(); App.refreshStatus();
    };

    function showInspection(files) {
      const box = $("#dinspect");
      box.innerHTML = `<div class="card" style="margin-bottom:16px"><div class="card-h">${icon("search")}<h3>Check before importing</h3><span class="spacer"></span>
          <button class="btn btn-ghost btn-sm" id="dcancel">Cancel</button><button class="btn btn-primary" id="dgo">${icon("download")}Import selected</button></div>
        <div class="card-b stack">${files.map((f, i) => {
          if (!f.ok) return `<div class="alert err">${icon("error")}<div><b>${esc(f.file_name)}</b>${esc(f.error)}</div></div>`;
          const blocked = f.errors.length || f.duplicate;
          const v = f.verification;
          const ver = v.ok === true ? `<span class="chip ok">${icon("check")}Matches SFA total</span>` : v.ok === false ? `<span class="chip err">${icon("warn")}Does not match SFA total</span>` : `<span class="chip">No totals row to check</span>`;
          return `<div class="panel" data-i="${i}"><div class="row wrap">
              <label class="check"><input type="checkbox" class="dsel" ${blocked ? "disabled" : "checked"}></label>
              <span class="chip cherry">${esc(KIND[f.kind][0])}</span><b>${esc(f.file_name)}</b>
              <span class="mono faint">${esc(f.period_from || "")}${f.period_to && f.period_to !== f.period_from ? " → " + esc(f.period_to) : ""}</span>
              <span class="spacer"></span>${ver}</div>
            <div class="row wrap" style="margin-top:8px;gap:18px">
              <span><span class="faint">Rows</span> <b>${f.rows.toLocaleString()}</b></span><span><span class="faint">Territories</span> <b>${f.territories}</b></span>
              ${Object.entries(f.totals).map(([k, n]) => `<span><span class="faint">${esc(k)}</span> <b>${money(n)}</b></span>`).join("")}
              ${f.converted_cells ? `<span class="faint">${f.converted_cells.toLocaleString()} numbers converted from text</span>` : ""}</div>
            ${f.errors.map((e) => `<div class="alert err" style="margin-top:8px">${icon("error")}<div>${esc(e)}</div></div>`).join("")}
            ${f.duplicate ? `<div class="alert info" style="margin-top:8px">${icon("info")}<div>Already imported as #${f.duplicate.id} on ${fmtTime(f.duplicate.imported_at)} — skipped.</div></div>` : ""}
            ${f.warnings.map((w) => `<div class="alert warn" style="margin-top:8px">${icon("warn")}<div>${esc(w)}</div></div>`).join("")}
            ${!f.duplicate && f.conflicts.length ? `<div class="alert warn" style="margin-top:8px">${icon("warn")}<div><b>Data for ${esc([...new Set(f.conflicts.flatMap((c) => c.dates))].join(", "))} already exists</b>
              from ${f.conflicts.map((c) => `#${c.import_id} ${esc(c.file_name)}`).join(", ")}.
              <label class="check" style="margin-top:6px"><input type="checkbox" class="drep"> Replace the existing data with this file</label></div></div>` : ""}
          </div>`; }).join("")}</div></div>`;
      $("#dcancel").onclick = () => box.innerHTML = "";
      $("#dgo").onclick = async () => {
        const items = [];
        $$(".panel[data-i]", box).forEach((p) => {
          const f = files[+p.dataset.i], sel = $(".dsel", p), rp = $(".drep", p);
          if (!sel || !sel.checked) return;
          if (f.conflicts.length && !(rp && rp.checked)) return toast("warning", "Not imported: " + f.file_name, "Tick “Replace” to overwrite the existing dates.");
          items.push({ path: f.path, replace: !!(rp && rp.checked) });
        });
        if (!items.length) return;
        busy($("#dgo"), true, "Importing…");
        const r = await call("data_import", items);
        busy($("#dgo"), false);
        if (!r.ok) return toast("error", "Import failed", r.error);
        r.results.forEach((x) => x.ok ? toast("success", `Imported ${x.file_name}`, `${x.rows.toLocaleString()} rows${x.replaced ? " · replaced earlier data" : ""}`) : toast("error", x.file_name, x.error));
        box.innerHTML = ""; load(); App.refreshStatus();
      };
    }
    await load();
  }

  // =============================================================== Territories
  async function territoriesPage(main) {
    const canEdit = App.user && App.user.role !== "user";
    main.innerHTML = `${head("Territory master", "Territories", "Every territory found in SFA data. Van / Pre selling decides how Callage is prepared: Van territories use the report day, Pre territories use the previous working day.")}
      <div class="row wrap" style="margin-bottom:12px">
        <div class="input-wrap" style="width:300px">${icon("search")}<input class="input" id="tsearch" placeholder="Search territories…"></div>
        <div class="seg" id="tseg"><button data-f="" class="on">All</button><button data-f="van">Van</button><button data-f="pre">Pre</button><button data-f="none">Not set</button><button data-f="smmt">SMMT</button></div>
        <span class="spacer"></span><span class="faint" id="tcount"></span></div>
      <div class="alert info" style="margin-bottom:12px">${icon("info")}<div>Selling mode is filled in automatically from the SKU report's <b style="display:inline">SALES REP MODEL</b> column. A territory with no sales yet (e.g. a Pre territory whose orders are not invoiced) stays “Not set” — choose it by hand; manual choices are never overwritten. Full sync from View Territory comes with the Phase 2 downloads.</div></div>
      <div class="card"><div class="card-b" id="tlist"><span class="spinner"></span></div></div>`;
    let all = [], filter = "";
    const r = await call("territories_list");
    if (!r.ok) throw new Error(r.error);
    all = r.territories;
    function draw() {
      const q = $("#tsearch").value.toLowerCase();
      const rows = all.filter((t) => (!q || t.name.toLowerCase().includes(q)) &&
        (!filter || (filter === "none" ? !t.selling_mode : filter === "smmt" ? t.is_smmt : t.selling_mode === filter)));
      $("#tcount").textContent = `${rows.length} of ${all.length} · ${all.filter((t) => t.selling_mode === "pre").length} Pre · ${all.filter((t) => t.selling_mode === "van").length} Van · ${all.filter((t) => !t.selling_mode).length} not set`;
      $("#tlist").innerHTML = all.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Territory</th><th>Selling mode</th><th>Set by</th><th>Type</th><th>First seen</th><th>Last seen</th></tr></thead><tbody>
        ${rows.map((t) => `<tr data-n="${esc(t.name)}"><td><b>${esc(t.name)}</b></td>
          <td><div class="seg">${["van", "pre"].map((m) => `<button data-m="${m}" class="${t.selling_mode === m ? "on" : ""}" ${canEdit ? "" : "disabled"}>${m === "van" ? "Van Selling" : "Pre Selling"}</button>`).join("")}</div></td>
          <td>${t.mode_source ? `<span class="chip ${t.mode_source === "manual" ? "info" : ""}">${esc(t.mode_source)}</span>` : `<span class="chip warn">Not set</span>`}</td>
          <td>${t.is_smmt ? `<span class="chip cherry">SMMT</span>` : `<span class="faint">GT</span>`}</td>
          <td class="mono faint">${esc(t.first_seen)}</td><td class="mono faint">${esc(t.last_seen)}</td></tr>`).join("")}</tbody></table></div>`
        : `<div class="empty"><img src="assets/img/hydra_logo_silver.png"><h3>No territories yet</h3>Import an SFA file on the SFA Data screen — territories are added automatically.</div>`;
      $$("#tlist tr[data-n] [data-m]").forEach((b) => b.onclick = async () => {
        const name = b.closest("tr").dataset.n, t = all.find((x) => x.name === name);
        const res = await call("territory_set_mode", name, b.dataset.m);
        if (!res.ok) return toast("error", "Not saved", res.error);
        t.selling_mode = b.dataset.m; t.mode_source = "manual"; draw();
        toast("success", `${name}: ${b.dataset.m === "van" ? "Van" : "Pre"} Selling`);
      });
    }
    $("#tsearch").oninput = draw;
    $$("#tseg button").forEach((b) => b.onclick = () => { $$("#tseg button").forEach((x) => x.classList.remove("on")); b.classList.add("on"); filter = b.dataset.f; draw(); });
    draw();
  }

  // =============================================================== Hierarchy & Targets (read-only until the Phase 5 editor)
  // =============================================================== Run Center
  async function runCenter(main, page, opts) {
    const types = (await call("reports_types")).types;
    const yday = new Date(Date.now() - 86400000 + new Date().getTimezoneOffset() * -60000).toISOString().slice(0, 10);
    main.innerHTML = `${head("Generate", "Run Center", "Pick a report date, check the data is there, and generate. Each report is saved as Excel, PDF and WhatsApp images, then opens in Preview &amp; Send.")}
      <div class="cards c2" style="grid-template-columns:2fr 3fr;align-items:start">
        <div class="card"><div class="card-h">${icon("run")}<h3>New run</h3></div><div class="card-b stack">
          <div class="field"><label>Report date</label><input class="input" type="date" id="rdate" value="${yday}"></div>
          <div class="field"><label>Reports</label>${types.map((t) => `<label class="check" style="margin:3px 0"><input type="checkbox" class="rtype" value="${t.id}" ${t.default_on === false ? "" : "checked"}> ${esc(t.name)}</label>`).join("")}</div>
          <div class="field"><label>Also create</label><div class="row wrap"><label class="check"><input type="checkbox" id="fpdf" checked> PDF</label><label class="check"><input type="checkbox" id="fpng" checked> WhatsApp images (PNG)</label></div></div>
          <div class="row"><button class="btn btn-primary btn-lg" id="rgo">${icon("zap")}Generate reports</button><button class="btn btn-dark btn-stop hidden" id="rstop">${icon("stop")}Stop</button></div>
          <div class="faint hidden" id="rprog"><span class="spinner"></span><span id="rprogt">Working…</span></div></div></div>
        <div class="card"><div class="card-h">${icon("check")}<h3>Data check</h3><span class="spacer"></span><button class="btn btn-ghost btn-sm" id="rdata">${icon("database")}SFA Data</button></div><div class="card-b" id="rready"><span class="spinner"></span></div></div>
      </div>
      <div id="rres" style="margin-top:16px"></div>`;
    async function ready() {
      const r = await call("reports_readiness", $("#rdate").value);
      if (!r.ok) return ($("#rready").innerHTML = `<div class="alert err">${esc(r.error)}</div>`);
      $("#rready").innerHTML = `<div class="checklist">${r.items.map((i) => `<div class="c ${i.ok ? "done" : "todo"}">${icon(i.ok ? "okcircle" : "warn")}<span><b>${esc(i.item)}</b><br><small class="faint">${esc(i.needed_by)}</small></span><span class="chip ${i.ok ? "ok" : "warn"}">${esc(i.detail)}</span></div>`).join("")}</div>`;
      Hydra.hydrateIcons($("#rready"));
    }
    $("#rdate").onchange = ready;
    $("#rdata").onclick = () => App.go("data");
    $("#rstop").onclick = async () => { await call("reports_stop"); $("#rprogt").textContent = "Stopping after the current report…"; };
    async function run(day, sel) {
      const formats = [$("#fpdf").checked && "pdf", $("#fpng").checked && "png"].filter(Boolean);
      busy($("#rgo"), true, "Generating…");
      $("#rstop").classList.remove("hidden"); $("#rprog").classList.remove("hidden");
      const poll = setInterval(async () => { const p = await call("reports_progress"); if (p.ok && p.text) $("#rprogt").textContent = p.text; }, 700);
      $("#stopall").disabled = false; $("#gen").disabled = true;
      const r = await call("reports_generate", day, sel, formats);
      clearInterval(poll);
      busy($("#rgo"), false);
      $("#rstop").classList.add("hidden"); $("#rprog").classList.add("hidden");
      App.refreshStatus();
      if (!r.ok) return toast("error", "Generation failed", r.error);
      showResults(day, r);
      const good = r.results.filter((x) => x.status === "generated").map((x) => x.id);
      if (good.length) previewSend(good, { day, sel, formats, rerun: () => run(day, sel) });
      else toast("warning", "Nothing to preview", "No report was generated — see the results below.");
    }
    function showResults(day, r) {
      $("#rres").innerHTML = `<div class="card"><div class="card-h">${icon("file")}<h3>Results — ${esc(day)}</h3>${r.stopped ? `<span class="chip warn">Stopped</span>` : ""}<span class="spacer"></span>
          <button class="btn btn-primary btn-sm" id="rprev">${icon("eye")}Preview &amp; Send</button>
          <button class="btn btn-secondary btn-sm" id="rfold">${icon("folder")}Open folder</button></div><div class="card-b stack">
        ${r.results.map((x) => `<div class="panel"><div class="row wrap">
            <span class="chip ${statusCls(x.status)}">${esc(x.status)}</span><b>${esc(x.title)}</b><span class="spacer"></span>
            ${fileButtons({ xlsx_path: x.path, pdf_path: x.pdf, png_paths: x.pngs, exists: !!x.path, has_pdf: !!x.pdf })}</div>
          ${Object.keys(x.summary || {}).length ? `<div class="row wrap" style="gap:18px;margin-top:8px">${Object.entries(x.summary).map(([k, v]) => `<span><span class="faint">${esc(k)}</span> <b>${typeof v === "number" ? (Math.abs(v) < 5 && !Number.isInteger(v) ? (v * 100).toFixed(1) + "%" : money(v)) : esc(Array.isArray(v) ? v.join(", ") : v)}</b></span>`).join("")}</div>` : ""}
          ${x.error ? `<div class="alert ${x.status === "skipped" ? "info" : "err"}" style="margin-top:8px">${icon(x.status === "skipped" ? "info" : "error")}<div>${esc(x.error)}</div></div>` : ""}
          ${(x.warnings || []).map((w) => `<div class="alert warn" style="margin-top:8px">${icon("warn")}<div>${esc(w)}</div></div>`).join("")}</div>`).join("")}</div></div>`;
      Hydra.hydrateIcons($("#rres"));
      $("#rfold").onclick = () => call("open_path", r.folder);
      const good = r.results.filter((x) => x.status === "generated").map((x) => x.id);
      $("#rprev").disabled = !good.length;
      $("#rprev").onclick = () => previewSend(good, { rerun: () => $("#rgo").click() });
      bindOpen($("#rres"));
    }
    $("#rgo").onclick = () => {
      const sel = $$(".rtype").filter((x) => x.checked).map((x) => x.value);
      if (!sel.length) return toast("warning", "Choose at least one report");
      run($("#rdate").value, sel);
    };
    await ready();
    if (opts && opts.autorun) $("#rgo").click();
  }

  const statusCls = (s) => ({ generated: "ok", approved: "ok", sent: "ok", saved: "ok", skipped: "" }[s] ?? "err");

  function fileButtons(x) {
    const b = [];
    if (x.exists) b.push(`<button class="btn btn-dark btn-sm" data-open="${esc(x.xlsx_path)}">${icon("file")}Excel</button>`);
    if (x.has_pdf || x.pdf_path) b.push(`<button class="btn btn-dark btn-sm" data-open="${esc(x.pdf_path)}">${icon("file")}PDF</button>`);
    const pngs = x.png_paths || [];
    if (pngs.length) b.push(`<button class="btn btn-dark btn-sm" data-open="${esc(pngs[0])}">${icon("image")}Image${pngs.length > 1 ? "s ×" + pngs.length : ""}</button>`);
    return `<div class="row">${b.join("")}</div>`;
  }
  function bindOpen(root) {
    $$("[data-open]", root).forEach((b) => b.onclick = async () => { const o = await call("open_path", b.dataset.open); if (!o.ok) toast("error", "Cannot open", o.error); });
  }

  // =============================================================== Preview & Send
  async function previewSend(ids, opts = {}) {
    const r = await call("reports_get", ids);
    if (!r.ok || !r.reports.length) return toast("error", "Nothing to preview", r.error || "");
    const reps = r.reports;
    const [st, wa, rc] = await Promise.all([call("settings_get"), call("wa_state"), call("wa_recipients")]);
    const cfg = (st.ok && st.settings) || {};
    const linked = !!(wa.ok && wa.status.linked);
    const recNames = Object.fromEntries(((rc.ok && rc.recipients) || []).filter((x) => x.active).map((x) => [x.id, x.name]));
    const routesOf = (t) => (((rc.ok && rc.routes) || {})[t] || []).filter((id) => recNames[id]).map((id) => recNames[id]);
    let cur = reps[0].id, page = 0, fmt = cfg["reports.send_format"] || "png";
    const chosen = new Set(reps.filter((x) => x.status !== "failed").map((x) => x.id));
    const back = document.createElement("div");
    back.className = "modal-back";
    back.innerHTML = `<div class="modal pv">
      <div class="modal-h"><img src="assets/img/hydra_logo_silver.png" alt=""><h3>Preview &amp; Send</h3><span class="spacer"></span><span class="faint" style="font-size:12px">${esc(reps[0].report_date)}</span><button class="iconbtn" id="pvx" title="Close">${icon("x")}</button></div>
      <div class="pv-body">
        <div class="pv-list">
          <label class="check pv-all"><input type="checkbox" id="pvall"> <b>Select all</b><span class="spacer"></span><span class="faint" id="pvcount"></span></label>
          <div id="pvitems">${reps.map((x) => `<div class="pv-item" data-id="${x.id}">
              <input type="checkbox" class="pvchk" value="${x.id}" ${chosen.has(x.id) ? "checked" : ""}>
              <div class="pv-thumb" id="th${x.id}"><span class="spinner"></span></div>
              <div class="pv-meta"><b>${esc(x.name)}</b><small class="faint">${x.pages ? x.pages + " image" + (x.pages > 1 ? "s" : "") : "No images"}${x.has_pdf ? " · PDF" : ""}</small>
                <small class="pv-to ${routesOf(x.report_type).length ? "" : "none"}">${routesOf(x.report_type).length ? "→ " + esc(routesOf(x.report_type).join(", ")) : "No WhatsApp recipients"}</small>
                <span class="chip ${statusCls(x.status)}" data-st="${x.id}">${esc(x.status)}</span>${(x.warnings || []).length ? ` <span class="chip warn" title="${esc(x.warnings.join("\n"))}">${icon("warn")}${x.warnings.length}</span>` : ""}</div></div>`).join("")}</div>
          <div class="pv-opts stack">
            <div class="field"><label>Send as</label><div class="seg" id="pvfmt">${["png", "pdf", "both"].map((f) => `<button data-f="${f}" class="${f === fmt ? "on" : ""}">${{ png: "Images", pdf: "PDF", both: "Both" }[f]}</button>`).join("")}</div></div>
            <div class="field"><label>Caption</label><textarea class="input" id="pvcap" rows="2"></textarea><small class="faint">{title} and {date} are filled in for each report.</small></div>
            ${linked ? `<div class="alert info">${icon("message")}<div><b>Sends from ${esc(wa.status.number || "the linked WhatsApp")}</b>Each report goes to the recipients shown under it. Change them on the <a href="#" class="pvwa">WhatsApp screen</a>.</div></div>`
              : `<div class="alert warn">${icon("warn")}<div><b>WhatsApp is not linked</b>Approve will mark the reports as approved only. <a href="#" class="pvwa">Link WhatsApp</a> to send them.</div></div>`}
          </div>
        </div>
        <div class="pv-view">
          <div class="pv-bar"><b id="pvtitle"></b><span class="spacer"></span><button class="iconbtn" id="pvprev" title="Previous image">${icon("left")}</button><span class="mono" id="pvpage"></span><button class="iconbtn" id="pvnext" title="Next image">${icon("right")}</button></div>
          <div class="pv-img" id="pvimg"><span class="spinner"></span></div>
        </div>
      </div>
      <div class="modal-f">
        <button class="btn btn-dark btn-stop" id="pvstop" title="Cancel — nothing is sent">${icon("stop")}Stop</button>
        <button class="btn btn-secondary" id="pvref" title="Generate these reports again with the latest data">${icon("refresh")}Refresh</button>
        <span class="spacer"></span>
        <button class="btn btn-secondary" id="pvsave" title="Keep the files in the output folder without sending">${icon("download")}Save</button>
        <button class="btn btn-primary" id="pvok">${icon("send")}${linked ? "Approve &amp; Send" : "Approve"}</button>
      </div></div>`;
    document.body.appendChild(back);
    Hydra.hydrateIcons(back);
    const q = (sel) => back.querySelector(sel);
    q("#pvcap").value = cfg["reports.caption"] || "{title}";
    const close = () => { back.remove(); document.removeEventListener("keydown", onKey); };
    function onKey(e) {
      if (e.key === "Escape") close();
      if (e.key === "ArrowRight") step(1);
      if (e.key === "ArrowLeft") step(-1);
    }
    document.addEventListener("keydown", onKey);
    function counter() {
      q("#pvcount").textContent = `${chosen.size} of ${reps.length} selected`;
      q("#pvall").checked = chosen.size === reps.length;
      q("#pvall").indeterminate = chosen.size > 0 && chosen.size < reps.length;
      q("#pvok").disabled = q("#pvsave").disabled = !chosen.size;
      back.querySelectorAll(".pv-item").forEach((el) => el.classList.toggle("off", !chosen.has(+el.dataset.id)));
    }
    async function show() {
      const x = reps.find((y) => y.id === cur);
      back.querySelectorAll(".pv-item").forEach((el) => el.classList.toggle("on", +el.dataset.id === cur));
      q("#pvtitle").textContent = x.title;
      if (!x.pages) {
        q("#pvimg").innerHTML = `<div class="empty"><img src="assets/img/hydra_logo_silver.png"><h3>No image for this report</h3>${esc((x.warnings || []).find((w) => w.startsWith("PDF/PNG")) || "Images were not created for this run.")}</div>`;
        q("#pvpage").textContent = ""; q("#pvprev").disabled = q("#pvnext").disabled = true; return;
      }
      q("#pvimg").innerHTML = `<span class="spinner"></span>`;
      const im = await call("report_image", cur, page);
      if (!im.ok) { q("#pvimg").innerHTML = `<div class="alert err">${esc(im.error)}</div>`; return; }
      if (x.id !== cur) return;
      page = im.page;
      q("#pvimg").innerHTML = `<img src="${im.src}" alt="">`;
      q("#pvpage").textContent = `${im.page + 1} / ${im.pages}`;
      q("#pvprev").disabled = im.page === 0; q("#pvnext").disabled = im.page >= im.pages - 1;
    }
    function step(d) {
      const x = reps.find((y) => y.id === cur);
      const i = reps.indexOf(x);
      if (page + d >= 0 && page + d < (x.pages || 0)) { page += d; return show(); }
      const n = reps[i + d]; if (!n) return;
      cur = n.id; page = d < 0 ? Math.max(0, (n.pages || 1) - 1) : 0; show();
    }
    back.querySelectorAll(".pv-item").forEach((el) => el.onclick = (e) => {
      if (e.target.classList.contains("pvchk")) return;
      cur = +el.dataset.id; page = 0; show();
    });
    back.querySelectorAll(".pvchk").forEach((c) => c.onchange = () => { c.checked ? chosen.add(+c.value) : chosen.delete(+c.value); counter(); });
    q("#pvall").onchange = (e) => {
      reps.forEach((x) => e.target.checked ? chosen.add(x.id) : chosen.delete(x.id));
      back.querySelectorAll(".pvchk").forEach((c) => c.checked = e.target.checked); counter();
    };
    back.querySelectorAll("#pvfmt button").forEach((b) => b.onclick = () => { fmt = b.dataset.f; back.querySelectorAll("#pvfmt button").forEach((y) => y.classList.toggle("on", y === b)); });
    q("#pvprev").onclick = () => step(-1); q("#pvnext").onclick = () => step(1);
    q("#pvx").onclick = close;
    q("#pvstop").onclick = () => { close(); toast("info", "Stopped", "Nothing was sent. The reports stay in Reports History."); };
    q("#pvref").onclick = () => { close(); if (opts.rerun) opts.rerun(); else toast("info", "Refresh", "Open the Run Center to generate again."); };
    async function mark(status, msg) {
      const ids = [...chosen];
      const s = await call("reports_set_status", ids, status);
      if (!s.ok) return toast("error", "Could not update", s.error);
      await call("settings_save", { "reports.send_format": fmt, "reports.caption": q("#pvcap").value });
      close(); toast("success", msg, `${s.updated} report(s)`);
      if (location.hash === "#reports") App.go("reports");
    }
    q("#pvsave").onclick = () => mark("saved", "Saved to the output folder");
    back.querySelectorAll(".pvwa").forEach((a) => a.onclick = (e) => { e.preventDefault(); close(); App.go("whatsapp"); });
    q("#pvok").onclick = async () => {
      if (!linked) return mark("approved", "Approved — link WhatsApp to send");
      const ids = [...chosen];
      const noTo = reps.filter((x) => chosen.has(x.id) && !routesOf(x.report_type).length).map((x) => x.name);
      if (noTo.length === ids.length) return toast("warning", "No recipients", "Choose who gets these reports on the WhatsApp screen first.");
      const r2 = await call("reports_send", ids, fmt, q("#pvcap").value);
      if (!r2.ok) return toast("error", "Not sent", r2.error);
      if (r2.skipped.length) toast("warning", "Not sent — no recipients", r2.skipped.join(", "));
      sending(r2.batch, r2.queued);
    };
    function sending(batch, total) {
      back.querySelectorAll(".pvchk, #pvall, #pvfmt button, #pvcap").forEach((el) => el.disabled = true);
      const f = q(".modal-f");
      f.innerHTML = `<div class="pv-prog"><div class="row"><span class="spinner" id="pvspin"></span><b id="pvptxt">Sending 0 of ${total}…</b><span class="spacer"></span><span class="faint" id="pvpsub"></span></div><div class="bar"><i id="pvbar"></i></div></div>
        <button class="btn btn-dark btn-stop" id="pvcancel">${icon("stop")}Cancel</button><button class="btn btn-primary hidden" id="pvdone">Close</button>`;
      Hydra.hydrateIcons(f);
      q("#pvcancel").onclick = async () => { await call("wa_cancel"); q("#pvpsub").textContent = "Cancelling after the current message…"; };
      q("#pvdone").onclick = () => { close(); if (location.hash === "#reports") App.go("reports"); };
      const t = setInterval(async () => {
        if (!document.body.contains(back)) return clearInterval(t);
        const b = await call("wa_batch", batch);
        if (!b.ok) return;
        const c = b.counts, done = c.sent + c.failed + c.cancelled;
        q("#pvbar").style.width = (100 * done / Math.max(total, 1)) + "%";
        q("#pvptxt").textContent = b.done ? `${c.sent} of ${total} sent` + (c.failed ? ` · ${c.failed} failed` : "") + (c.cancelled ? ` · ${c.cancelled} cancelled` : "") : `Sending ${done + 1} of ${total}…`;
        q("#pvpsub").textContent = b.done ? "" : (b.worker.message || "");
        const per = {};
        b.items.forEach((it) => { (per[it.report_id] = per[it.report_id] || []).push(it.status); });
        Object.entries(per).forEach(([rid, sts]) => {
          const chip = back.querySelector(`[data-st="${rid}"]`); if (!chip) return;
          const st2 = sts.every((x) => x === "sent") ? "sent" : sts.some((x) => x === "failed") ? "failed" : sts.some((x) => x === "sending") ? "sending" : "approved";
          chip.textContent = st2; chip.className = "chip " + (st2 === "sent" ? "ok" : st2 === "failed" ? "err" : "warn");
          const fail = b.items.find((it) => it.report_id === +rid && it.error && it.status === "failed");
          if (fail) chip.title = fail.error;
        });
        if (b.done) {
          clearInterval(t);
          q("#pvspin").remove(); q("#pvcancel").classList.add("hidden"); q("#pvdone").classList.remove("hidden");
          q("#pvbar").classList.toggle("bad", c.failed > 0);
          const fails = b.items.filter((it) => it.status === "failed");
          if (fails.length) q("#pvpsub").textContent = fails[0].recipient + ": " + fails[0].error;
          toast(c.failed ? "warning" : "success", c.failed ? "Some messages failed" : "Reports sent on WhatsApp", `${c.sent} sent` + (c.failed ? `, ${c.failed} failed` : ""));
        }
      }, 1000);
    }
    counter();
    show();
    // thumbnails (first image of each report)
    for (const x of reps) {
      const th = q("#th" + x.id);
      if (!x.pages) { th.innerHTML = icon("file"); Hydra.hydrateIcons(th); continue; }
      call("report_image", x.id, 0).then((im) => { th.innerHTML = im.ok && im.src ? `<img src="${im.src}" alt="">` : ""; });
    }
  }

  // =============================================================== Reports History
  async function reportsHistory(main) {
    const types = (await call("reports_types")).types;
    main.innerHTML = `${head("History", "Reports History", "Every report Hydra has generated. Tick reports and press Preview &amp; Send to approve them again or resend.")}
      <div class="row wrap" style="margin-bottom:12px"><select class="input select" id="hType" style="width:240px"><option value="">All reports</option>${types.map((t) => `<option value="${t.id}">${esc(t.name)}</option>`).join("")}</select>
        <select class="input select" id="hStat" style="width:180px"><option value="">Any status</option>${["generated", "approved", "saved", "sent", "failed", "skipped"].map((x) => `<option>${x}</option>`).join("")}</select>
        <span class="spacer"></span><span class="faint" id="hsel"></span><button class="btn btn-primary" id="hprev" disabled>${icon("eye")}Preview &amp; Send</button></div>
      <div class="card"><div class="card-b" id="hlist"><span class="spinner"></span></div></div>`;
    const picked = new Set();
    function upd() { $("#hprev").disabled = !picked.size; $("#hsel").textContent = picked.size ? `${picked.size} selected` : ""; }
    async function load() {
      const r = await call("reports_history", $("#hType").value, $("#hStat").value);
      if (!r.ok) throw new Error(r.error);
      picked.clear(); upd();
      $("#hlist").innerHTML = r.reports.length ? `<div class="table-wrap"><table class="table"><thead><tr><th style="width:30px"><input type="checkbox" id="hall"></th><th>Report date</th><th>Report</th><th>Generated</th><th>By</th><th>Status</th><th>Files</th></tr></thead><tbody>
        ${r.reports.map((x) => `<tr><td>${x.status === "failed" || x.status === "skipped" ? "" : `<input type="checkbox" class="hchk" value="${x.id}">`}</td><td class="mono">${esc(x.report_date)}</td><td><b>${esc(x.name)}</b><br><small class="faint">${esc(x.title)}</small></td><td class="faint">${fmtTime(x.created_at)}</td><td class="faint">${esc(x.created_by || "")}</td>
          <td><span class="chip ${statusCls(x.status)}" title="${esc((x.warnings || []).join("\n"))}">${esc(x.status)}</span>${x.warnings.length && x.status !== "failed" && x.status !== "skipped" ? ` <span class="chip warn" title="${esc(x.warnings.join("\n"))}">${icon("warn")}${x.warnings.length}</span>` : ""}</td>
          <td>${x.exists ? fileButtons(x) : x.xlsx_path ? `<span class="faint">Files moved</span>` : ""}</td></tr>`).join("")}</tbody></table></div>`
        : `<div class="empty"><img src="assets/img/hydra_logo_silver.png"><h3>No reports yet</h3>Generate them in the Run Center.</div>`;
      Hydra.hydrateIcons($("#hlist"));
      bindOpen($("#hlist"));
      $$(".hchk").forEach((c) => c.onchange = () => { c.checked ? picked.add(+c.value) : picked.delete(+c.value); upd(); });
      const all = $("#hall");
      if (all) all.onchange = () => $$(".hchk").forEach((c) => { c.checked = all.checked; c.onchange(); });
    }
    $("#hType").onchange = load; $("#hStat").onchange = load;
    $("#hprev").onclick = () => previewSend([...picked]);
    await load();
  }

  window.Pages = { previewSend, run: runCenter, reports: reportsHistory, dashboard, notifications, logs, settings: settingsPage, about, placeholder, notifItem, changePassword, colleagues, data: dataPage, territories: territoriesPage };
  Object.keys(PLAN).forEach((k) => window.Pages[k] = placeholder);
  window.Pages.util = { head, money, statusCls };
})();
