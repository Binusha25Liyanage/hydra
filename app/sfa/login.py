"""Log in to SalesPro SFA with Playwright and keep the session for later runs.

Used by the splash screen (daily check), the setup wizard ("Test Login") and,
from Phase 2, by every download job. A saved session (cookies) is tried first,
so most days the login form is not even needed.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger("hydra.sfa")

ProgressFn = Callable[[int, str], None]


class Cancelled(Exception):
    pass


@dataclass
class LoginConfig:
    base_url: str
    login_path: str
    username: str
    password: str
    browser: str = "chromium"            # chromium | msedge | chrome
    headless: bool = True
    timeout_s: int = 45
    selectors: dict = field(default_factory=dict)
    state_path: Path | None = None       # where to save/load the session


@dataclass
class LoginResult:
    ok: bool
    message: str
    display_name: str = ""
    used_saved_session: bool = False
    duration_ms: int = 0
    kind: str = ""                       # ok | credentials | timeout | browser | network | config | cancelled | error

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _first_visible(page, selectors: list[str], timeout_ms: int = 0):
    """Return the first visible locator from a list of selectors, else None."""
    deadline = time.time() + timeout_ms / 1000
    while True:
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    return loc
            except Exception:
                continue
        if time.time() >= deadline:
            return None
        time.sleep(0.25)


def _welcome_name(page) -> str:
    try:
        text = page.evaluate("() => document.body ? document.body.innerText : ''")
    except Exception:
        return ""
    m = re.search(r"Welcome,?\s*\n?\s*([A-Za-z][^\n]{1,60})", text or "")
    return m.group(1).strip() if m else ""


def check_login(cfg: LoginConfig, progress: ProgressFn | None = None,
                cancel: threading.Event | None = None) -> LoginResult:
    progress = progress or (lambda pct, msg: None)
    t0 = time.perf_counter()

    def done(ok: bool, msg: str, kind: str, name: str = "", saved: bool = False) -> LoginResult:
        r = LoginResult(ok, msg, name, saved, int((time.perf_counter() - t0) * 1000), kind)
        (log.info if ok else log.warning)("SFA login: %s (%s ms)", msg, r.duration_ms)
        return r

    def check_cancel():
        if cancel is not None and cancel.is_set():
            raise Cancelled()

    if not cfg.base_url:
        return done(False, "SFA URL is not set", "config")
    if not cfg.username or not cfg.password:
        return done(False, "SFA username or password is not saved", "config")

    sel = cfg.selectors or {}
    url = cfg.base_url.rstrip("/") + "/" + (cfg.login_path or "/").lstrip("/")
    timeout_ms = max(10, int(cfg.timeout_s)) * 1000

    try:
        from playwright.sync_api import Error as PwError
        from playwright.sync_api import TimeoutError as PwTimeout
        from playwright.sync_api import sync_playwright
    except ImportError:
        return done(False, "Playwright is not installed (pip install playwright)", "browser")

    try:
        with sync_playwright() as p:
            progress(10, "Opening browser…")
            check_cancel()
            launch_args = {"headless": cfg.headless}
            if cfg.browser in ("msedge", "chrome"):
                launch_args["channel"] = cfg.browser
            try:
                browser = p.chromium.launch(**launch_args)
            except PwError as e:
                hint = ("run 'playwright install chromium'" if cfg.browser == "chromium"
                        else f"is {cfg.browser} installed?")
                return done(False, f"Could not start the browser — {hint} ({str(e).splitlines()[0]})", "browser")
            try:
                ctx_args = {"accept_downloads": True}
                if cfg.state_path and Path(cfg.state_path).exists():
                    ctx_args["storage_state"] = str(cfg.state_path)
                context = browser.new_context(**ctx_args)
                context.set_default_timeout(timeout_ms)
                page = context.new_page()

                progress(30, "Opening SFA…")
                check_cancel()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                # 1) Saved session still valid?
                if "storage_state" in ctx_args:
                    progress(45, "Checking saved session…")
                    if _first_visible(page, sel.get("logged_in", []), 4000) and \
                            not _first_visible(page, sel.get("password", []), 0):
                        context.storage_state(path=str(cfg.state_path))
                        return done(True, "Signed in to SFA (saved session)", "ok", _welcome_name(page), True)

                # 2) Fill in the login form
                progress(55, "Entering credentials…")
                check_cancel()
                pw_box = _first_visible(page, sel.get("password", []), 8000)
                if pw_box is None:
                    if _first_visible(page, sel.get("logged_in", []), 0):
                        return done(True, "Signed in to SFA", "ok", _welcome_name(page))
                    return done(False, "Could not find the SFA login form — check the SFA URL / login path",
                                "config")
                user_box = _first_visible(page, sel.get("username", []), 2000)
                if user_box is None:
                    return done(False, "Could not find the username box on the SFA login page", "config")
                user_box.fill(cfg.username)
                pw_box.fill(cfg.password)

                progress(70, "Signing in…")
                check_cancel()
                submit = _first_visible(page, sel.get("submit", []), 1000)
                if submit is not None:
                    submit.click()
                else:
                    pw_box.press("Enter")

                # 3) Wait for the logged-in page (or an error)
                progress(85, "Verifying login…")
                deadline = time.time() + timeout_ms / 1000
                while time.time() < deadline:
                    check_cancel()
                    if _first_visible(page, sel.get("logged_in", []), 0) and \
                            not _first_visible(page, sel.get("password", []), 0):
                        if cfg.state_path:
                            context.storage_state(path=str(cfg.state_path))
                        return done(True, "Signed in to SFA", "ok", _welcome_name(page))
                    body = (page.evaluate("() => document.body ? document.body.innerText : ''") or "").lower()
                    if any(w in body for w in ("invalid", "incorrect", "wrong password", "not match", "failed")):
                        return done(False, "SFA rejected the username or password", "credentials")
                    time.sleep(0.5)
                return done(False, f"SFA did not finish signing in within {cfg.timeout_s} s", "timeout")
            finally:
                browser.close()
    except Cancelled:
        return done(False, "SFA check skipped", "cancelled")
    except PwTimeout:
        return done(False, f"SFA did not respond within {cfg.timeout_s} s", "timeout")
    except Exception as e:  # network errors surface as Playwright errors
        msg = str(e).splitlines()[0]
        kind = "network" if "net::" in msg or "ERR_" in msg else "error"
        return done(False, f"SFA login error: {msg}", kind)


def config_from_settings(password: str | None = None, overrides: dict | None = None) -> LoginConfig:
    """Build a LoginConfig from saved settings (overrides come from the wizard form)."""
    from .. import paths, settings
    o = overrides or {}
    return LoginConfig(
        base_url=o.get("base_url", settings.get("sfa.base_url")),
        login_path=o.get("login_path", settings.get("sfa.login_path")),
        username=o.get("username", settings.get("sfa.username")),
        password=password if password is not None else settings.get_secret("sfa.password"),
        browser=o.get("browser", settings.get("sfa.browser")),
        headless=bool(o.get("headless", settings.get("sfa.headless"))),
        timeout_s=int(o.get("timeout_s", settings.get("startup.sfa_timeout_s"))),
        selectors=settings.get("sfa.selectors"),
        state_path=paths.sfa_state_path(),
    )


def check_pages(cfg: LoginConfig, pages: list[dict], progress: ProgressFn | None = None) -> list[dict]:
    """Open each SFA page with the saved session and report the page heading.

    Proves the URL is right (e.g. "OUTLET WISE SKU SALES REPORT") without
    downloading anything. Signs in first if the saved session has expired.
    """
    progress = progress or (lambda pct, msg: None)
    results: list[dict] = []
    login = check_login(cfg, lambda p, m: progress(int(p * 0.3), m))
    if not login.ok:
        return [{"key": pg["key"], "ok": False, "message": f"Not signed in: {login.message}"} for pg in pages]
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        launch_args = {"headless": cfg.headless}
        if cfg.browser in ("msedge", "chrome"):
            launch_args["channel"] = cfg.browser
        browser = p.chromium.launch(**launch_args)
        try:
            context = browser.new_context(storage_state=str(cfg.state_path))
            page = context.new_page()
            for i, pg in enumerate(pages):
                progress(30 + int(70 * i / max(1, len(pages))), f"Opening {pg['name']}…")
                if not pg.get("url"):
                    results.append({"key": pg["key"], "ok": False, "message": "No URL set"})
                    continue
                try:
                    resp = page.goto(pg["url"], wait_until="domcontentloaded", timeout=cfg.timeout_s * 1000)
                    page.wait_for_timeout(800)
                    if _first_visible(page, cfg.selectors.get("password", []), 0):
                        results.append({"key": pg["key"], "ok": False,
                                        "message": "Redirected to the login page (session expired?)"})
                        continue
                    heading = page.evaluate("""() => {
                        const h = [...document.querySelectorAll('h1,h2,h3,.page-title,.card-title')]
                          .map(e => e.innerText.trim()).filter(t => t && t.length < 80);
                        return h[0] || document.title || '';
                    }""")
                    code = resp.status if resp else 0
                    ok = code < 400
                    results.append({"key": pg["key"], "ok": ok, "status": code, "heading": heading,
                                    "message": (f"Found “{heading}”" if heading else "Page opened") if ok
                                    else f"HTTP {code}"})
                except Exception as e:
                    results.append({"key": pg["key"], "ok": False, "message": str(e).splitlines()[0]})
            context.storage_state(path=str(cfg.state_path))
        finally:
            browser.close()
    progress(100, "Done")
    return results
