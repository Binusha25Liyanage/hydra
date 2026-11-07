/* Setup Wizard: 13 steps. Steps whose phase is not built yet are shown, explained and skippable. */
(function () {
  const { call, icon, esc, $, $$, toast, busy } = Hydra;
  let S = null;          // wizard_state
  let idx = 0;           // current step index
  let sfaDirty = false;

  const LATER = {
    filters: ["Filter Setup", "Choose the filter values Hydra applies on each SFA page, and a date rule for every date field.",
      ["“Learn Filters from SFA” reads every dropdown and its real options", "Date rules: Report Date · Previous Working Day · Month Start → Report Date · Last Month Same Day · Fixed",
       "Defaults: Report Type = All Invoices, Invoice Status = Pending, SO Status = Active, Territory Status = Active"]],
    territories: ["Territory Sync", "Download View Territory (Status = Active) and keep Hydra's territory database up to date.",
      ["Shows new, inactive and renamed territories after every sync", "Monthly auto-sync option"]],
    selling_mode: ["Selling Mode", "Mark every territory as Van Selling or Pre Selling — this decides how Callage is prepared.",
      ["Pre-filled from the SKU report's SALES REP MODEL column", "Bulk actions and search"]],
    targets: ["Targets", "Bring in the National Sales Manager's monthly targets and the management hierarchy.",
      ["Import the NSM target workbook (DB Code / Territory / Distributor / CSR / Target)", "One-click import from Famulus (targets + Sep/Oct history)", "Hierarchy & Targets editor with validation"]],
    calendar: ["Calendar & Competition", "Working days, holidays and the NSM's competition rounds.",
      ["NOWD calculated (with manual override)", "Rounds of selected days, like the NSM's Competition Calendar", "Daily Winners only on competition days"]],
    rules: ["Report Rules", "Winner limits and outlet-category eligibility.",
      ["Van 100,000 / 20 bills · Pre 125,000 / 30 bills (editable per round)", "SMMT/MRP outlet categories excluded from competition", "Excluded national SMMT territories"]],
    whatsapp: ["WhatsApp Link", "Link WhatsApp Web once by QR code and choose which groups get which reports.",
      ["QR shown inside Hydra", "Recipients per report, test message", "Nothing is ever sent without your approval"]],
    schedule: ["Schedule", "Times for automatic runs, each with its own report date.",
      ["Report date per time: Today / Yesterday", "Monthly jobs (Finalized Target vs Achievement, Rep Performance, Territory sync)", "Runs even when the Hydra window is closed"]],
  };

  // ---------------------------------------------------------------- stepper
  function renderSteps() {
    const steps = S.steps;
    $("#steps").innerHTML = steps.map((s, i) => {
      const cls = [i === idx ? "on" : "", s.done ? "done" : "", !s.available ? "later" : ""].join(" ");
      const n = s.done && i !== idx ? icon("check") : String(s.n).padStart(2, "0");
      return `<div class="st ${cls}" data-i="${i}"><div class="n">${n}</div><div><b>${esc(s.title)}</b><small>${esc(s.subtitle)}</small></div>
        ${!s.available ? `<span class="soon">Phase ${s.phase}</span>` : ""}</div>`;
    }).join("");
    $$(".st").forEach((el) => el.onclick = () => go(+el.dataset.i));
    const on = $(".st.on"); if (on) on.scrollIntoView({ block: "nearest" });
    const done = steps.filter((s) => s.done).length;
    $("#seqbar").style.width = (100 * (idx + 1) / steps.length) + "%";
    $("#stage").textContent = `Step ${idx + 1} / ${steps.length}`;
    $("#seqfoot").textContent = `${done} of ${steps.length} steps done · required now: SFA, Page URLs, Save Location`;
    $("#back").disabled = idx === 0;
    const s = steps[idx];
    $("#next").innerHTML = s.id === "finish" ? `${icon("check")}Finish setup` : (!s.available ? `Skip for now ${icon("arrow")}` : `Save &amp; continue ${icon("arrow")}`);
    if (s.id === "welcome") $("#next").innerHTML = `Start setup ${icon("arrow")}`;
    $("#navhint").textContent = !s.available ? `Available from Phase ${s.phase} — you can finish this later in Settings.` : "";
  }

  function go(i) { idx = Math.max(0, Math.min(S.steps.length - 1, i)); renderSteps(); renderContent(); }

  function head(eyebrow, title, text) {
    return `<div class="page-h"><div><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1>${text ? `<p>${text}</p>` : ""}</div></div>`;
  }

  // ---------------------------------------------------------------- steps
  function renderContent() {
    const s = S.steps[idx];
    const c = $("#content");
    if (s.id === "welcome") c.innerHTML = welcome();
    else if (s.id === "sfa") { c.innerHTML = sfaForm(); bindSfa(); }
    else if (s.id === "pages") { c.innerHTML = pagesForm(); bindPages(); }
    else if (s.id === "output") { c.innerHTML = outputForm(); bindOutput(); }
    else if (s.id === "finish") c.innerHTML = finish();
    else c.innerHTML = later(s);
    Hydra.hydrateIcons(c); Hydra.bindEyes(c);
  }

  function welcome() {
    return `${head("Step 01 · Welcome", "Welcome to Hydra", "")}
      <div class="card"><div class="card-b welcome-grid"><img src="assets/img/hydra_logo_silver.png" alt="">
        <div class="stack"><p class="muted" style="margin:0;font-size:14px">Hydra signs in to SalesPro SFA with your account, downloads the sales Excel reports,
          converts every number, builds the management reports (Day Report, Target vs Achievement, Sales Comparison, Daily Winners, Pending Orders and the monthly
          Finalized report) and sends them to WhatsApp after you approve them.</p>
          <div class="alert info">${icon("info")}<div><b>This is Phase 1 — the foundation.</b>Today you set up the SFA connection, the page URLs and the save folder.
          The other steps are shown so you can see the whole journey; they switch on as each phase is delivered and can be completed later from Settings.</div></div>
          <div class="row wrap"><span class="chip ok">${icon("check")}SFA sign-in</span><span class="chip ok">${icon("check")}Page checks</span><span class="chip ok">${icon("check")}Save folder</span>
          <span class="chip">Filters · Phase 2</span><span class="chip">Targets · Phase 5</span><span class="chip">WhatsApp · Phase 9</span><span class="chip">Schedule · Phase 10</span></div>
        </div></div></div>`;
  }

  // ----- SFA connection
  function sfaForm() {
    const f = S.sfa;
    const b = (id, title, sub) => `<div class="bcard ${f.browser === id ? "on" : ""}" data-b="${id}"><b>${title}</b><small>${sub}</small></div>`;
    return `${head("Step 02 · SFA Connection", "Connect to SalesPro SFA", "Hydra signs in with these details every day at startup and before each automatic run. The password is stored in Windows Credential Manager — never in the database.")}
      <div class="card"><div class="card-b stack">
        <div class="field"><label>SFA URL</label><div class="input-wrap">${icon("globe")}<input class="input mono" id="base_url" value="${esc(f.base_url)}" placeholder="https://lakmee.salespro.lk"></div></div>
        <div class="grid-2">
          <div class="field"><label>SFA username</label><div class="input-wrap">${icon("user")}<input class="input" id="username" value="${esc(f.username)}" autocomplete="off"></div></div>
          <div class="field"><label>SFA password</label><div class="input-wrap">${icon("lock")}<input class="input" id="password" type="password" placeholder="${f.has_password ? "Saved — leave blank to keep" : "Enter password"}" autocomplete="new-password"><button type="button" class="eye"></button></div></div>
        </div>
        <div class="field"><label>Browser</label><div class="browser-cards">
          ${b("chromium", "Chromium (built in)", "Recommended · installed with Hydra")}${b("msedge", "Microsoft Edge", "Uses Edge already on this PC")}${b("chrome", "Google Chrome", "Uses Chrome already on this PC")}</div></div>
        <div class="grid-2">
          <div class="toggle-row"><div class="t"><b>Run the browser hidden</b><small>Turn off to watch Hydra work (useful for testing)</small></div><label class="toggle"><input type="checkbox" id="headless" ${f.headless ? "checked" : ""}><span></span></label></div>
          <div class="field"><label>Timeout (seconds)</label><input class="input" id="timeout_s" type="number" min="15" max="180" value="${esc(f.timeout_s)}"><div class="hint">How long to wait for SFA before giving up.</div></div>
        </div>
        <details><summary class="faint" style="cursor:pointer">Advanced</summary><div class="field" style="margin-top:10px"><label>Login page path</label><input class="input mono" id="login_path" value="${esc(f.login_path)}"><div class="hint">Usually “/”. Change only if the login form is on another page.</div></div></details>
        <div class="row"><button class="btn btn-secondary" id="test">${icon("zap")}Test Login</button><span class="faint">Opens a browser, signs in and confirms the “Welcome” name.</span></div>
        <div class="result" id="result">${resultHtml(f.last_test)}</div>
      </div></div>`;
  }
  function resultHtml(r) {
    if (!r || !r.message) return "";
    const cls = r.ok ? "ok" : "err";
    const name = r.display_name ? ` as <b style="display:inline">${esc(r.display_name)}</b>` : "";
    return `<div class="alert ${cls}">${icon(r.ok ? "okcircle" : "error")}<div><b>${r.ok ? "Signed in to SFA" : "Sign-in failed"}</b>${esc(r.message)}${r.ok ? name : ""} · ${(r.duration_ms / 1000).toFixed(1)} s${r.ts ? " · " + Hydra.fmtTime(r.ts) : ""}</div></div>`;
  }
  function sfaData() {
    return { base_url: $("#base_url").value.trim(), username: $("#username").value.trim(), password: $("#password").value,
      browser: $(".bcard.on").dataset.b, headless: $("#headless").checked, timeout_s: +$("#timeout_s").value || 45, login_path: $("#login_path").value.trim() || "/" };
  }
  function bindSfa() {
    $$(".bcard").forEach((el) => el.onclick = () => { $$(".bcard").forEach((x) => x.classList.remove("on")); el.classList.add("on"); sfaDirty = true; });
    $$("#content input").forEach((el) => el.addEventListener("input", () => sfaDirty = true));
    $("#test").onclick = async () => {
      busy($("#test"), true, "Signing in to SFA…");
      $("#result").innerHTML = `<div class="alert info">${icon("info")}<div><b>Testing…</b>A browser is opening SalesPro and signing in. This takes 5–30 seconds.</div></div>`;
      const r = await call("sfa_test_login", sfaData());
      busy($("#test"), false);
      if (!r.ok) { $("#result").innerHTML = `<div class="alert err">${icon("error")}<div>${esc(r.error)}</div></div>`; return; }
      $("#result").innerHTML = resultHtml(r.result);
      S.sfa.last_test = r.result;
    };
  }
  async function saveSfa() {
    const r = await call("sfa_save", sfaData());
    if (!r.ok) { toast("error", "Not saved", r.error); return false; }
    S.sfa = r.sfa; sfaDirty = false; markDone("sfa");
    toast("success", "SFA connection saved", S.sfa.last_test && S.sfa.last_test.ok ? "" : "Tip: press Test Login to confirm it works.");
    return true;
  }

  // ----- Page URLs
  function pagesForm() {
    const rows = S.pages.map((p) => `<tr data-key="${p.key}"><td><b>${esc(p.name)}</b></td>
      <td><input class="input mono" value="${esc(p.url)}" placeholder="${p.key === "rep_performance" ? "Paste the Rep Performance Report path" : ""}"></td>
      <td class="st-cell" style="width:260px"><span class="faint">Not tested</span></td></tr>`).join("");
    return `${head("Step 03 · Page URLs", "SFA pages Hydra uses", "Paths are added to the SFA URL (<span class='mono'>" + esc(S.sfa.base_url) + "</span>). You can also paste a full https:// address.")}
      <div class="card"><div class="card-b stack">
        <div class="table-wrap"><table class="table"><thead><tr><th style="width:250px">Page</th><th>Path / URL</th><th>Check</th></tr></thead><tbody>${rows}</tbody></table></div>
        <div class="row"><button class="btn btn-secondary" id="testpages">${icon("zap")}Save &amp; test all pages</button><span class="faint">Signs in, opens every page and reads its title (e.g. “OUTLET WISE SKU SALES REPORT”). Nothing is downloaded.</span></div>
        <div class="alert info">${icon("info")}<div><b>Rep Performance Report</b>Needed for the monthly Finalized Target vs Achievement. Open it in SFA and copy the part of the address after <span class="mono">salespro.lk</span>.</div></div>
      </div></div>`;
  }
  function pagesData() { return $$("#content tbody tr").map((tr) => ({ key: tr.dataset.key, url: $("input", tr).value.trim() })); }
  function bindPages() {
    $("#testpages").onclick = async () => {
      const sv = await call("pages_save", pagesData());
      if (!sv.ok) { toast("error", "Not saved", sv.error); return; }
      S.pages = sv.pages; markDone("pages");
      busy($("#testpages"), true, "Opening SFA pages…");
      $$(".st-cell").forEach((td) => td.innerHTML = `<span class="row"><span class="spinner"></span><span class="faint">Waiting…</span></span>`);
      const r = await call("pages_test");
      busy($("#testpages"), false);
      if (!r.ok) { toast("error", "Page test failed", r.error); return; }
      r.results.forEach((x) => {
        const td = $(`tr[data-key="${x.key}"] .st-cell`);
        if (td) td.innerHTML = `<span class="chip ${x.ok ? "ok" : "err"}" title="${esc(x.message)}">${icon(x.ok ? "check" : "warn")}${x.ok ? "OK" : "Problem"}</span> <span class="faint" style="font-size:12px">${esc(x.message)}</span>`;
      });
    };
  }
  async function savePages() {
    const r = await call("pages_save", pagesData());
    if (!r.ok) { toast("error", "Not saved", r.error); return false; }
    S.pages = r.pages; markDone("pages"); return true;
  }

  // ----- Save location
  function outputForm() {
    return `${head("Step 10 · Save Location", "Where Hydra saves reports", "Every run gets its own dated folder with the raw SFA downloads and the finished reports.")}
      <div class="card"><div class="card-b stack">
        <div class="field"><label>Reports folder</label><div class="row"><div class="input-wrap" style="flex:1">${icon("folder")}<input class="input mono" id="root" value="${esc(S.output.root)}"></div>
          <button class="btn btn-secondary" id="browse">${icon("folder")}Browse…</button></div></div>
        <div class="field"><label>Folder structure</label><div class="tree" id="tree"></div></div>
      </div></div>`;
  }
  function drawTree() {
    const r = ($("#root").value || "…").replace(/[\\/]+$/, "");
    $("#tree").textContent = `${r}\\\n└── 2026-11\\\n    └── 2026-11-03\\\n        ├── inputs\\    (raw SFA downloads: SKU, Callage, Sales Order…)\n        └── outputs\\   (Excel · PDF · PNG reports)\n${r}\\backups\\   (daily database backup)`;
  }
  function bindOutput() {
    drawTree();
    $("#root").addEventListener("input", drawTree);
    $("#browse").onclick = async () => {
      const r = await call("choose_folder", $("#root").value);
      if (r.ok && r.path) { $("#root").value = r.path; drawTree(); }
    };
  }
  async function saveOutput() {
    const r = await call("output_save", $("#root").value);
    if (!r.ok) { toast("error", "Not saved", r.error); return false; }
    S.output.root = r.root; markDone("output"); return true;
  }

  // ----- later phases / finish
  function later(s) {
    const [title, text, bullets] = LATER[s.id] || [s.title, "", []];
    return `${head(`Step ${String(s.n).padStart(2, "0")} · ${title}`, title, esc(text))}
      <div class="card"><div class="card-b"><div class="phase-card" style="margin:0 auto;padding:20px">
        <img src="assets/img/hydra_logo_silver.png" alt=""><h2>Arrives in Phase ${s.phase}</h2>
        <p class="muted">This step switches on when Phase ${s.phase} is delivered. Skip it for now — Hydra will remind you on the Dashboard.</p>
        <ul>${bullets.map((b) => `<li>${esc(b)}</li>`).join("")}</ul></div></div></div>`;
  }
  function finish() {
    const rows = S.steps.filter((s) => !["welcome", "finish"].includes(s.id)).map((s) => {
      const cls = s.done ? "ok" : (s.available ? "todo" : "later");
      const ic = s.done ? "okcircle" : (s.available ? "warn" : "clock");
      const d = s.done ? "Done" : (s.available ? "Required — not done yet" : `Phase ${s.phase}`);
      return `<div class="sumrow ${cls}">${icon(ic)}<b>${esc(s.title)}</b><span class="d">${d}</span></div>`;
    }).join("");
    return `${head("Step 13 · Finish", "Review & start", "When you finish, Hydra restarts its splash screen in daily mode: the bar will now follow the real checks — database, save folder, internet, SFA server, a live SFA sign-in, WhatsApp, schedule and targets.")}
      <div class="card"><div class="card-b">${rows}</div></div>`;
  }

  function markDone(id) { const s = S.steps.find((x) => x.id === id); if (s) s.done = true; }

  // ---------------------------------------------------------------- navigation
  $("#back").onclick = () => go(idx - 1);
  $("#next").onclick = async () => {
    const s = S.steps[idx];
    const btn = $("#next");
    let ok = true;
    busy(btn, true, "Saving…");
    try {
      if (s.id === "sfa") ok = await saveSfa();
      else if (s.id === "pages") ok = await savePages();
      else if (s.id === "output") ok = await saveOutput();
      else if (s.id === "finish") {
        const r = await call("wizard_complete");
        if (!r.ok) { toast("warning", "Not finished yet", r.error); ok = false; }
        else { location.href = "splash.html"; return; }
      }
    } finally { busy(btn, false); }
    if (ok) go(idx + 1);
  };
  $("#exit").onclick = () => location.href = "app.html";

  async function init() {
    const st = await call("auth_state");
    if (!st.user) { location.href = "login.html"; return; }
    $("#userchip").textContent = `${st.user.display_name} · ${st.user.role}`;
    if (st.setup_completed) $("#exit").classList.remove("hidden");
    S = await call("wizard_state");
    if (!S.ok) { toast("error", "Cannot open the wizard", S.error); return; }
    const want = new URLSearchParams(location.search).get("step");
    const i = want ? S.steps.findIndex((x) => x.id === want) : 0;
    go(i >= 0 ? i : 0);
  }
  Hydra.ready.then(init);
})();
