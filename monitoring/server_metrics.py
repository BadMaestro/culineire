"""Server health mirror: Linode infrastructure metrics plus local host readings.

Why this exists
---------------
On 2026-07-22 the production disk filled at 03:20, PostgreSQL could not write its
checkpoint, and every page returned 500 for seven and three quarter hours before
anyone noticed. The same fault had already happened on 07-19 and passed unseen.
The only record of it was the Linode dashboard, which lives outside the site and
which nobody was looking at.

Design decisions worth stating, because each of them is a deliberate "no"
------------------------------------------------------------------------
*No database table.* Linode already keeps the last 24 hours; copying that into
Postgres would add write load to a 1 GB single-core box that is already using
swap, to store data we do not own and cannot backfill. The cache is enough.

*No chart library.* This project renders SVG by hand for icons and has no charting
dependency. Adding one for four sparklines would be a new front-end dependency and
a second design language. The charts here are server-rendered polylines.

*No API token in the repo.* The token lives beside the alert credentials in
/srv/culineire/shared/alert.env and is read from the environment. Without it the
page still works and simply says so, exactly like the alert channel does.

*Local readings are not from Linode.* Disk, memory and swap come from the host
itself, because they are the numbers that actually predict the failure above and
Linode's graphs do not show them at all.
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from django.core.cache import cache

LINODE_API = "https://api.linode.com/v4"
CACHE_KEY = "monitoring:linode:stats"
CACHE_SECONDS = 300  # Linode samples every 5 minutes; polling faster buys nothing.
HTTP_TIMEOUT = 12

# Thresholds mirror watchdog.sh so the page and the alarm cannot disagree.
DISK_WARN_PCT = 85
DISK_CRIT_PCT = 92


@dataclass
class Series:
    """One metric line, already reduced to what a chart needs."""

    key: str
    label: str
    unit: str
    points: list[tuple[int, float]] = field(default_factory=list)

    @property
    def values(self) -> list[float]:
        return [v for _, v in self.points]

    @property
    def maximum(self) -> float:
        return max(self.values) if self.values else 0.0

    @property
    def average(self) -> float:
        vals = self.values
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def last(self) -> float:
        return self.values[-1] if self.values else 0.0

    def polyline(self, width: int = 640, height: int = 120) -> str:
        """Render the series as SVG polyline coordinates.

        Scaled against the series maximum rather than a fixed ceiling: CPU on a
        one-core Linode is reported above 100% (steal and iowait are included),
        so a hard 0-100 axis would clip the exact spike worth looking at.
        """
        vals = self.values
        if len(vals) < 2:
            return ""
        top = self.maximum or 1.0
        step = width / (len(vals) - 1)
        coords = []
        for index, value in enumerate(vals):
            x = index * step
            y = height - (value / top) * height
            coords.append(f"{x:.1f},{y:.1f}")
        return " ".join(coords)


def _cache_get():
    """Never let the cache backend break the health page.

    Learned the hard way on 2026-07-22: a single cache file left owned by root
    (written by a diagnostic run as the wrong user) made every request to this
    page raise PermissionError and return 500. The page whose entire job is to
    tell you the server is unhappy must not be the thing that falls over.
    """
    try:
        return cache.get(CACHE_KEY)
    except Exception:  # noqa: BLE001 - a broken cache is not a broken page
        return None


def _cache_set(value, seconds):
    try:
        cache.set(CACHE_KEY, value, seconds)
    except Exception:  # noqa: BLE001
        pass


def _token() -> str:
    return (os.getenv("LINODE_API_TOKEN") or "").strip()


def _linode_id() -> str:
    return (os.getenv("LINODE_INSTANCE_ID") or "").strip()


def _fetch(path: str) -> dict:
    request = urllib.request.Request(
        f"{LINODE_API}{path}",
        headers={
            "Authorization": f"Bearer {_token()}",
            "User-Agent": "culineire-monitoring/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _series_from(raw: list, key: str, label: str, unit: str, scale: float = 1.0) -> Series:
    """Linode returns [[epoch_millis, value], ...]; empty lists are normal."""
    points: list[tuple[int, float]] = []
    for item in raw or []:
        try:
            stamp, value = item[0], item[1]
        except (TypeError, IndexError):
            continue
        if value is None:
            continue
        points.append((int(stamp) // 1000, float(value) * scale))
    return Series(key=key, label=label, unit=unit, points=points)


def linode_metrics(force: bool = False) -> dict:
    """Last 24h of Linode metrics, cached.

    Never raises: a monitoring page that 500s during an incident is worse than a
    monitoring page that says it cannot reach the API right now.
    """
    if not force:
        cached = _cache_get()
        if cached is not None:
            return cached

    if not _token() or not _linode_id():
        result = {
            "configured": False,
            "error": (
                "LINODE_API_TOKEN / LINODE_INSTANCE_ID are not set on the server. "
                "Add them to /srv/culineire/shared/alert.env to switch this on."
            ),
            "series": [],
            "fetched_at": None,
        }
        _cache_set(result, 60)
        return result

    try:
        payload = _fetch(f"/linode/instances/{_linode_id()}/stats")
        data = payload.get("data", {})
        cpu = data.get("cpu", [])
        io = (data.get("io") or {}).get("io", [])
        swap = (data.get("io") or {}).get("swap", [])
        net_in = (data.get("netv4") or {}).get("in", [])
        net_out = (data.get("netv4") or {}).get("out", [])

        series = [
            _series_from(cpu, "cpu", "CPU", "%"),
            _series_from(io, "io", "Disk I/O", "blocks/s"),
            _series_from(swap, "swap", "Swap rate", "blocks/s"),
            # Linode reports network in bits/s; kbit/s is what its own panel shows.
            _series_from(net_in, "net_in", "Network in", "kbit/s", scale=1 / 1000),
            _series_from(net_out, "net_out", "Network out", "kbit/s", scale=1 / 1000),
        ]
        result = {
            "configured": True,
            "error": "",
            "series": series,
            "fetched_at": datetime.now(timezone.utc),
        }
    except urllib.error.HTTPError as exc:
        detail = "token rejected (check it is read-only and not expired)" if exc.code in (401, 403) else f"HTTP {exc.code}"
        result = {"configured": True, "error": f"Linode API: {detail}", "series": [], "fetched_at": None}
    except Exception as exc:  # noqa: BLE001 - never let the health page be the outage
        result = {"configured": True, "error": f"Linode API unreachable: {exc}", "series": [], "fetched_at": None}

    _cache_set(result, CACHE_SECONDS)
    return result


def _read_meminfo() -> dict:
    values: dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                name, _, rest = line.partition(":")
                values[name.strip()] = int(rest.strip().split()[0])
    except (OSError, ValueError, IndexError):
        return {}
    return values


def host_metrics() -> dict:
    """Disk, memory and swap read from this host.

    Linode's panel does not show any of these, and they are precisely what
    predicted the 22 July outage: the disk hit 100% and PostgreSQL died four
    minutes later.
    """
    result: dict = {"available": True, "error": ""}

    try:
        usage = shutil.disk_usage("/")
        used_pct = round(usage.used / usage.total * 100, 1) if usage.total else 0.0
        result["disk"] = {
            "total_gb": round(usage.total / 1024 ** 3, 1),
            "used_gb": round(usage.used / 1024 ** 3, 1),
            "free_gb": round(usage.free / 1024 ** 3, 1),
            "used_pct": used_pct,
            "state": "critical" if used_pct >= DISK_CRIT_PCT else "warning" if used_pct >= DISK_WARN_PCT else "ok",
        }
    except OSError as exc:
        result["disk"] = None
        result["error"] = f"disk unreadable: {exc}"

    mem = _read_meminfo()
    if mem:
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", 0)
        swap_total = mem.get("SwapTotal", 0)
        swap_free = mem.get("SwapFree", 0)
        swap_used = swap_total - swap_free
        result["memory"] = {
            "total_mb": total // 1024,
            "available_mb": available // 1024,
            "used_mb": (total - available) // 1024,
            "used_pct": round((total - available) / total * 100, 1) if total else 0.0,
        }
        result["swap"] = {
            "total_mb": swap_total // 1024,
            "used_mb": swap_used // 1024,
            "used_pct": round(swap_used / swap_total * 100, 1) if swap_total else 0.0,
        }
    else:
        result["memory"] = None
        result["swap"] = None

    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as handle:
            parts = handle.read().split()
        result["load"] = {"one": float(parts[0]), "five": float(parts[1]), "fifteen": float(parts[2])}
    except (OSError, ValueError, IndexError):
        result["load"] = None

    return result
