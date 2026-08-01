"""Curated notable landmarks, validated against where the trip data actually is.

The on-device Timeline export doesn't carry place *names* (only generic
semantic types), so named landmarks are curated by hand from the trip evidence
(spending log + known coordinates). Each candidate is then kept only if real
photo or route points fall near it — so a marker never lands somewhere the trip
data doesn't support — and annotated with how many photos were taken nearby,
which surfaces the frequently-visited spots.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from math import radians, sin, cos, asin, sqrt

from . import config

# (name, lat, lon, country, kind) — kind drives the marker emoji.
CANDIDATES = [
    # Osaka, Japan
    ("Osaka Castle", 34.6873, 135.5259, "Japan", "castle"),
    ("Osaka Aquarium Kaiyukan", 34.6545, 135.4288, "Japan", "aquarium"),
    ("Universal Studios Japan", 34.6656, 135.4323, "Japan", "park"),
    ("Dotonbori", 34.6686, 135.5030, "Japan", "food"),
    ("Shinsaibashi", 34.6723, 135.5010, "Japan", "shopping"),
    ("Tsutenkaku / Shinsekai", 34.6524, 135.5063, "Japan", "landmark"),
    # Bangkok + Pattaya, Thailand
    ("Terminal 21 Asok", 13.7376, 100.5601, "Thailand", "shopping"),
    ("Siam Paragon", 13.7462, 100.5347, "Thailand", "shopping"),
    ("CentralWorld", 13.7466, 100.5396, "Thailand", "shopping"),
    ("EmSphere", 13.7297, 100.5697, "Thailand", "shopping"),
    ("IconSiam", 13.7266, 100.5100, "Thailand", "shopping"),
    ("Chatuchak Weekend Market", 13.7999, 100.5502, "Thailand", "market"),
    ("Pattaya Floating Market", 12.8892, 100.9007, "Thailand", "market"),
    ("Pattaya Beach", 12.9270, 100.8776, "Thailand", "beach"),
]

KEEP_KM = 2.0     # a landmark must have a data point within this radius
NEARBY_KM = 0.35  # photos within this radius count as "visited here"


@dataclass
class Landmark:
    name: str
    lat: float
    lon: float
    country: str
    kind: str
    nearest_km: float
    photos_nearby: int


def _haversine(a_lat, a_lon, b_lat, b_lon) -> float:
    r = 6371.0
    dlat = radians(b_lat - a_lat)
    dlon = radians(b_lon - a_lon)
    h = (sin(dlat / 2) ** 2
         + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(dlon / 2) ** 2)
    return 2 * r * asin(sqrt(h))


def build_landmarks() -> list[dict]:
    photos = json.loads(config.PHOTOS_JSON.read_text(encoding="utf-8"))
    route = json.loads(config.ROUTE_JSON.read_text(encoding="utf-8"))

    photo_pts = [(p["lat"], p["lon"]) for p in photos]
    route_pts = [tuple(pt) for pts in route.get("routes", {}).values()
                 for pt in pts]
    all_pts = photo_pts + route_pts

    kept: list[Landmark] = []
    for name, lat, lon, country, kind in CANDIDATES:
        if not all_pts:
            break
        nearest = min(_haversine(lat, lon, plat, plon) for plat, plon in all_pts)
        if nearest > KEEP_KM:
            continue
        nearby = sum(1 for plat, plon in photo_pts
                     if _haversine(lat, lon, plat, plon) <= NEARBY_KM)
        kept.append(Landmark(name, lat, lon, country, kind,
                             round(nearest, 3), nearby))

    kept.sort(key=lambda l: l.photos_nearby, reverse=True)
    return [asdict(l) for l in kept]


def write_landmarks() -> list[dict]:
    data = build_landmarks()
    (config.PROCESSED_DIR / "landmarks.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8")
    return data


if __name__ == "__main__":
    for lm in write_landmarks():
        print(f"  {lm['country']:>8}  {lm['name']:<28} "
              f"{lm['photos_nearby']:>3} photos  ({lm['nearest_km']} km)")
