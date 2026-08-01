"""Extract GPS + timestamp from trip photos and build base64 thumbnails.

Uses Pillow + pillow-heif (pure Python) instead of exiftool, so the same code
runs on Windows locally and on Streamlit Community Cloud. Photos without GPS
(screenshots, some exports) are silently skipped — that is expected, not an error.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, asdict
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ExifTags, UnidentifiedImageError

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover - HEIC support is best-effort
    pass

from . import config

THUMB_MAX_PX = 300
THUMB_QUALITY = 70
# A larger "view" image is written as a static file for every geotagged photo,
# powering the click-to-enlarge lightbox in both the gallery and the map popups.
# The map/grid still embed only the small thumb; the full image loads lazily on
# click. Kept at 1000 px so the whole set stays a reasonable size to commit.
LARGE_MAX_PX = 1000
LARGE_QUALITY = 78
IMAGE_SUFFIXES = {".heic", ".heif", ".jpg", ".jpeg", ".png"}


@dataclass
class Photo:
    filename: str
    lat: float
    lon: float
    country: str
    datetime: str | None       # ISO, local time as recorded by the camera
    date: str | None           # YYYY-MM-DD
    thumb_b64: str             # data-URI-ready base64 JPEG
    # Filled in later by the vision-matching step:
    description: str = ""
    matched_spend_id: int | None = None
    match_confidence: str = ""


def _dms_to_deg(dms, ref: str) -> float:
    d, m, s = (float(x) for x in dms)
    val = d + m / 60.0 + s / 3600.0
    return -val if ref in ("S", "W") else val


def _extract_gps(exif) -> tuple[float, float] | None:
    try:
        gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:
        return None
    if not gps:
        return None
    lat = gps.get(2)
    lat_ref = gps.get(1)
    lon = gps.get(4)
    lon_ref = gps.get(3)
    if not (lat and lat_ref and lon and lon_ref):
        return None
    try:
        return _dms_to_deg(lat, lat_ref), _dms_to_deg(lon, lon_ref)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _extract_datetime(exif) -> str | None:
    try:
        exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    except Exception:
        exif_ifd = {}
    raw = exif_ifd.get(ExifTags.Base.DateTimeOriginal) or \
        exif.get(ExifTags.Base.DateTime)
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S").isoformat()
    except ValueError:
        return None


def _encode(img: Image.Image, max_px: int, quality: int) -> str:
    im = img.convert("RGB")
    im.thumbnail((max_px, max_px))
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _make_thumb(img: Image.Image) -> str:
    return _encode(img, THUMB_MAX_PX, THUMB_QUALITY)


def write_full_images(photo_dicts: list[dict], photos_dir=None,
                      out_dir=None, max_px: int = LARGE_MAX_PX,
                      quality: int = LARGE_QUALITY) -> int:
    """Write a larger JPEG for every geotagged photo and record its served path
    in `full_img`.

    These power the click-to-enlarge lightbox in both the gallery and the map
    popups. Serving them as static files (loaded lazily on click) keeps
    photos.json small and the map/grid on the light 300 px thumbnail.
    """
    if photos_dir is None:
        candidates = [p for p in config.RAW_DIR.rglob("Photos") if p.is_dir()]
        if not candidates:
            raise FileNotFoundError(f"No Photos/ folder under {config.RAW_DIR}")
        photos_dir = candidates[0]
    out_dir = Path(out_dir) if out_dir else config.FULL_IMG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    by_name = {p.name: p for p in photos_dir.iterdir()
               if p.suffix.lower() in IMAGE_SUFFIXES}
    n = 0
    for p in photo_dicts:
        p.pop("full_b64", None)  # legacy inline field — never embed
        src = by_name.get(p["filename"])
        if not src:
            p.pop("full_img", None)
            continue
        stem = Path(p["filename"]).stem
        try:
            with Image.open(src) as img:
                im = img.convert("RGB")
                im.thumbnail((max_px, max_px))
                im.save(out_dir / f"{stem}.jpg", format="JPEG", quality=quality)
            p["full_img"] = f"full/{stem}.jpg"
            n += 1
        except (UnidentifiedImageError, OSError):
            continue
    return n


def extract_photos(photos_dir=None) -> list[Photo]:
    """Return one Photo per geotagged image; skip anything without GPS."""
    if photos_dir is None:
        candidates = [p for p in config.RAW_DIR.rglob("Photos") if p.is_dir()]
        if not candidates:
            raise FileNotFoundError(f"No Photos/ folder under {config.RAW_DIR}")
        photos_dir = candidates[0]

    out: list[Photo] = []
    files = sorted(p for p in photos_dir.iterdir()
                   if p.suffix.lower() in IMAGE_SUFFIXES)
    from . import corrections
    for path in files:
        try:
            with Image.open(path) as img:
                exif = img.getexif()
                gps = _extract_gps(exif)
                fix = corrections.PHOTO_CORRECTIONS.get(path.name)
                if gps is None:
                    if not fix:
                        continue  # no location and no manual fix — skip silently
                    lat, lon, country = fix["lat"], fix["lon"], fix["country"]
                else:
                    country = config.country_for_point(*gps)
                    if country is None and not fix:
                        continue  # outside all known trip regions
                    lat, lon = round(gps[0], 6), round(gps[1], 6)
                    if fix:  # correction overrides a bad/stale GPS fix
                        lat, lon, country = fix["lat"], fix["lon"], fix["country"]
                dt = _extract_datetime(exif)
                out.append(Photo(
                    filename=path.name,
                    lat=lat,
                    lon=lon,
                    country=country,
                    datetime=dt,
                    date=dt[:10] if dt else None,
                    thumb_b64=_make_thumb(img),
                ))
        except (UnidentifiedImageError, OSError):
            continue  # unreadable file — skip

    return out


def photos_to_dicts(photos: list[Photo]) -> list[dict]:
    return [asdict(p) for p in photos]


if __name__ == "__main__":
    import collections
    result = extract_photos()
    print(f"Geotagged photos: {len(result)}")
    print("by country:", dict(collections.Counter(p.country for p in result)))
    dated = sum(1 for p in result if p.date)
    print(f"with timestamp: {dated}/{len(result)}")
    if result:
        avg_kb = sum(len(p.thumb_b64) for p in result) / len(result) / 1024
        print(f"avg thumbnail: {avg_kb:.1f} KB base64")
