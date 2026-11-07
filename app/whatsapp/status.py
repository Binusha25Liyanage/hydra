"""Is WhatsApp linked? Phase 9 writes linked.json after a successful QR scan."""
from __future__ import annotations

import json

from .. import paths


def status() -> dict:
    marker = paths.whatsapp_profile_dir() / "linked.json"
    if not marker.exists():
        return {"linked": False, "message": "WhatsApp not linked"}
    try:
        info = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return {"linked": False, "message": "WhatsApp link file is damaged — link again"}
    return {"linked": True, "number": info.get("number", ""), "linked_at": info.get("linked_at", ""),
            "message": f"Linked as {info.get('number', 'unknown number')}"}
