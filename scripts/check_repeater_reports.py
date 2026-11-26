"""Check data/repeater_reports.json and data/repeater_ephemerides.json before they are committed.

Run: python scripts/check_repeater_reports.py   (exits with a message if something is wrong)
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPES = {"detection", "non-detection", "burst-storm", "atel"}
NAME = re.compile(r"^20\d{6}[A-Z]{0,2}$")


def main():
    errors = []
    rep = json.loads((ROOT / "data" / "repeater_reports.json").read_text(encoding="utf-8"))
    today = dt.date.today().isoformat()
    seen = set()
    for i, r in enumerate(rep.get("reports", [])):
        w = f"reports[{i}] {r.get('frb')} {r.get('date')}"
        for k in ("frb", "date", "type", "source", "status"):
            if k not in r:
                errors.append(f"{w}: missing '{k}'")
        if not NAME.match(str(r.get("frb", ""))):
            errors.append(f"{w}: frb must look like 20180916B (no 'FRB' prefix)")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(r.get("date", ""))) or str(r.get("date")) > today:
            errors.append(f"{w}: date must be YYYY-MM-DD and not in the future")
        if r.get("type") not in TYPES:
            errors.append(f"{w}: type must be one of {sorted(TYPES)}")
        if r.get("status") not in ("auto", "checked"):
            errors.append(f"{w}: status must be 'auto' or 'checked'")
        src = r.get("source") or {}
        if not (src.get("url") or src.get("arxiv") or src.get("atel")):
            errors.append(f"{w}: source needs a url, an arxiv id or an ATel number")
        key = (r.get("frb"), r.get("date"), r.get("type"), src.get("url"))
        if key in seen:
            errors.append(f"{w}: duplicate report")
        seen.add(key)

    eph = json.loads((ROOT / "data" / "repeater_ephemerides.json").read_text(encoding="utf-8"))
    for e in eph.get("sources", []):
        w = f"ephemeris {e.get('frb')}"
        a, b = (e.get("window") or [None, None])[:2]
        if not (isinstance(e.get("P"), (int, float)) and e["P"] > 0 and isinstance(e.get("P_err"), (int, float))):
            errors.append(f"{w}: P and P_err must be numbers")
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and 0 <= a < b <= 1):
            errors.append(f"{w}: window must be [start, end] phases with 0 <= start < end <= 1")
        if not 40000 < e.get("ref_mjd", 0) < 80000:
            errors.append(f"{w}: ref_mjd looks wrong")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print(f"OK: {len(rep.get('reports', []))} reports, {len(eph.get('sources', []))} ephemerides")


if __name__ == "__main__":
    main()
