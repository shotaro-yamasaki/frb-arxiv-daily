"""Build docs/data/repeaters.json for the repeater activity page (docs/repeaters.html).

Inputs (all in this repository, no downloads):
  data/chimefrbcat2.csv            CHIME/FRB Catalog 2: repeaters, positions, DMs, burst times (to 2023-09-15)
  docs/data/hosts_base.json        localized FRBs from FRBs/FRB: positions, redshifts, repeater flag
  data/repeater_ephemerides.json   activity cycles of periodic repeaters
  data/repeater_reports.json       later activity reports (ATel feed, weekly literature search, by hand)
"""
import csv
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAT2 = ROOT / "data" / "chimefrbcat2.csv"
HOSTS = ROOT / "docs" / "data" / "hosts_base.json"
EPH = ROOT / "data" / "repeater_ephemerides.json"
REP = ROOT / "data" / "repeater_reports.json"
OUT = ROOT / "docs" / "data" / "repeaters.json"


def mjd_to_iso(m):
    return (dt.datetime(1858, 11, 17) + dt.timedelta(days=m)).strftime("%Y-%m-%d")


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def norm(name):
    m = re.search(r"(\d{8}[A-Z]{0,2})", str(name))
    return m.group(1) if m else None


def main():
    src = defaultdict(lambda: {"cat2_bursts": 0, "cat2_mjd": [], "aliases": set()})

    # CHIME/FRB Catalog 2: one entry per repeater, named by its repeater name
    if CAT2.exists():
        for r in csv.DictReader(open(CAT2, newline="", encoding="utf-8-sig")):
            rep = norm(r.get("repeater_name"))
            if not rep or r.get("sub_num") not in ("0", ""):
                continue
            s = src[rep]
            s["cat2_bursts"] += 1
            if fnum(r.get("mjd_400")):
                s["cat2_mjd"].append(fnum(r["mjd_400"]))
            s.setdefault("ra", fnum(r.get("ra")))
            s.setdefault("dec", fnum(r.get("dec")))
            s.setdefault("dm", fnum(r.get("dm_fitb")))
            s.setdefault("dm_exc", fnum(r.get("dm_exc_ne2001")))
            s["aliases"].add(norm(r.get("tns_name")))

    # Localized repeaters (better positions, redshifts)
    hosts = json.loads(HOSTS.read_text())["hosts"] if HOSTS.exists() else []
    for h in hosts:
        if not h.get("repeater"):
            continue
        s = src[h["frb"]]
        s["ra"], s["dec"] = h.get("ra") or s.get("ra"), h.get("dec") or s.get("dec")
        s["localized"] = True
        s["z"] = h.get("z")
        if h.get("dm") and not s.get("dm"):
            s["dm"] = h["dm"]

    eph = {e["frb"]: e for e in json.loads(EPH.read_text())["sources"]}
    for name in eph:
        src[name]  # make sure periodic sources are listed

    reports = json.loads(REP.read_text()) if REP.exists() else {"reports": []}
    by_frb = defaultdict(list)
    for r in reports.get("reports", []):
        n = norm(r.get("frb"))
        if n:
            by_frb[n].append(r)

    out = []
    for name, s in src.items():
        if s.get("ra") is None:
            continue
        mjds = sorted(s["cat2_mjd"])
        reps = sorted(by_frb.get(name, []), key=lambda r: r.get("date", ""), reverse=True)
        det = [r for r in reps if r.get("type") in ("detection", "burst-storm")]
        last_det = max([d for d in [mjd_to_iso(mjds[-1]) if mjds else None] + [r.get("date") for r in det] if d], default=None)
        out.append({
            "frb": name, "ra": round(s["ra"], 4), "dec": round(s["dec"], 4),
            "dm": round(s["dm"], 1) if s.get("dm") else None, "z": s.get("z"), "localized": bool(s.get("localized")),
            "cat2_bursts": s["cat2_bursts"],
            "cat2_first": mjd_to_iso(mjds[0]) if mjds else None, "cat2_last": mjd_to_iso(mjds[-1]) if mjds else None,
            "last_detection": last_det, "reports": reps[:12], "periodic": eph.get(name),
        })
    out.sort(key=lambda s: (s["last_detection"] or "", s["cat2_bursts"]), reverse=True)
    doc = {"updated": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "cat2_end": "2023-09-15", "last_search": reports.get("last_search"), "sources": out}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} repeaters ({sum(1 for s in out if s['periodic'])} periodic, "
          f"{sum(len(s['reports']) for s in out)} reports) -> {OUT}")


if __name__ == "__main__":
    main()
