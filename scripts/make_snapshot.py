"""Write the static fallback the frontend uses when the API is unreachable.

    python scripts/make_snapshot.py

Runs the real pipeline once (live Open-Meteo fetch -> models -> advisories) and saves:
  frontend/public/snapshot.json             same shape as the API responses + map geometry
  frontend/public/snapshot-advisories.json  every panchayat x crop x stage x language advisory
Regenerated daily by .github/workflows/refresh-snapshot.yml. Nothing here is hand-made:
if the live fetch fails, the script fails and the previous snapshot stays in place.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.advisory import advisory_for  # noqa: E402
from backend.advisory_text import CROPS, LANGS, STAGES  # noqa: E402
from backend.forecast import ForecastService  # noqa: E402
from backend.main import geo, options  # noqa: E402

OUT = ROOT / "frontend" / "public"


def main():
    svc = ForecastService()
    if not svc.refresh():
        raise SystemExit(f"live refresh failed ({svc.last_error}); snapshot NOT updated")
    d = svc.data
    snapshot = {
        **{k: d[k] for k in ("generated_at", "source", "dates", "units", "block", "tiers", "spread", "panchayats")},
        "stale": False, "stale_since": None, "served_from": "snapshot",
        "geo": geo(),
        "validation": json.loads((ROOT / "ml/metrics.json").read_text()),
        "options": options(),
    }
    advisories = {}
    for p in d["panchayats"]:
        for crop in CROPS:
            for stage in STAGES:
                for lang in LANGS:
                    a = advisory_for(p, crop, stage, lang)
                    advisories[f"{p['id']}|{crop}|{stage}|{lang}"] = {
                        k: a[k] for k in ("alerts", "lines", "sms", "sms_chars", "whatsapp", "tier")}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")))
    (OUT / "snapshot-advisories.json").write_text(json.dumps(advisories, ensure_ascii=False, separators=(",", ":")))
    for f in ("snapshot.json", "snapshot-advisories.json"):
        print(f"{f}: {(OUT / f).stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
