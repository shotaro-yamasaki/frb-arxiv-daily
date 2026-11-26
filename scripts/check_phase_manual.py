"""Check scripts/phase_manual.json before it is committed. Exits with an error message if something is wrong.

Run: python scripts/check_phase_manual.py
"""
import json
import re
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parent / "phase_manual.json"
REF_OK = re.compile(r"(arXiv:\d{4}\.\d{4,5})|(\b(19|20)\d{2}\b)")


def main():
    d = json.loads(PATH.read_text(encoding="utf-8"))
    errors = []

    names = set()
    for i, o in enumerate(d.get("lpt", [])):
        w = f"lpt[{i}] {o.get('name')}"
        for k in ("name", "S_min", "S_max", "W_min", "W_max", "nu_GHz", "D_kpc", "detail", "ref"):
            if k not in o:
                errors.append(f"{w}: missing '{k}'")
        if errors:
            continue
        if o["name"] in names:
            errors.append(f"{w}: duplicate name")
        names.add(o["name"])
        checks = [("S_min", 1e-5, 1e4), ("S_max", 1e-5, 1e4), ("W_min", 1e-3, 1e5), ("W_max", 1e-3, 1e5),
                  ("nu_GHz", 0.01, 50), ("D_kpc", 0.001, 100)]
        for k, lo, hi in checks:
            if not isinstance(o[k], (int, float)) or not lo <= o[k] <= hi:
                errors.append(f"{w}: {k}={o[k]!r} outside {lo}..{hi}")
        if o["S_min"] > o["S_max"] or o["W_min"] > o["W_max"]:
            errors.append(f"{w}: min is larger than max")
        if not REF_OK.search(o["ref"]):
            errors.append(f"{w}: ref should include a year or an arXiv id")
        if o.get("status") not in (None, "auto", "checked"):
            errors.append(f"{w}: status must be 'auto' or 'checked'")

    cls_names = set()
    for i, c in enumerate(d.get("he", [])):
        w = f"he[{i}] {c.get('name')}"
        if c.get("name") in cls_names:
            errors.append(f"{w}: duplicate class name")
        cls_names.add(c.get("name"))
        for k in ("name", "cls", "t", "L", "ref"):
            if k not in c:
                errors.append(f"{w}: missing '{k}'")
        t, L = c.get("t", [1, 1]), c.get("L", [1e40, 1e40])
        if not (len(t) == 2 and 1e-6 <= t[0] <= t[1] <= 1e10):
            errors.append(f"{w}: t must be [min, max] seconds within 1e-6..1e10")
        if not (len(L) == 2 and 1e20 <= L[0] <= L[1] <= 1e56):
            errors.append(f"{w}: L must be [min, max] erg/s within 1e20..1e56")
        labels = set()
        for j, p in enumerate(c.get("points", [])):
            pw = f"{w} point[{j}] {p.get('label')}"
            for k in ("x", "y", "label", "ref"):
                if k not in p:
                    errors.append(f"{pw}: missing '{k}'")
            if not (isinstance(p.get("x"), (int, float)) and 1e-6 <= p["x"] <= 1e10):
                errors.append(f"{pw}: x (duration in s) outside 1e-6..1e10")
            if not (isinstance(p.get("y"), (int, float)) and 1e20 <= p["y"] <= 1e56):
                errors.append(f"{pw}: y (luminosity in erg/s) outside 1e20..1e56")
            if p.get("label") in labels:
                errors.append(f"{pw}: duplicate label in this class")
            labels.add(p.get("label"))
            if "ref" in p and not REF_OK.search(p["ref"]):
                errors.append(f"{pw}: ref should include a year or an arXiv id")
            if p.get("status") not in (None, "auto", "checked"):
                errors.append(f"{pw}: status must be 'auto' or 'checked'")

    if errors:
        sys.exit("phase_manual.json has problems:\n  " + "\n  ".join(errors))
    n_pts = sum(len(c.get("points", [])) for c in d.get("he", []))
    print(f"phase_manual.json OK ({len(d.get('lpt', []))} long-period transients, {len(d.get('he', []))} classes, {n_pts} individual objects)")


if __name__ == "__main__":
    main()
