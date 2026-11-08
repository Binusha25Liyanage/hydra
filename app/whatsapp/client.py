"""WhatsApp Web through Playwright (one persistent browser profile under %LOCALAPPDATA%\\Hydra\\profiles\\whatsapp).

Playwright objects belong to the thread that made them, so a WAClient is only ever
used from the WhatsApp worker thread (see service.py).
"""
from __future__ import annotations

import base64
import json
import logging
import re
import time
from pathlib import Path

from .. import db, paths, settings

log = logging.getLogger("hydra.whatsapp")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


class WAError(Exception):
    pass


def _sel() -> dict:
    s = dict(settings.DEFAULTS["whatsapp.selectors"])
    s.update(settings.get("whatsapp.selectors") or {})
    return s


def _css_name(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')


class WAClient:
    def __init__(self):
        self._pw = self._ctx = self.page = None
        self.base = (settings.get("whatsapp.url") or "https://web.whatsapp.com").rstrip("/")

    # ------------------------------------------------------------------ browser
    @property
    def open(self) -> bool:
        return self.page is not None and not self.page.is_closed()

    def start(self):
        if self.open:
            return
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        prof = paths.whatsapp_profile_dir() / "browser"
        prof.mkdir(parents=True, exist_ok=True)
        args = dict(headless=bool(settings.get("whatsapp.headless")), user_agent=UA,
                    viewport={"width": 1280, "height": 860}, locale="en-US")
        ch = settings.get("sfa.browser") or "chromium"
        ctx = None
        for channel in ([ch] if ch in ("msedge", "chrome") else []) + [None, "msedge", "chrome"]:
            try:
                ctx = self._pw.chromium.launch_persistent_context(str(prof), **args, **({"channel": channel} if channel else {}))
                break
            except Exception as e:      # that browser is not installed on this PC — try the next
                log.debug("WhatsApp browser %s failed: %s", channel, e)
        if ctx is None:
            self.close()
            raise WAError("No browser available for WhatsApp (install Edge or Chrome)")
        self._ctx = ctx
        self.page = ctx.pages[0] if ctx.pages else ctx.new_page()
        self.page.goto(self.base, wait_until="domcontentloaded", timeout=60000)

    def close(self):
        for obj, fn in ((self._ctx, "close"), (self._pw, "stop")):
            try:
                if obj:
                    getattr(obj, fn)()
            except Exception:
                pass
        self._pw = self._ctx = self.page = None

    # ------------------------------------------------------------------ helpers
    def _first(self, key: str, timeout: float = 0, **fmt):
        """First visible element for any selector in the list `key`; waits up to `timeout` seconds."""
        sels = [s.format(**fmt) if fmt else s for s in _sel()[key]]
        end = time.time() + timeout
        while True:
            for s in sels:
                try:
                    loc = self.page.locator(s).first
                    if loc.count() and loc.is_visible():
                        return loc
                except Exception:
                    continue
            if time.time() >= end:
                return None
            self.page.wait_for_timeout(250)

    def _need(self, key: str, timeout: float, what: str, **fmt):
        loc = self._first(key, timeout, **fmt)
        if loc is None:
            raise WAError(f"{what} not found on WhatsApp Web (selector list '{key}' — WhatsApp may have changed; "
                          f"check Settings → WhatsApp selectors)")
        return loc

    def state(self) -> str:
        """'linked' | 'qr' | 'loading'"""
        if self._first("logged_in"):
            return "linked"
        if self._first("qr"):
            return "qr"
        return "loading"

    def qr_image(self) -> str:
        """The QR code as a PNG data URL (for showing inside Hydra)."""
        loc = self._first("qr")
        if not loc:
            return ""
        try:
            png = loc.screenshot()
        except Exception:
            return ""
        return "data:image/png;base64," + base64.b64encode(png).decode()

    def number(self) -> str:
        try:
            wid = self.page.evaluate("() => localStorage.getItem('last-wid-md') || localStorage.getItem('last-wid') || ''")
            m = re.search(r"(\d{8,15})", wid or "")
            return "+" + m.group(1) if m else ""
        except Exception:
            return ""

    def mark_linked(self):
        marker = paths.whatsapp_profile_dir() / "linked.json"
        marker.write_text(json.dumps({"number": self.number(), "linked_at": db.now_iso()}), encoding="utf-8")

    # ------------------------------------------------------------------ chats
    def open_chat(self, name: str, kind: str = "group", phone: str | None = None):
        if kind == "contact" and phone:
            digits = re.sub(r"\D", "", phone)
            self.page.goto(f"{self.base}/send?phone={digits}", wait_until="domcontentloaded", timeout=60000)
            end = time.time() + 40
            while time.time() < end:
                if self._first("invalid_phone"):
                    raise WAError(f"{phone} is not on WhatsApp")
                if self._first("composer"):
                    return
                self.page.wait_for_timeout(300)
            raise WAError(f"Could not open the chat with {phone}")
        self._need("logged_in", 60, "Chat list")
        box = self._need("search", 15, "Search box")
        box.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Backspace")
        box.type(name, delay=25)
        hit = self._first("chat_title", 15, name=_css_name(name))
        if hit is None:
            raise WAError(f"No chat called “{name}” — check the name matches WhatsApp exactly")
        hit.click()
        self._need("composer", 20, "Message box")

    def _wait_sent(self, before: int, timeout: float):
        """Wait until a new outgoing message exists and nothing is still pending (clock icon)."""
        end = time.time() + timeout
        while time.time() < end:
            outs = self.page.locator("div.message-out").count()
            if outs > before and not self._first("pending"):
                return
            self.page.wait_for_timeout(500)
        raise WAError("WhatsApp did not confirm the message in time (still uploading?)")

    def send_text(self, text: str, timeout: float = 60):
        before = self.page.locator("div.message-out").count()
        box = self._need("composer", 15, "Message box")
        box.click()
        for i, line in enumerate(text.split("\n")):
            if i:
                self.page.keyboard.press("Shift+Enter")
            self.page.keyboard.type(line, delay=5)
        self.page.keyboard.press("Enter")
        self._wait_sent(before, timeout)

    def send_files(self, files: list[str | Path], caption: str = "", timeout: float = 90):
        """Images go as photos (one message, caption on it); anything else goes as a document."""
        files = [Path(f) for f in files]
        missing = [f.name for f in files if not f.exists()]
        if missing:
            raise WAError("File not found: " + ", ".join(missing))
        images = [str(f) for f in files if f.suffix.lower() in IMAGE_EXT]
        docs = [str(f) for f in files if f.suffix.lower() not in IMAGE_EXT]
        groups = ([("media_input", images)] if images else []) + [("document_input", [d]) for d in docs]
        for i, (inp_key, paths_) in enumerate(groups):
            before = self.page.locator("div.message-out").count()
            self._need("attach", 15, "Attach button").click()
            inp = None
            end = time.time() + 10
            while inp is None and time.time() < end:
                for s in _sel()[inp_key]:
                    loc = self.page.locator(s)
                    if loc.count():
                        inp = loc.last
                        break
                if inp is None:
                    self.page.wait_for_timeout(250)
            if inp is None:
                raise WAError("File upload box not found after pressing Attach")
            inp.set_input_files(paths_)
            if caption and i == 0:
                cap = self._need("caption", 20, "Caption box")
                cap.click()
                for j, line in enumerate(caption.split("\n")):
                    if j:
                        self.page.keyboard.press("Shift+Enter")
                    self.page.keyboard.type(line, delay=5)
            else:
                self._need("send", 20, "Send button")
            self._need("send", 20, "Send button").click()
            self._wait_sent(before, timeout)
