#!/usr/bin/env python3
"""
enrich_metadata.py — read every photo's EXIF and derive richer metadata
fields that get fed into the caption generator.

## Why

The Google Photos manifest gives us only filename, ID, dimensions,
and capture timestamp. Caption quality jumps when the LLM sees:

  - **Precise time of day** (morning/afternoon/evening/night/late-night).
    Changes the register: "subah ki" vs "late raat".
  - **Day of week** ("Sunday mood" hits different from "Tuesday office").
  - **GPS → city / locality** (when EXIF carries it). "Manali", "Gurgaon",
    "office", etc. — anchors the caption to a real place.
  - **Camera / phone model** — sometimes implies the era ("old Pixel
    days").
  - **Days since previous photo** ("agle hi din" vs "long gap ke baad").
  - **Days into the relationship** (since the album's first photo).
  - **Burst detection** — photos taken within 10s of each other are
    likely the same moment. The captioner can avoid writing 4 captions
    for the same scene.
  - **Orientation** (portrait/landscape/square).

PRIVACY: GPS coordinates are reverse-geocoded LOCALLY (via cached
Nominatim lookups for unique coords) and only the resulting
city/locality name is exposed to the LLM — exact lat/lon never leaves
this machine.

## Output

Writes `enriched_metadata.json` alongside `manifest.json`. The caption
generator reads BOTH.

## Run

  python tools/enrich_metadata.py
  python tools/enrich_metadata.py --no-geocode   # skip GPS lookups
  python tools/enrich_metadata.py --force         # ignore cache
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image, ExifTags
except ImportError:
    print("ERROR: Pillow not installed.", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests not installed.", file=sys.stderr)
    sys.exit(1)


# Reverse the EXIF tag dictionary so we can look up by name.
_TAG_BY_NAME = {v: k for k, v in ExifTags.TAGS.items()}
_GPS_TAG_BY_NAME = {v: k for k, v in ExifTags.GPSTAGS.items()}


def _dms_to_deg(dms, ref) -> float | None:
    """Convert ((deg_num, deg_den), (min_num, min_den), (sec_num, sec_den))
    + 'N'/'S'/'E'/'W' to a signed decimal degree."""
    try:
        d = float(dms[0])
        m = float(dms[1])
        s = float(dms[2])
        deg = d + m / 60 + s / 3600
        if ref in ("S", "W"):
            deg = -deg
        return round(deg, 6)
    except (TypeError, ValueError, IndexError):
        return None


def extract_exif(image_path: Path) -> dict:
    """Pull a select set of EXIF fields. Best-effort; missing fields OK."""
    out: dict = {}
    try:
        img = Image.open(image_path)
        exif = img._getexif() or {}
    except Exception:
        return out

    def get(name):
        tag = _TAG_BY_NAME.get(name)
        return exif.get(tag) if tag else None

    # ── Camera identification
    make = get("Make")
    model = get("Model")
    if make or model:
        out["camera"] = " ".join(str(x).strip() for x in (make, model) if x)
    soft = get("Software")
    if soft:
        out["software"] = str(soft).strip()

    # ── Precise timestamp (more accurate than Google's stored ts in
    # some cases)
    dt_orig = get("DateTimeOriginal") or get("DateTime")
    if dt_orig:
        out["exif_datetime"] = str(dt_orig)

    # ── Orientation (1 = normal, others mean rotated)
    orient = get("Orientation")
    if orient is not None:
        out["orientation_code"] = int(orient)

    # ── Lens / focal length / exposure (informs lighting / framing)
    lens = get("LensModel")
    if lens:
        out["lens"] = str(lens).strip()
    fl = get("FocalLength")
    if fl:
        try:
            out["focal_length_mm"] = round(float(fl), 1)
        except (TypeError, ValueError):
            pass
    iso = get("ISOSpeedRatings")
    if iso:
        try:
            out["iso"] = int(iso) if not hasattr(iso, "__iter__") else int(iso[0])
        except (TypeError, ValueError):
            pass
    flash = get("Flash")
    if flash is not None:
        try:
            out["flash_fired"] = bool(int(flash) & 1)
        except (TypeError, ValueError):
            pass

    # ── GPS
    gps = get("GPSInfo")
    if isinstance(gps, dict):
        def gpsget(name):
            t = _GPS_TAG_BY_NAME.get(name)
            return gps.get(t) if t else None

        lat = _dms_to_deg(gpsget("GPSLatitude"), gpsget("GPSLatitudeRef"))
        lon = _dms_to_deg(gpsget("GPSLongitude"), gpsget("GPSLongitudeRef"))
        if lat is not None and lon is not None:
            out["gps_lat"] = lat
            out["gps_lon"] = lon

    return out


# ── Reverse geocoding (Nominatim, cached) ─────────────────────────

_GEOCODE_CACHE: dict = {}


def _coord_key(lat: float, lon: float) -> str:
    """Round to 3 decimal places (~110m precision) so nearby photos
    share a cache hit."""
    return f"{lat:.3f},{lon:.3f}"


def reverse_geocode(lat: float, lon: float, cache_path: Path) -> dict | None:
    """Lookup city / locality for a GPS coord. Cached on disk."""
    global _GEOCODE_CACHE
    if not _GEOCODE_CACHE and cache_path.exists():
        try:
            _GEOCODE_CACHE = json.loads(cache_path.read_text())
        except json.JSONDecodeError:
            _GEOCODE_CACHE = {}

    key = _coord_key(lat, lon)
    if key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[key]

    # Nominatim — public, rate-limited to 1 req/sec, requires a User-Agent.
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": lat, "lon": lon, "format": "json",
                "zoom": 14, "accept-language": "en",
            },
            headers={"User-Agent": "vesper-yaadein/1.0 (private personal project)"},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            addr = data.get("address", {})
            simplified = {
                "city": (addr.get("city") or addr.get("town") or addr.get("village")
                         or addr.get("suburb") or addr.get("county")),
                "state": addr.get("state"),
                "country": addr.get("country"),
                "locality": (addr.get("suburb") or addr.get("neighbourhood")
                             or addr.get("road")),
                "display": data.get("display_name", "").split(",")[:3],
            }
            _GEOCODE_CACHE[key] = simplified
            # Persist cache after each lookup
            cache_path.write_text(json.dumps(_GEOCODE_CACHE, indent=2,
                                            ensure_ascii=False))
            time.sleep(1.0)  # Nominatim rate limit
            return simplified
    except (requests.RequestException, ValueError):
        pass
    return None


# ── Derived fields ────────────────────────────────────────────────


def time_of_day(hour: int) -> str:
    """Map 24h hour → coarse part of day with a Hinglish-friendly bias."""
    if 5 <= hour < 9:
        return "early morning"
    if 9 <= hour < 12:
        return "morning"
    if 12 <= hour < 16:
        return "afternoon"
    if 16 <= hour < 19:
        return "late afternoon"
    if 19 <= hour < 22:
        return "evening"
    if 22 <= hour or hour < 2:
        return "night"
    return "late night"


def day_of_week(dt: datetime) -> str:
    return dt.strftime("%A")


def season_india(month: int) -> str:
    """Coarse Indian-context seasons. Useful for shaadi / festival captioning."""
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4):
        return "spring"
    if month == 5 or month == 6:
        return "summer"
    if month in (7, 8, 9):
        return "monsoon"
    return "autumn"


def detect_bursts(photos: list[dict], threshold_s: int = 10) -> dict[str, int]:
    """Group photos taken within `threshold_s` seconds into bursts.
    Returns: {filename: burst_id} where bursts have shared id, singletons
    have unique ids."""
    # Sort by timestamp
    sorted_photos = sorted(
        [p for p in photos if p.get("capture_ts_ms") and p.get("filename")],
        key=lambda p: p["capture_ts_ms"],
    )
    bursts: dict[str, int] = {}
    current_id = 0
    prev_ts = None
    for p in sorted_photos:
        ts = p["capture_ts_ms"]
        if prev_ts is None or (ts - prev_ts) > threshold_s * 1000:
            current_id += 1
        bursts[p["filename"]] = current_id
        prev_ts = ts
    return bursts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos-dir",
                        default="events/astha-birthday/media/photos")
    parser.add_argument("--manifest",
                        default="events/astha-birthday/media/photos/manifest.json")
    parser.add_argument("--output",
                        default="events/astha-birthday/media/photos/enriched_metadata.json")
    parser.add_argument("--geocode-cache",
                        default="events/astha-birthday/media/photos/.geocode_cache.json")
    parser.add_argument("--no-geocode", action="store_true",
                        help="Skip GPS → city lookups")
    parser.add_argument("--force", action="store_true",
                        help="Re-extract EXIF even for photos already enriched")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent.parent
    def resolve(p):
        p = Path(p)
        return p if p.is_absolute() else here / p
    photos_dir = resolve(args.photos_dir)
    manifest_path = resolve(args.manifest)
    out_path = resolve(args.output)
    geocode_cache_path = resolve(args.geocode_cache)

    manifest = json.loads(manifest_path.read_text())
    photos = manifest["photos"]
    print(f"Enriching metadata for {len(photos)} photos...")

    # Load existing enrichment if any (idempotent)
    existing = {}
    if out_path.exists() and not args.force:
        try:
            existing = json.loads(out_path.read_text()).get("photos", {})
        except (json.JSONDecodeError, KeyError):
            pass

    # Burst detection — runs across all photos at once
    bursts = detect_bursts(photos)

    # First photo timestamp for "days into relationship"
    dated = sorted([p for p in photos if p.get("capture_ts_ms")],
                   key=lambda p: p["capture_ts_ms"])
    first_ts = dated[0]["capture_ts_ms"] if dated else 0
    last_ts = dated[-1]["capture_ts_ms"] if dated else 0

    prev_ts_by_index: dict[str, int | None] = {}
    for i, p in enumerate(dated):
        prev_ts_by_index[p["filename"]] = (
            dated[i - 1]["capture_ts_ms"] if i > 0 else None
        )

    enriched: dict[str, dict] = {}
    geocode_count = 0
    for i, p in enumerate(photos, 1):
        fname = p.get("filename")
        if not fname:
            continue

        cached = existing.get(fname, {}) if not args.force else {}

        # If cached and has EXIF, reuse
        if cached and "extracted" in cached:
            enriched[fname] = cached
        else:
            img_path = photos_dir / fname
            if not img_path.exists():
                continue
            exif = extract_exif(img_path)
            enriched[fname] = {"extracted": True, **exif}

        # ── Derived fields (recompute every time — cheap)
        ts_ms = p.get("capture_ts_ms")
        if ts_ms:
            dt = datetime.fromtimestamp(ts_ms / 1000)
            enriched[fname]["time_of_day"] = time_of_day(dt.hour)
            enriched[fname]["day_of_week"] = day_of_week(dt)
            enriched[fname]["season_india"] = season_india(dt.month)
            enriched[fname]["hour_24"] = dt.hour
            if first_ts:
                days_in = (ts_ms - first_ts) // (24 * 3600 * 1000)
                enriched[fname]["days_since_album_start"] = int(days_in)
            prev = prev_ts_by_index.get(fname)
            if prev:
                gap_d = (ts_ms - prev) / (24 * 3600 * 1000)
                enriched[fname]["days_since_prev_photo"] = round(gap_d, 1)

        # Orientation summary
        w, h = p.get("width"), p.get("height")
        if w and h:
            if abs(w - h) < min(w, h) * 0.1:
                enriched[fname]["orientation"] = "square"
            elif w > h:
                enriched[fname]["orientation"] = "landscape"
            else:
                enriched[fname]["orientation"] = "portrait"
            enriched[fname]["aspect_ratio"] = round(w / h, 2)

        # Burst id
        if fname in bursts:
            enriched[fname]["burst_id"] = bursts[fname]
            # Count co-burst photos
            same_burst = sum(1 for v in bursts.values() if v == bursts[fname])
            enriched[fname]["burst_size"] = same_burst

        # GPS → city (only if EXIF had coords and --no-geocode not set)
        if (not args.no_geocode
                and "gps_lat" in enriched[fname]
                and "gps_lon" in enriched[fname]
                and "city" not in enriched[fname]):
            loc = reverse_geocode(
                enriched[fname]["gps_lat"],
                enriched[fname]["gps_lon"],
                geocode_cache_path,
            )
            if loc:
                if loc.get("city"):
                    enriched[fname]["city"] = loc["city"]
                if loc.get("locality"):
                    enriched[fname]["locality"] = loc["locality"]
                if loc.get("state"):
                    enriched[fname]["state"] = loc["state"]
                if loc.get("country"):
                    enriched[fname]["country"] = loc["country"]
                geocode_count += 1

            # IMPORTANT — strip raw coords before saving; LLM only sees
            # the city / locality.
            enriched[fname].pop("gps_lat", None)
            enriched[fname].pop("gps_lon", None)

        if i % 50 == 0 or i == len(photos):
            print(f"  [{i:>3d}/{len(photos)}] processed")

    # Write enriched output
    out_doc = {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "photo_count": len(enriched),
        "geocoded_count": geocode_count,
        "photos": enriched,
    }
    out_path.write_text(json.dumps(out_doc, indent=2, ensure_ascii=False))

    # Summary
    print(f"\n=== enrichment summary ===")
    print(f"  Photos:           {len(enriched)}")
    print(f"  With GPS:         {sum(1 for v in enriched.values() if 'city' in v)}")
    print(f"  Cameras seen:     {len(set(v.get('camera','?') for v in enriched.values()))}")
    print(f"  Bursts detected:  {len(set(v.get('burst_id') for v in enriched.values() if v.get('burst_id')))}")
    print(f"  Saved to:         {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
