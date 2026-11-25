"""Build docs/data/hosts_base.json from the FRBs/FRB repository (https://github.com/FRBs/FRB).

Usage: python scripts/hosts_sync.py PATH_TO_FRB_REPO
The weekly workflow clones FRBs/FRB and runs this. Values are copied as they are, with their
references. Derived quantities (sSFR, offset from the main sequence, galaxy class) are computed
on the page, so the same rules apply to rows added from the literature (hosts_lit.json).
"""
import csv
import datetime as dt
import glob
import json
import math
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "hosts_base.json"


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def log10_or_none(v):
    return round(math.log10(v), 3) if v and v > 0 else None


def log_err(v, lo, up):
    """Asymmetric errors in dex for a linear quantity."""
    if not v or v <= 0:
        return None, None
    lo_d = round(math.log10(v) - math.log10(v - lo), 3) if lo and v - lo > 0 else None
    up_d = round(math.log10(v + up) - math.log10(v), 3) if up else None
    return lo_d, up_d


def pick(d, keys):
    for k in keys:
        if num(d.get(k)) is not None:
            return k
    return None


def main(repo):
    repo = Path(repo)
    data = repo / "frb" / "data"
    frbs = {}
    for f in glob.glob(str(data / "FRBs" / "FRB*.json")):
        d = json.load(open(f))
        frbs[d.get("FRB")] = d
    public = {}
    pub_csv = data / "Galaxies" / "public_hosts.csv"
    if pub_csv.exists():
        for row in csv.DictReader(open(pub_csv)):
            public["FRB" + row["FRB"].strip()] = row

    rows = []
    for f in sorted(glob.glob(str(data / "Galaxies" / "*" / "*_host.json"))):
        h = json.load(open(f))
        name = h.get("FRB")
        if not name:
            continue
        der, off, zz = h.get("derived", {}), h.get("offsets", {}), h.get("redshift", {})
        frb = frbs.get(name, {})
        pub = public.get(name, {})
        refs = set(frb.get("refs") or [])
        refs |= {v for k, v in der.items() if k.endswith("_ref") and isinstance(v, str)}
        refs |= {r.strip() for r in (pub.get("References") or "").split(",") if r.strip()}

        mkey = pick(der, ["Mstar", "Mstar_spec", "Mtotal"])
        skey = pick(der, ["SFR_SED", "SFR_nebular", "SFR_photom"])
        mstar = num(der.get(mkey)) if mkey else None
        sfr = num(der.get(skey)) if skey else None
        m_lo, m_up = log_err(mstar, num(der.get(f"{mkey}_loerr")) or num(der.get(f"{mkey}_err")),
                             num(der.get(f"{mkey}_uperr")) or num(der.get(f"{mkey}_err"))) if mkey else (None, None)
        z_spec = num(zz.get("z_spec"))
        dm = frb.get("DM", {})
        rows.append({
            "frb": name.replace("FRB", ""),
            "ra": num(h.get("ra")), "dec": num(h.get("dec")),
            "z": num(zz.get("z")), "z_type": "spec" if z_spec is not None else ("phot" if num(zz.get("z_phot")) is not None else None),
            "repeater": frb.get("repeater"),
            "dm": num(dm.get("value")) if isinstance(dm, dict) else num(dm),
            "p_ox": num(pub.get("P_Ox")),
            "surveys": [p.strip() for p in (pub.get("Projects") or "").split(",") if p.strip() and not p.strip().startswith("F4")],
            "log_mstar": log10_or_none(mstar), "log_mstar_lo": m_lo, "log_mstar_up": m_up,
            "mstar_kind": {"Mstar": "stellar", "Mstar_spec": "stellar (spec)", "Mtotal": "total formed"}.get(mkey),
            "sfr": round(sfr, 4) if sfr is not None else None,
            "sfr_lo": num(der.get(f"{skey}_loerr")) or num(der.get(f"{skey}_err")) if skey else None,
            "sfr_up": num(der.get(f"{skey}_uperr")) or num(der.get(f"{skey}_err")) if skey else None,
            "sfr_kind": {"SFR_SED": "SED", "SFR_nebular": "Hα/nebular", "SFR_photom": "photometric"}.get(skey),
            "offset_kpc": num(off.get("physical")), "offset_kpc_err": num(off.get("physical_err")),
            "offset_arcsec": num(off.get("ang_best")),
            "z_gas": num(der.get("Z_gas")), "z_stellar": num(der.get("Z_stellar")),
            "av": num(der.get("AV_old")), "m_r": num(der.get("M_r")), "u_r": num(der.get("u-r")),
            "age_mass": num(der.get("age_mass")),
            "morphology": h.get("morphology") if isinstance(h.get("morphology"), str) else None,
            "refs": sorted({r.lower(): r for r in sorted(refs, reverse=True)}.values()),
            "source": "FRBs/FRB",
        })

    commit = None
    try:
        commit = subprocess.check_output(["git", "-C", str(repo), "log", "-1", "--format=%h %cs"], text=True).strip()
    except Exception:  # noqa: BLE001
        pass
    out = {"updated": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "source": "https://github.com/FRBs/FRB", "source_commit": commit, "hosts": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(rows)
    print(f"{n} hosts -> {OUT}  (M*: {sum(r['log_mstar'] is not None for r in rows)}, "
          f"SFR: {sum(r['sfr'] is not None for r in rows)}, offset: {sum(r['offset_kpc'] is not None for r in rows)})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("FRB_REPO", "FRB"))
