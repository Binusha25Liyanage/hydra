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
        ${card("WhatsApp", "message", wa.linked ? "Linked" : "Not linked", wa.linked ? esc(wa.number) : "Linking arrives in Phase 9")}
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
    run: [6, "Run Center", ["Report date picker and report checkboxes", "Live step list with time and MB per step", "Stop and Retry failed step", "Live log with Copy Log"]],
    reports: [6, "Reports History", ["Every generated report with status (Generated / Approved / Sent / Saved / Failed)", "Open Excel / PDF / PNG, Resend, Open folder"]],
    territories: [3, "Territories", ["Active territory database synced from View Territory", "Van / Pre selling mode per territory", "Changes after each sync"]],
    targets: [5, "Hierarchy & Targets", ["Import the NSM target workbook or Famulus", "Tree + spreadsheet editor, Lock month, audit history", "Validation against active SFA territories"]],
    calendar: [5, "Calendar & Competition", ["NOWD with manual override", "Competition rounds exactly like the NSM's calendar", "Export the calendar as a PNG"]],
    aliases: [5, "Aliases & Labels", ["Territory and rep name aliases", "Monthly label overrides", "Excluded test territories"]],
    reconciliation: [7, "Reconciliation", ["Hydra achievement vs SFA Rep Performance per territory", "Tolerance highlight and possible causes"]],
    schedule: [10, "Schedule", ["Run times with Today / Yesterday report date", "Monthly jobs and Activity Report schedule", "Runs while the window is closed"]],
    whatsapp: [9, "WhatsApp", ["Link by QR inside Hydra", "Recipients per report, test message", "Send history"]],
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

  window.Pages = { dashboard, notifications, logs, settings: settingsPage, about, placeholder, notifItem, changePassword, colleagues };
  Object.keys(PLAN).forEach((k) => window.Pages[k] = placeholder);
})();
