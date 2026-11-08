"""WhatsApp service: recipients, which reports go to whom, and the send queue.

One background thread owns the WhatsApp browser. The UI (and later the scheduler)
only puts work in the queue and reads progress, so a send never blocks the window.
"""
from __future__ import annotations

import json
import logging
import queue
import shutil
import threading
import time
import uuid
from pathlib import Path

from .. import db, notify, paths, settings
from .client import WAClient, WAError

log = logging.getLogger("hydra.whatsapp")

IDLE_CLOSE_S = 120        # close the browser after 2 minutes with nothing to do
LINK_TIMEOUT_S = 180


class WAServiceError(Exception):
    pass


# =============================================================================== recipients & routes
def recipients(active_only=False) -> list[dict]:
    q = "SELECT * FROM wa_recipients" + (" WHERE active=1" if active_only else "") + " ORDER BY name COLLATE NOCASE"
    out = [dict(r) for r in db.conn().execute(q)]
    routes = {}
    for r in db.conn().execute("SELECT recipient_id, report_type FROM wa_routes"):
        routes.setdefault(r[0], []).append(r[1])
    for x in out:
        x["reports"] = routes.get(x["id"], [])
    return out


def save_recipient(data: dict, user=None) -> int:
    name = (data.get("name") or "").strip()
    kind = data.get("kind") or "group"
    phone = "".join(ch for ch in str(data.get("phone") or "") if ch.isdigit()) or None
    if not name:
        raise WAServiceError("Enter the group or contact name exactly as it shows in WhatsApp")
    if kind not in ("group", "contact"):
        raise WAServiceError("Choose group or contact")
    if kind == "contact" and phone and len(phone) < 9:
        raise WAServiceError("Phone number looks too short — use the full number with country code, e.g. 94771234567")
    if phone and phone.startswith("0"):
        phone = "94" + phone[1:]          # Sri Lankan local format 077… -> 9477…
    with db.tx() as c:
        dup = c.execute("SELECT id FROM wa_recipients WHERE LOWER(name)=LOWER(?) AND id!=?", (name, int(data.get("id") or 0))).fetchone()
        if dup:
            raise WAServiceError(f"“{name}” is already a recipient")
        if data.get("id"):
            c.execute("UPDATE wa_recipients SET name=?, kind=?, phone=?, active=?, notes=? WHERE id=?",
                      (name, kind, phone, 1 if data.get("active", True) else 0, data.get("notes") or None, int(data["id"])))
            rid = int(data["id"])
        else:
            rid = c.execute("INSERT INTO wa_recipients(name, kind, phone, active, notes, created_at) VALUES (?,?,?,?,?,?)",
                            (name, kind, phone, 1 if data.get("active", True) else 0, data.get("notes") or None, db.now_iso())).lastrowid
    db.audit(user, "whatsapp.recipient", name)
    return rid


def delete_recipient(rid: int, user=None):
    with db.tx() as c:
        r = c.execute("SELECT name FROM wa_recipients WHERE id=?", (int(rid),)).fetchone()
        c.execute("DELETE FROM wa_recipients WHERE id=?", (int(rid),))
    db.audit(user, "whatsapp.recipient_delete", r["name"] if r else str(rid))


def routes() -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for r in db.conn().execute("SELECT report_type, recipient_id FROM wa_routes"):
        out.setdefault(r[0], []).append(r[1])
    return out


def save_routes(mapping: dict[str, list[int]], user=None):
    with db.tx() as c:
        c.execute("DELETE FROM wa_routes")
        for rt, ids in (mapping or {}).items():
            for rid in set(int(i) for i in ids or []):
                c.execute("INSERT INTO wa_routes(report_type, recipient_id) VALUES (?,?)", (rt, rid))
    db.audit(user, "whatsapp.routes", json.dumps(mapping)[:300])


# =============================================================================== queueing
def caption_for(template: str, report: dict) -> str:
    from datetime import date
    try:
        d = date.fromisoformat(report["report_date"]).strftime("%d %b %Y")
    except Exception:
        d = report.get("report_date", "")
    return (template or "{title}").replace("{title}", report.get("title", "")) \
        .replace("{date}", d).replace("{report}", report.get("name", ""))


def files_for(report: dict, fmt: str) -> list[str]:
    pngs = [p for p in report.get("png_paths") or [] if Path(p).exists()]
    pdf = report.get("pdf_path") if report.get("pdf_path") and Path(report["pdf_path"]).exists() else None
    if fmt == "pdf":
        files = [pdf] if pdf else pngs
    elif fmt == "both":
        files = pngs + ([pdf] if pdf else [])
    else:
        files = pngs or ([pdf] if pdf else [])
    if not files and report.get("xlsx_path") and Path(report["xlsx_path"]).exists():
        files = [report["xlsx_path"]]          # last resort: the Excel file as a document
    return files


def queue_reports(report_ids: list[int], fmt: str = "png", caption: str = "{title}",
                  only_recipients: list[int] | None = None, user=None) -> dict:
    """Queue every report for each recipient routed to its report type. Returns {batch, queued, skipped}."""
    from ..reports import engine
    rmap = routes()
    active = {r["id"]: r for r in recipients(active_only=True)}
    batch = uuid.uuid4().hex[:12]
    queued, skipped = 0, []
    with db.tx() as c:
        for rid in report_ids:
            rep = engine.get(int(rid))
            if not rep or rep["status"] in ("failed", "skipped"):
                continue
            targets = [active[i] for i in (only_recipients or rmap.get(rep["report_type"], [])) if i in active]
            if not targets:
                skipped.append(rep["name"])
                continue
            files = files_for(rep, fmt)
            if not files:
                skipped.append(rep["name"] + " (no files)")
                continue
            for t in targets:
                c.execute("INSERT INTO wa_sends(batch, report_id, recipient_id, recipient, files_json, caption, status, created_at, created_by) "
                          "VALUES (?,?,?,?,?,?, 'queued', ?, ?)",
                          (batch, rep["id"], t["id"], t["name"], json.dumps(files), caption_for(caption, rep), db.now_iso(), user))
                queued += 1
            c.execute("UPDATE reports SET status='approved' WHERE id=? AND status IN ('generated','saved','approved')", (rep["id"],))
    db.audit(user, "whatsapp.queue", f"batch {batch}: {queued} message(s)")
    if queued:
        WORKER.kick()
    return {"batch": batch, "queued": queued, "skipped": skipped}


def queue_test(recipient_id: int, user=None) -> dict:
    r = db.conn().execute("SELECT * FROM wa_recipients WHERE id=?", (int(recipient_id),)).fetchone()
    if not r:
        raise WAServiceError("Recipient not found")
    batch = uuid.uuid4().hex[:12]
    db.conn().execute("INSERT INTO wa_sends(batch, recipient_id, recipient, files_json, caption, status, created_at, created_by) "
                      "VALUES (?,?,?, '[]', ?, 'queued', ?, ?)",
                      (batch, r["id"], r["name"], "✅ Hydra test message — reports from Hydra will arrive in this chat.", db.now_iso(), user))
    WORKER.kick()
    return {"batch": batch, "queued": 1, "skipped": []}


def batch_status(batch: str) -> dict:
    rows = [dict(r) for r in db.conn().execute(
        "SELECT s.*, r.title FROM wa_sends s LEFT JOIN reports r ON r.id=s.report_id WHERE batch=? ORDER BY s.id", (batch,))]
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("queued", "sending", "sent", "failed", "cancelled")}
    return {"batch": batch, "items": rows, "counts": counts, "done": not counts["queued"] and not counts["sending"],
            "worker": WORKER.snapshot()}


def history(limit=200) -> list[dict]:
    return [dict(r) for r in db.conn().execute(
        "SELECT s.*, r.title, r.report_type, r.report_date FROM wa_sends s LEFT JOIN reports r ON r.id=s.report_id "
        "ORDER BY s.id DESC LIMIT ?", (limit,))]


def cancel_queued(user=None) -> int:
    n = db.conn().execute("UPDATE wa_sends SET status='cancelled', error='Cancelled by user' WHERE status='queued'").rowcount
    WORKER.stop_event.set()
    db.audit(user, "whatsapp.cancel", f"{n} message(s)")
    return n


def recover():
    """At start-up: anything left 'sending' was interrupted by Hydra closing."""
    db.conn().execute("UPDATE wa_sends SET status='failed', error='Hydra closed while sending' WHERE status='sending'")


def _finish_reports(report_ids: set[int]):
    """A report becomes 'sent' once every message for it in the latest batch went out."""
    c = db.conn()
    for rid in report_ids:
        rows = c.execute("SELECT status FROM wa_sends WHERE report_id=? AND batch=(SELECT batch FROM wa_sends WHERE report_id=? "
                         "ORDER BY id DESC LIMIT 1)", (rid, rid)).fetchall()
        if rows and all(r[0] == "sent" for r in rows):
            c.execute("UPDATE reports SET status='sent' WHERE id=?", (rid,))


# =============================================================================== worker thread
class Worker:
    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.state = {"phase": "idle", "message": "", "qr": "", "current": "", "updated": time.time()}

    # --- called from any thread
    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.state)

    def _set(self, **kw):
        with self._lock:
            self.state.update(kw, updated=time.time())

    def _ensure_thread(self):
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="hydra-whatsapp", daemon=True)
            self._thread.start()

    def kick(self):
        self.stop_event.clear()
        self._ensure_thread()
        self.q.put(("process",))

    def link(self):
        self._ensure_thread()
        self._set(phase="starting", message="Opening WhatsApp Web…", qr="")
        self.q.put(("link",))

    def unlink(self):
        self._ensure_thread()
        self.q.put(("unlink",))

    def shutdown(self):
        self.q.put(("quit",))

    # --- worker thread only
    def _run(self):
        client = WAClient()
        last_work = time.time()
        while True:
            try:
                cmd = self.q.get(timeout=5)
            except queue.Empty:
                if client.open and time.time() - last_work > IDLE_CLOSE_S:
                    client.close()
                    self._set(phase="idle", message="", current="")
                continue
            try:
                if cmd[0] == "quit":
                    client.close()
                    return
                if cmd[0] == "link":
                    self._do_link(client)
                elif cmd[0] == "unlink":
                    client.close()
                    shutil.rmtree(paths.whatsapp_profile_dir() / "browser", ignore_errors=True)
                    (paths.whatsapp_profile_dir() / "linked.json").unlink(missing_ok=True)
                    self._set(phase="idle", message="WhatsApp unlinked", qr="")
                elif cmd[0] == "process":
                    self._do_queue(client)
            except Exception as e:
                log.exception("WhatsApp worker")
                self._set(phase="error", message=str(e), qr="")
                client.close()
            last_work = time.time()

    def _wait_ready(self, client: WAClient, allow_qr: bool, timeout: float) -> str:
        end = time.time() + timeout
        last_qr = 0.0
        while time.time() < end:
            st = client.state()
            if st == "linked":
                return st
            if st == "qr":
                if not allow_qr:
                    return st
                if time.time() - last_qr > 2:          # the QR changes every ~20 s; refresh the picture often
                    self._set(phase="qr", message="Scan this code with WhatsApp on the phone: Settings → Linked devices → Link a device",
                              qr=client.qr_image())
                    last_qr = time.time()
            client.page.wait_for_timeout(500)
        return "timeout"

    def _do_link(self, client: WAClient):
        client.start()
        self._set(phase="loading", message="Loading WhatsApp Web…")
        st = self._wait_ready(client, allow_qr=True, timeout=LINK_TIMEOUT_S)
        if st != "linked":
            client.close()
            self._set(phase="error", message="The QR code was not scanned in time — press Link again", qr="")
            return
        self._set(phase="loading", message="Linked — finishing sync…", qr="")
        client.page.wait_for_timeout(3000)
        client.mark_linked()
        num = client.number()
        self._set(phase="linked", message=f"Linked{' as ' + num if num else ''}", qr="")
        notify.add("whatsapp", "success", "WhatsApp linked", num or "", "whatsapp")
        db.audit(None, "whatsapp.linked", num)

    def _do_queue(self, client: WAClient):
        c = db.conn()
        if not c.execute("SELECT 1 FROM wa_sends WHERE status='queued'").fetchone():
            return
        self._set(phase="starting", message="Opening WhatsApp Web…", current="")
        client.start()
        st = self._wait_ready(client, allow_qr=False, timeout=90)
        if st != "linked":
            (paths.whatsapp_profile_dir() / "linked.json").unlink(missing_ok=True)
            msg = "WhatsApp is not linked — open the WhatsApp screen and scan the QR code" if st == "qr" else \
                "WhatsApp Web did not load in time"
            n = c.execute("UPDATE wa_sends SET status='failed', error=? WHERE status='queued'", (msg,)).rowcount
            self._set(phase="error", message=msg)
            notify.add("whatsapp", "error", f"{n} WhatsApp message(s) not sent", msg, "whatsapp")
            client.close()
            return
        client.mark_linked()
        sent = failed = 0
        touched: set[int] = set()
        timeout = float(settings.get("whatsapp.send_timeout_s") or 90)
        gap = float(settings.get("whatsapp.gap_s") or 0)
        open_chat = None
        while not self.stop_event.is_set():
            row = c.execute("SELECT s.*, w.kind, w.phone FROM wa_sends s LEFT JOIN wa_recipients w ON w.id=s.recipient_id "
                            "WHERE s.status='queued' ORDER BY s.recipient, s.id LIMIT 1").fetchone()
            if not row:
                break
            c.execute("UPDATE wa_sends SET status='sending' WHERE id=?", (row["id"],))
            label = row["recipient"]
            self._set(phase="sending", message=f"Sending to {label}", current=label)
            try:
                if open_chat != row["recipient"]:
                    client.open_chat(row["recipient"], row["kind"] or "group", row["phone"])
                    open_chat = row["recipient"]
                files = json.loads(row["files_json"] or "[]")
                if files:
                    client.send_files(files, row["caption"] or "", timeout)
                else:
                    client.send_text(row["caption"] or "", timeout)
                c.execute("UPDATE wa_sends SET status='sent', sent_at=?, error=NULL WHERE id=?", (db.now_iso(), row["id"]))
                sent += 1
                log.info("WhatsApp sent to %s (%d file(s))", label, len(files))
            except Exception as e:
                failed += 1
                open_chat = None
                err = str(e) if isinstance(e, WAError) else f"{type(e).__name__}: {e}"
                c.execute("UPDATE wa_sends SET status='failed', error=? WHERE id=?", (err[:500], row["id"]))
                log.warning("WhatsApp to %s failed: %s", label, err)
                try:     # get back to a clean page for the next message
                    client.page.keyboard.press("Escape")
                    client.page.goto(client.base, wait_until="domcontentloaded", timeout=60000)
                    self._wait_ready(client, allow_qr=False, timeout=60)
                except Exception:
                    client.close()
                    client.start()
            if row["report_id"]:
                touched.add(row["report_id"])
            if gap:
                time.sleep(gap)
        if self.stop_event.is_set():
            c.execute("UPDATE wa_sends SET status='cancelled', error='Cancelled by user' WHERE status='queued'")
        _finish_reports(touched)
        self._set(phase="linked", message=f"Done — {sent} sent" + (f", {failed} failed" if failed else ""), current="")
        if sent or failed:
            notify.add("whatsapp", "error" if failed else "success",
                       f"WhatsApp: {sent} message(s) sent" + (f", {failed} failed" if failed else ""), "", "whatsapp")


WORKER = Worker()
