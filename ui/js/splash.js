/* Splash screen: drives the real startup sequence and routes to the next screen.
   first_run → smooth cosmetic bar, then account creation + setup wizard
   daily     → the bar follows the real checks (DB, folders, internet, SFA sign-in, WhatsApp…) */
(function () {
  const { call, icon, esc, $ } = Hydra;
  let shown = 0, target = 0, timer = null, runningSince = {}, mode = "daily";

  function animate() {
    shown += (target - shown) * 0.18;
    if (Math.abs(target - shown) < 0.4) shown = target;
    $("#bar").style.width = shown.toFixed(1) + "%";
    $("#pct").textContent = Math.round(shown) + "%";
    requestAnimationFrame(animate);
  }

  function stepIcon(state) {
    if (state === "running") return '<span class="spinner"></span>';
    return icon({ ok: "check", warning: "warn", error: "warn", skipped: "skip", pending: "clock" }[state] || "clock");
  }

  function renderSteps(steps) {
    if (mode === "first_run") return;
    $("#steps").innerHTML = steps.map((s) =>
      `<div class="s ${s.state}" title="${esc(s.detail)}">${stepIcon(s.state)}<span>${esc(s.label)}${s.detail && s.state !== "running" && s.state !== "pending" ? " — " + esc(s.detail) : ""}</span></div>`
    ).join("");
  }

  function renderActions(snap) {
    const box = $("#actions");
    const run = snap.steps.find((s) => s.state === "running");
    if (run && run.skippable) {
      runningSince[run.id] = runningSince[run.id] || Date.now();
      if (Date.now() - runningSince[run.id] > 4000 && !$("#skip")) {
        box.innerHTML = `<button class="btn btn-ghost btn-sm" id="skip">${icon("skip")}Skip SFA check — continue offline</button>`;
        $("#skip").onclick = async () => { $("#skip").disabled = true; await call("startup_skip"); };
      }
    } else if ($("#skip")) {
      box.innerHTML = "";
    }
  }

  function showFatal(snap) {
    clearInterval(timer);
    $("#sdot").className = "dot err";
    const bad = snap.steps.find((s) => s.state === "error");
    $("#fatal").classList.remove("hidden");
    $("#fatal").innerHTML = `<div class="alert err">${icon("error")}<div><b>Hydra cannot start</b>${esc(bad ? bad.label + ": " + bad.detail : snap.message)}</div></div>`;
    $("#actions").innerHTML = `
      <button class="btn btn-primary" id="retry">${icon("refresh")}Retry</button>
      <button class="btn btn-dark" id="copylog">${icon("copy")}Copy log</button>
      <button class="btn btn-ghost" id="folder">${icon("folder")}Open data folder</button>`;
    $("#retry").onclick = () => location.reload();
    $("#copylog").onclick = async () => {
      const r = await call("recent_log_text", 400);
      await call("copy_text", r.text || "");
      Hydra.toast("success", "Log copied to clipboard");
    };
    $("#folder").onclick = () => call("open_folder", "data");
  }

  function finish(snap) {
    clearInterval(timer);
    target = 100;
    const go = () => {
      const routes = { create_admin: "login.html?mode=create", login: "login.html", app: "app.html", wizard: "wizard.html" };
      location.href = routes[snap.next] || "login.html";
    };
    if (snap.warnings && mode === "daily") {
      $("#sdot").className = "dot warn";
      $("#msg").textContent = snap.message + " — details on the Dashboard";
      setTimeout(go, 1800);
    } else {
      $("#sdot").className = "dot ok";
      setTimeout(go, mode === "first_run" ? 500 : 700);
    }
  }

  async function poll() {
    const snap = await call("startup_poll");
    if (!snap.ok || snap.started === false) return;
    target = Math.max(target, snap.progress);
    $("#msg").textContent = snap.message;
    renderSteps(snap.steps);
    renderActions(snap);
    if (snap.finished) snap.fatal ? showFatal(snap) : finish(snap);
  }

  async function start() {
    requestAnimationFrame(animate);
    const info = await call("app_info");
    $("#ver").textContent = `Hydra v${info.version} · ${info.phase}`;
    const r = await call("startup_begin");
    mode = r.mode;
    $("#mode").textContent = mode === "first_run" ? "First-time setup" : "Daily startup check";
    $("#foot-right").textContent = mode === "first_run" ? "Welcome" : "Checking SFA, WhatsApp and data";
    if (mode === "first_run") $("#steps").classList.add("hidden");
    timer = setInterval(poll, 150);
  }

  Hydra.ready.then(start);
})();
