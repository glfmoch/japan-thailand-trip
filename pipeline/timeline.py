"""Parse a Google Maps Timeline JSON export into a movement route.

Handles the newer on-device export format: a flat list of time-ordered
segments, each of which is a ``visit``, an ``activity`` (movement between two
points), or a ``timelinePath`` (a list of intermediate points). Location is
encoded as ``geo:lat,lng`` strings.

Japan Timeline data is sparse/absent (no SIM there), so the primary output is
the Thailand route. Missing Japan data is expected, not an error.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from . import config

GEO_RE = re.compile(r"geo:([-\d.]+),([-\d.]+)")


def _parse_time(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _geo(s: str | None):
    if not s:
        return None
    m = GEO_RE.search(s)
    return (float(m.group(1)), float(m.group(2))) if m else None


def _load(json_path=None) -> list:
    if json_path is None:
        matches = list(config.RAW_DIR.rglob("*Google Maps*.json"))
        if not matches:
            raise FileNotFoundError(
                f"No Timeline JSON found under {config.RAW_DIR}"
            )
        json_path = matches[0]
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def _timed_points(segments: list) -> list[tuple[datetime, float, float]]:
    """Flatten all segments into (time, lat, lon) points, best-effort."""
    points: list[tuple[datetime, float, float]] = []
    for seg in segments:
        start = _parse_time(seg.get("startTime", ""))
        if start is None:
            continue

        if "visit" in seg:
            loc = _geo(seg["visit"].get("topCandidate", {}).get("placeLocation"))
            if loc:
                points.append((start, loc[0], loc[1]))

        elif "activity" in seg:
            for key in ("start", "end"):
                loc = _geo(seg["activity"].get(key))
                if loc:
                    points.append((start, loc[0], loc[1]))

        elif "timelinePath" in seg:
            for p in seg["timelinePath"]:
                loc = _geo(p.get("point"))
                if loc:
                    points.append((start, loc[0], loc[1]))

    points.sort(key=lambda t: t[0])
    return points


def build_routes(json_path=None) -> dict:
    """Return per-country ordered routes plus visit markers.

    Output shape:
        {
          "routes": {"Thailand": [[lat, lon], ...], "Japan": [...]},
          "visits": {"Thailand": [{"lat","lon","start","name"}], ...},
          "counts": {"Thailand": n, "Japan": n},
        }
    """
    segments = _load(json_path)
    points = _timed_points(segments)

    routes: dict[str, list[list[float]]] = {}
    counts: dict[str, int] = {}
    for _, lat, lon in points:
        country = config.country_for_point(lat, lon)
        if country is None:
            continue
        routes.setdefault(country, [])
        # De-duplicate consecutive identical points to keep the polyline lean.
        if not routes[country] or routes[country][-1] != [lat, lon]:
            routes[country].append([round(lat, 6), round(lon, 6)])
        counts[country] = counts.get(country, 0) + 1

    visits: dict[str, list[dict]] = {}
    for seg in segments:
        if "visit" not in seg:
            continue
        cand = seg["visit"].get("topCandidate", {})
        loc = _geo(cand.get("placeLocation"))
        if not loc:
            continue
        country = config.country_for_point(*loc)
        if country is None:
            continue
        visits.setdefault(country, []).append({
            "lat": round(loc[0], 6),
            "lon": round(loc[1], 6),
            "start": seg.get("startTime", ""),
            "semantic_type": cand.get("semanticType", ""),
        })

    return {"routes": routes, "visits": visits, "counts": counts}


if __name__ == "__main__":
    data = build_routes()
    for country, pts in data["routes"].items():
        print(f"{country}: {len(pts)} route points, "
              f"{len(data['visits'].get(country, []))} visits "
              f"({data['counts'][country]} raw points)")
