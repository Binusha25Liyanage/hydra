"""Quick network checks used by the splash screen."""
from __future__ import annotations

import socket
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse


def internet_ok(prefer_url: str = "", timeout: float = 3.0) -> tuple[bool, str]:
    """True when the network is up. Tries the SFA host first (the one that matters)."""
    targets = []
    host = urlparse(prefer_url).hostname if prefer_url else None
    if host:
        targets.append((host, 443 if prefer_url.startswith("https") else 80))
    targets += [("8.8.8.8", 53), ("1.1.1.1", 53)]
    for h, port in targets:
        try:
            with socket.create_connection((h, port), timeout=timeout):
                return True, "Internet connection OK"
        except OSError:
            continue
    return False, "No internet connection"


def reach(url: str, timeout: float = 10.0) -> tuple[bool, str, int]:
    """Is the SFA server answering? Returns (ok, message, latency_ms)."""
    if not url:
        return False, "SFA URL is not set", 0
    host = urlparse(url).hostname or url
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Hydra/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            code = r.status
    except urllib.error.HTTPError as e:   # the server answered, even if with 4xx/5xx
        code = e.code
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        reason = getattr(e, "reason", e)
        return False, f"{host} is not reachable ({reason})", 0
    ms = int((time.perf_counter() - t0) * 1000)
    if code >= 500:
        return False, f"{host} answered with error {code}", ms
    return True, f"{host} reachable · {ms} ms", ms
