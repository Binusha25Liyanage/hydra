/* Hydra app shell: router, top bar, notifications panel, user menu, status strip. */
(function () {
  const { call, icon, esc, $, $$, toast, fmtAgo, fmtTime } = Hydra;
  const TITLES = {
    dashboard: "Dashboard", run: "Run Center", reports: "Reports History", territories: "Territories",
    targets: "Hierarchy & Targets", calendar: "Competition Calendar", aliases: "Aliases & Labels",
    reconciliation: "Reconciliation", schedule: "Schedule", whatsapp: "WhatsApp", activity: "Activity Monitor",
    notifications: "Notifications", logs: "Logs", settings: "Settings", about: "About", colleagues: "Colleagues", data: "SFA Data",
  };
  window.App = { user: null, status: null, go, refreshStatus };

  function go(page) {
    if (!TITLES[page]) page = "dashboard";
    $$("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.page === page));
    $("#crumb").textContent = TITLES[page];
    const main = $("#main");
    main.scrollTop = 0;
    main.innerHTML = `<div class="row faint"><span class="spinner"></span>Loading…</div>`;
    if (history.replaceState) history.replaceState(null, "", "#" + page);
    Promise.resolve((Pages[page] || Pages.placeholder)(main, page)).then(() => Hydra.hydrateIcons(main)).catch((e) => {
      main.innerHTML = `<div class="alert err">${icon("error")}<div><b>Could not open ${esc(TITLES[page])}</b>${esc(e.message || e)}</div></div>`;
    });
  }

  async function refreshStatus() {
    const s = await call("status_bar");
    if (!s.ok) return;
    App.status = s;
    const sfa = s.sfa;
    const sfaCls = sfa.logged_in ? "ok" : (sfa.reachable === false ? "err" : "warn");
    $("#sfachip").className = "chip " + sfaCls;
    $("#sfachip").innerHTML = `<span class="dot ${sfaCls}"></span>SFA: ${sfa.logged_in ? "Connected" : (sfa.reachable === false ? "Unreachable" : "Not signed in")}`;
    $("#sfachip").title = sfa.message || "";
    const wa = s.whatsapp;
    $("#wachip").className = "chip " + (wa.linked ? "ok" : "");
    $("#wachip").innerHTML = `<span class="dot ${wa.linked ? "ok" : "off"}"></span>WA: ${wa.linked ? "Ready" : "Not linked"}`;
    ["#bellbadge", "#navbadge"].forEach((id) => { $(id).textContent = s.unread; $(id).classList.toggle("hidden", !s.unread); });
    $("#s-next").textContent = s.next_run ? fmtTime(s.next_run) : "Not scheduled";
    $("#s-data").textContent = s.data_today_mb.toFixed(1) + " MB";
    $("#s-worker").textContent = s.worker.state === "not_installed" ? "Not installed (Phase 10)" : s.worker.label;
    $("#s-sfa").textContent = sfa.ts ? fmtAgo(sfa.ts) + (sfa.logged_in ? " · OK" : " · failed") : "—";
    $("#s-ver").textContent = "Hydra v" + s.version;
    $("#vbadge").textContent = "v" + s.version.split(".").slice(0, 2).join(".");
  }

  // ---------------------------------------------------------------- notifications dropdown
  async function openBell() {
    const p = $("#npanel");
    if (!p.classList.contains("hidden")) { p.classList.add("hidden"); return; }
    $("#umenu").classList.add("hidden");
    const r = await call("notifications_list", false, "");
    const items = (r.items || []).slice(0, 12);
    $("#nlist").innerHTML = items.length ? items.map(Pages.notifItem).join("") : `<div class="empty" style="padding:30px">No notifications yet</div>`;
    p.classList.remove("hidden");
  }
  $("#bell").onclick = openBell;
  $("#readall").onclick = async () => { await call("notifications_mark_read", null); $$(".nitem.unread").forEach((n) => n.classList.remove("unread")); refreshStatus(); };
  $("#nall").onclick = (e) => { e.preventDefault(); $("#npanel").classList.add("hidden"); go("notifications"); };

  // ---------------------------------------------------------------- user menu
  $("#avatar").onclick = () => { $("#npanel").classList.add("hidden"); $("#umenu").classList.toggle("hidden"); };
  $("#m-logout").onclick = async () => { await call("auth_logout"); location.href = "login.html"; };
  $("#m-wizard").onclick = () => location.href = "wizard.html";
  $("#m-pass").onclick = () => { $("#umenu").classList.add("hidden"); Pages.changePassword(); };
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#npanel,#bell")) $("#npanel").classList.add("hidden");
    if (!e.target.closest("#umenu,#avatar")) $("#umenu").classList.add("hidden");
  });

  $("#collapse").onclick = () => document.body.classList.toggle("collapsed");
  $$("#nav a").forEach((a) => a.onclick = () => go(a.dataset.page));

  async function init() {
    const st = await call("auth_state");
    if (!st.user) { location.href = "login.html"; return; }
    if (!st.setup_completed) { location.href = "wizard.html"; return; }
    App.user = st.user;
    $("#avatar").textContent = (st.user.display_name || st.user.username).trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
    $("#uname").textContent = st.user.display_name;
    $("#urole").textContent = `${st.user.username} · ${st.user.role}`;
    if (st.user.role === "user") $("#m-wizard").classList.add("hidden");
    $$("[data-role]").forEach((el) => el.classList.toggle("hidden", el.dataset.role !== st.user.role));
    const info = await call("app_info");
    if (info.ok) $("#sidefoot").textContent = info.phase;
    await refreshStatus();
    setInterval(refreshStatus, 30000);
    go((location.hash || "#dashboard").slice(1));
  }
  Hydra.ready.then(init);
})();
