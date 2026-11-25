"""Check docs/data/hosts_lit.json before it is committed. Exits with an error message if something is wrong.

Run: python scripts/check_hosts_lit.py
"""
import json
import re
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "docs" / "data" / "hosts_lit.json"

RANGES = {  # field: (min, max)
    "z": (0, 6), "ra": (0, 360), "dec": (-90, 90), "dm": (0, 10000),
    "log_mstar": (5, 13), "log_mstar_lo": (0, 3), "log_mstar_up": (0, 3),
    "sfr": (0, 3000), "sfr_lo": (0, 3000), "sfr_up": (0, 3000),
    "offset_kpc": (0, 500), "offset_kpc_err": (0, 500), "offset_arcsec": (0, 600),
    "z_gas": (6, 10), "p_ox": (0, 1),
}
TEXT = {"mstar_kind", "sfr_kind", "morphology", "notes", "added", "status", "z_type"}
ALLOWED = set(RANGES) | TEXT | {"frb", "repeater", "source"}


def main():
    d = json.loads(PATH.read_text(encoding="utf-8"))
    errors = []
    seen = set()
    for i, e in enumerate(d.get("entries", [])):
        where = f"entry {i} ({e.get('frb')})"
        if not re.fullmatch(r"\d{8}[A-Z]{0,3}", str(e.get("frb", ""))):
            errors.append(f"{where}: frb must look like 20240114A (no 'FRB' prefix)")
        for k, v in e.items():
            if k not in ALLOWED:
                errors.append(f"{where}: unknown field '{k}'")
            elif k in RANGES and v is not None:
                lo, hi = RANGES[k]
                if not isinstance(v, (int, float)) or not lo <= v <= hi:
                    errors.append(f"{where}: {k}={v!r} is outside {lo}..{hi}")
        if "repeater" in e and e["repeater"] not in (True, False, None):
            errors.append(f"{where}: repeater must be true, false or null")
        src = e.get("source") or {}
        if not (src.get("arxiv") or src.get("doi") or src.get("url")):
            errors.append(f"{where}: source needs arxiv, doi or url")
        if src.get("arxiv") and not re.fullmatch(r"\d{4}\.\d{4,5}", src["arxiv"]):
            errors.append(f"{where}: source.arxiv should look like 2611.01234")
        if e.get("status") not in ("auto", "checked"):
            errors.append(f"{where}: status must be 'auto' or 'checked'")
        key = (e.get("frb"), src.get("arxiv") or src.get("doi") or src.get("url"))
        if key in seen:
            errors.append(f"{where}: duplicate of an earlier entry from the same paper")
        seen.add(key)
    if errors:
        sys.exit("hosts_lit.json has problems:\n  " + "\n  ".join(errors))
    print(f"hosts_lit.json OK ({len(d.get('entries', []))} entries)")


if __name__ == "__main__":
    main()
