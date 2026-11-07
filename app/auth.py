"""Hydra users: PBKDF2-SHA256 password hashes, three roles, remember-me tokens.

Roles
  superadmin — everything, including Users & Roles
  admin      — settings, targets, schedules, approve & send
  user       — view reports, Generate Now, approve & send when allowed
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timedelta

from . import db, paths

ROLES = ("superadmin", "admin", "user")
ITERATIONS = 260_000
MAX_FAILED = 5
LOCK_MINUTES = 2
REMEMBER_DAYS = 30
MIN_PASSWORD = 8

_session_lock = threading.Lock()
_current: dict | None = None


class AuthError(Exception):
    pass


def hash_password(password: str, salt: str | None = None, iterations: int = ITERATIONS) -> tuple[str, str, int]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()
    return digest, salt, iterations


def _public(row) -> dict:
    return {
        "id": row["id"], "username": row["username"], "display_name": row["display_name"] or row["username"],
        "role": row["role"], "active": bool(row["active"]), "last_login": row["last_login"],
        "created_at": row["created_at"],
    }


def has_users() -> bool:
    return db.conn().execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


def list_users() -> list[dict]:
    return [_public(r) for r in db.conn().execute("SELECT * FROM users ORDER BY username")]


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Password must be at least {MIN_PASSWORD} characters.")
    if password.isalpha() or password.isdigit():
        raise AuthError("Use letters and numbers (or symbols) in the password.")


def create_user(username: str, password: str, role: str, display_name: str = "", by: str | None = None) -> dict:
    username = (username or "").strip()
    if not username or len(username) < 3:
        raise AuthError("Username must be at least 3 characters.")
    if role not in ROLES:
        raise AuthError("Unknown role.")
    validate_password(password)
    h, salt, it = hash_password(password)
    try:
        db.conn().execute(
            "INSERT INTO users(username, display_name, role, pw_hash, salt, iterations, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (username, display_name.strip() or username, role, h, salt, it, db.now_iso()),
        )
    except Exception as e:
        if "UNIQUE" in str(e):
            raise AuthError("That username already exists.") from e
        raise
    db.audit(by or username, "user.create", f"{username} ({role})")
    row = db.conn().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return _public(row)


def create_first_admin(username: str, password: str, display_name: str = "") -> dict:
    if has_users():
        raise AuthError("An administrator already exists. Please sign in.")
    return create_user(username, password, "superadmin", display_name)


def verify(username: str, password: str) -> dict:
    c = db.conn()
    row = c.execute("SELECT * FROM users WHERE username=?", ((username or "").strip(),)).fetchone()
    if row is None or not row["active"]:
        raise AuthError("Incorrect username or password.")
    if row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > datetime.now():
        raise AuthError(f"Too many attempts. Try again in {LOCK_MINUTES} minutes.")
    digest, _, _ = hash_password(password, row["salt"], row["iterations"])
    if not hmac.compare_digest(digest, row["pw_hash"]):
        failed = row["failed_count"] + 1
        locked = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds") \
            if failed >= MAX_FAILED else None
        c.execute("UPDATE users SET failed_count=?, locked_until=? WHERE id=?",
                  (0 if locked else failed, locked, row["id"]))
        db.audit(row["username"], "login.failed", "")
        raise AuthError("Incorrect username or password.")
    c.execute("UPDATE users SET failed_count=0, locked_until=NULL, last_login=? WHERE id=?",
              (db.now_iso(), row["id"]))
    db.audit(row["username"], "login.ok", "")
    return _public(c.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone())


# ------------------------------------------------------------- session
def login(username: str, password: str, remember: bool = False) -> dict:
    global _current
    user = verify(username, password)
    with _session_lock:
        _current = user
    if remember:
        _issue_remember_token(user["id"])
    else:
        forget_device()
    return user


def logout() -> None:
    global _current
    with _session_lock:
        if _current:
            db.audit(_current["username"], "logout", "")
        _current = None
    forget_device()


def current() -> dict | None:
    return _current


def require(*roles: str) -> dict:
    u = _current
    if u is None:
        raise AuthError("Please sign in first.")
    if roles and u["role"] not in roles:
        raise AuthError("You do not have permission for this action.")
    return u


def _issue_remember_token(user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    th = hashlib.sha256(token.encode()).hexdigest()
    exp = (datetime.now() + timedelta(days=REMEMBER_DAYS)).isoformat(timespec="seconds")
    c = db.conn()
    c.execute("DELETE FROM remember_tokens WHERE user_id=?", (user_id,))
    c.execute("INSERT INTO remember_tokens(token_hash, user_id, expires_at) VALUES (?,?,?)", (th, user_id, exp))
    paths.remember_token_path().write_text(token, encoding="utf-8")


def forget_device() -> None:
    p = paths.remember_token_path()
    if p.exists():
        token = p.read_text(encoding="utf-8").strip()
        db.conn().execute("DELETE FROM remember_tokens WHERE token_hash=?",
                          (hashlib.sha256(token.encode()).hexdigest(),))
        p.unlink(missing_ok=True)


def auto_login() -> dict | None:
    """Sign in silently with this computer's remember-me token, if valid."""
    global _current
    p = paths.remember_token_path()
    if not p.exists():
        return None
    th = hashlib.sha256(p.read_text(encoding="utf-8").strip().encode()).hexdigest()
    c = db.conn()
    row = c.execute(
        "SELECT u.* , t.expires_at FROM remember_tokens t JOIN users u ON u.id=t.user_id WHERE t.token_hash=?",
        (th,),
    ).fetchone()
    if row is None or not row["active"] or datetime.fromisoformat(row["expires_at"]) < datetime.now():
        forget_device()
        return None
    c.execute("UPDATE users SET last_login=? WHERE id=?", (db.now_iso(), row["id"]))
    db.audit(row["username"], "login.remembered", "")
    with _session_lock:
        _current = _public(row)
    return _current


# ------------------------------------------------------------- admin actions
def change_password(old: str, new: str) -> None:
    u = require()
    verify(u["username"], old)
    validate_password(new)
    h, salt, it = hash_password(new)
    db.conn().execute("UPDATE users SET pw_hash=?, salt=?, iterations=? WHERE id=?", (h, salt, it, u["id"]))
    db.audit(u["username"], "password.change", "")


def reset_password(user_id: int, new: str) -> None:
    admin = require("superadmin")
    validate_password(new)
    h, salt, it = hash_password(new)
    db.conn().execute("UPDATE users SET pw_hash=?, salt=?, iterations=?, failed_count=0, locked_until=NULL "
                      "WHERE id=?", (h, salt, it, user_id))
    db.audit(admin["username"], "password.reset", str(user_id))


def update_user(user_id: int, role: str, active: bool, display_name: str) -> None:
    admin = require("superadmin")
    if role not in ROLES:
        raise AuthError("Unknown role.")
    c = db.conn()
    if admin["id"] == user_id and (role != "superadmin" or not active):
        raise AuthError("You cannot remove your own superadmin access.")
    if role != "superadmin" or not active:
        others = c.execute("SELECT COUNT(*) FROM users WHERE role='superadmin' AND active=1 AND id<>?",
                           (user_id,)).fetchone()[0]
        if others == 0:
            raise AuthError("Hydra needs at least one active superadmin.")
    c.execute("UPDATE users SET role=?, active=?, display_name=? WHERE id=?",
              (role, int(active), display_name.strip(), user_id))
    db.audit(admin["username"], "user.update", f"{user_id} role={role} active={active}")
