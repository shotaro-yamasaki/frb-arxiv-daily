"""Build the data for the transient phase-space page (docs/phase.html).

Usage:
  python scripts/build_phase.py PATH_TO_Transient_Phase_Space PATH_TO_FRBs_FRB_repo [--cat2 data/chimefrbcat2.csv]

FRBs come from CHIME/FRB Catalog 2 when --cat2 points to the catalogue file, otherwise from Catalog 1.

Inputs
  - FRBs/Transient_Phase_Space (Keane, Pietka et al.; GPL-3.0): pulsars, RRATs, giant pulses, Sun,
    flare stars, XRBs, AGN, SNe, GRB afterglows, novae, CVs, GW170817, SGR 1935+2154.
  - FRBs/FRB: CHIME/FRB Catalog 1 (peak flux, width, peak frequency, DM) and spectroscopic redshifts.
  - scripts/phase_manual.json: long-period transients and high-energy/optical classes, typed in from papers.

Output
  docs/data/phase.json with two panels:
    radio: x = nu*W (GHz s), y = L_nu = 4 pi D^2 S (erg/s/Hz)
    he:    x = duration (s), y = peak luminosity (erg/s)
"""
import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "phase.json"
MANUAL = ROOT / "scripts" / "phase_manual.json"

JY = 1e-23            # erg/s/cm2/Hz
KPC = 3.0857e21       # cm
SD2_TO_LNU = 4 * math.pi * JY * KPC ** 2   # S[Jy] * D[kpc]^2 -> L_nu [erg/s/Hz]  (= 1.197e21)

# Planck18
H0, OM = 67.66, 0.30966


def lum_dist_kpc(z, n=2000):
    c = 299792.458
    s = 0.0
    for i in range(n):
        zz = (i + 0.5) / n * z
        s += 1.0 / math.sqrt(OM * (1 + zz) ** 3 + (1 - OM))
    dc = c / H0 * s * z / n      # Mpc
    return dc * (1 + z) * 1e3


def num(s):
    try:
        v = float(str(s).strip().lstrip("<>"))
        return v if math.isfinite(v) and v > 0 else None
    except ValueError:
        return None


CAT2 = None
META = {}

# Column names used by the CHIME/FRB catalogues. The first name found is used.
COLS = {
    "name": ["tns_name"], "repeater": ["repeater_name"], "flux": ["flux"], "width": ["width_fitb", "width"],
    "freq": ["peak_freq"], "dmx": ["dm_exc_ne2001", "dm_exc_ymw16"], "sub": ["sub_num"],
}


def read_chime(frbrepo, cat2_path):
    """First sub-burst of each CHIME burst, with L_nu and the source of z."""
    zspec = {}
    for f in (Path(frbrepo) / "frb" / "data" / "FRBs").glob("FRB*.json"):
        d = json.load(open(f))
        if d.get("z"):
            zspec[d["FRB"].replace("FRB", "")] = d["z"]
    if cat2_path and Path(cat2_path).exists():
        path, cat_name, ref = Path(cat2_path), "CHIME/FRB Catalog 2", "CHIME/FRB Collaboration 2025 (Catalog 2)"
    else:
        path, cat_name, ref = Path(frbrepo) / "frb" / "data" / "FRBs" / "chimefrbcat1.csv", "CHIME/FRB Catalog 1", "CHIME/FRB Collaboration 2021"
        if not path.exists():
            path = Path(frbrepo) / "frb" / "data" / "FRBs" / "chimefrbcat.csv"
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8-sig")))
    have = set(rows[0].keys()) if rows else set()
    col = {}
    for k, names in COLS.items():
        col[k] = next((n for n in names if n in have), None)
        if col[k] is None and k != "sub":
            sys.exit(f"{path.name}: no column for '{k}' (tried {names}). Columns are: {sorted(have)}")
    print(f"{cat_name}: {len(rows)} rows, columns used: {col}")
    one, rep = [], []
    seen = set()
    for r in rows:
        if col["sub"] and r.get(col["sub"]) not in ("0", "", None):
            continue
        name = r[col["name"]].replace("FRB", "").strip()
        repname = (r.get(col["repeater"]) or "").strip()
        is_rep = repname not in ("", "-9999", "nan", "None")
        key = (name, r.get(col["freq"]), r.get(col["flux"]))
        if key in seen:
            continue
        seen.add(key)
        flux, width, nu = num(r[col["flux"]]), num(r[col["width"]]), num(r[col["freq"]])
        if not (flux and width and nu):
            continue
        nu = min(max(nu, 400.0), 800.0) / 1e3      # GHz, clipped to the CHIME band
        # spectroscopic z: by TNS name, or by repeater name for repeaters (all bursts share the host)
        zk = zspec.get(name) or (zspec.get(repname.replace("FRB", "")) if is_rep else None)
        if zk:
            z, zkind = zk, "spectroscopic"
        else:
            dmx = num(r[col["dmx"]])
            if not dmx:
                continue
            z, zkind = max((dmx - 50 - 50) / 1000.0, 0.01), "from DM"
        dl = lum_dist_kpc(z)
        p = {"x": nu * width, "y": flux * dl ** 2 * SD2_TO_LNU / (1 + z),
             "label": f"FRB {name}" + (f" ({repname.replace('FRB', 'FRB ')})" if is_rep else ""),
             "z": round(z, 3), "zkind": zkind, "nu": nu, "w": width, "ref": ref}
        (rep if is_rep else one).append(p)
    return one, rep, cat_name


def pts(rows, name, cls, ref, note=""):
    return {"name": name, "cls": cls, "ref": ref, "note": note, "points": rows}


def keane_two_col(path, xcol, ycol, skip_header=False, label_col=None):
    """Files that already hold x = nu*W (GHz s) and y = S*D^2 (Jy kpc^2)."""
    out = []
    for i, line in enumerate(open(path)):
        if skip_header and i == 0:
            continue
        f = line.split()
        if len(f) <= max(xcol, ycol):
            continue
        x, y = num(f[xcol]), num(f[ycol])
        if x and y:
            out.append({"x": x, "y": y * SD2_TO_LNU, "label": " ".join(f[label_col:]) if label_col is not None else f[0]})
    return out


def gosia(path, header):
    """Pietka et al. 2015 compilation: rise time [day] in col 2, L_nu [erg/s/Hz] in col 7, nu [GHz] in col 9."""
    out = []
    for i, line in enumerate(open(path)):
        if header and i == 0:
            continue
        f = line.split()
        if len(f) < 9:
            continue
        t, lnu, nu = num(f[1]), num(f[6]), num(f[8])
        if t and lnu and nu:
            out.append({"x": t * 86400 * nu, "y": lnu, "label": f[0]})
    return out


def build_radio(tps, frbrepo):
    g = Path(tps) / "gach_rud"
    series = []
    # pulsars, RRATs, giant pulses: columns 5 and 6 are nu*W and S*D^2
    series.append(pts(keane_two_col(g / "psrs_2", 4, 5), "Pulsars", "pulsar", "ATNF pulsar catalogue via Keane (TPS)"))
    series.append(pts(keane_two_col(g / "rrats_nohead", 4, 5), "RRATs", "rrat", "RRATalog via Keane (TPS)"))
    grp = keane_two_col(g / "GRPs_vals", 6, 7, skip_header=True)
    crab = keane_two_col(g / "crab_GRP", 5, 4)
    nano = keane_two_col(g / "crab_nanogiant", 0, 1)
    series.append(pts(grp + crab + nano, "Pulsar giant pulses", "grp", "Keane (TPS): Crab GRPs, nanoshots, B1821-24, B1937+21"))
    sun = keane_two_col(g / "solar_vals", 4, 5, skip_header=True)
    series.append(pts(sun, "Solar bursts", "sun", "Keane (TPS)"))
    misc = []
    for line in open(g / "misc"):
        f = line.split()
        if len(f) >= 3 and num(f[0]) and num(f[1]):
            misc.append({"x": num(f[0]), "y": num(f[1]) * SD2_TO_LNU, "label": " ".join(f[2:])})
    gw = keane_two_col(g / "gw170817", 0, 1)
    for p in gw:
        p["label"] = "GW170817"
    pg = lambda f, h: gosia(g / f, h)  # noqa: E731
    series.append(pts(pg("Gosia_flare_stars2", False) + [m for m in misc if "Leo" in m["label"] or "Ceti" in m["label"] or "BD" in m["label"]],
                      "Flare stars / brown dwarfs", "star", "Pietka et al. 2015; Keane (TPS)"))
    series.append(pts(pg("Gosia_RSCVn2", False), "RS CVn", "rscvn", "Pietka et al. 2015"))
    series.append(pts(pg("Gosia_MagCV2", True), "Magnetic CVs", "cv", "Pietka et al. 2015"))
    series.append(pts(pg("Gosia_Novae2", False), "Novae", "nova", "Pietka et al. 2015"))
    series.append(pts(pg("Gosia_XRB2", False), "X-ray binaries", "xrb", "Pietka et al. 2015"))
    series.append(pts(pg("Gosia_SN2", False), "Supernovae", "sn", "Pietka et al. 2015"))
    series.append(pts(pg("Gosia_GRB2", False), "GRB afterglows", "grb", "Pietka et al. 2015"))
    series.append(pts(pg("Gosia_AGN_QSO_Blazar_TDE2", True), "AGN / blazars / TDEs", "agn", "Pietka et al. 2015"))
    series.append(pts(gw, "GW170817", "gw", "Keane (TPS)"))
    gcrt = [m for m in misc if "GCRT" in m["label"] or "1745" in m["label"]]
    # SGR 1935+2154 radio burst: S[Jy], D[kpc], nu[GHz], W[s]
    s, d, nu, w = [float(v) for v in open(g / "SGR1935+2154").read().split()[:4]]
    series.append(pts([{"x": nu * w, "y": s * d * d * SD2_TO_LNU, "label": "FRB 20200428D (SGR 1935+2154)"}],
                      "Galactic magnetar burst", "magnetar", "STARE2/CHIME 2020 via Keane (TPS)"))

    one, rep, cat_name = read_chime(frbrepo, CAT2)
    note = (f"{cat_name} (first sub-burst). Filled markers: spectroscopic z of the host. Open markers: z estimated "
            "as (DM_exc,NE2001 - 50 - 50)/1000. L_nu includes a (1+z)^-1 bandwidth factor.")
    for lst, base, label in ((one, "frb", "FRBs"), (rep, "frbrep", "Repeating FRBs")):
        known = [p for p in lst if p["zkind"] == "spectroscopic"]
        est = [p for p in lst if p["zkind"] != "spectroscopic"]
        series.append(pts(est, f"{label}, z from DM", base + "_dm", cat_name, note))
        series.append(pts(known, f"{label}, z measured", base + "_z", cat_name, note))
    META["frb_catalog"] = cat_name
    series.append(pts(gcrt, "GCRT J1745-3009 (old entry)", "lpt", "Keane (TPS)"))
    return series


def build():
    global CAT2
    args = sys.argv[1:]
    if "--cat2" in args:
        i = args.index("--cat2")
        CAT2 = args[i + 1]
        args = args[:i] + args[i + 2:]
    tps, frbrepo = args[0], args[1]
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    radio = build_radio(tps, frbrepo)
    radio = [s for s in radio if s["cls"] != "lpt"]  # replaced by the hand-checked LPT list below

    lpt_pts = []
    for o in manual["lpt"]:
        s = [o["S_min"], o["S_max"]]
        w = [o["W_min"], o["W_max"]]
        d = o["D_kpc"]
        lo = s[0] * d * d * SD2_TO_LNU
        hi = s[1] * d * d * SD2_TO_LNU
        lpt_pts.append({"x": o["nu_GHz"] * math.sqrt(w[0] * w[1]), "y": math.sqrt(lo * hi),
                        "xr": [o["nu_GHz"] * w[0], o["nu_GHz"] * w[1]], "yr": [lo, hi],
                        "label": o["name"] + (" [AUTO]" if o.get("status") == "auto" else ""),
                        "detail": o["detail"], "ref": o["ref"]})
    radio.append(pts(lpt_pts, "Long-period transients", "lpt", "see each object",
                     "Ranges show the reported spread of peak flux density and pulse width."))

    he = []
    # radio bursts on the same luminosity-duration plane: nu*L_nu against pulse width
    frb_he = {"frb_z": [], "frb_dm": []}
    for srs in radio:
        if srs["cls"].startswith("frb"):
            k = "frb_z" if srs["cls"].endswith("_z") else "frb_dm"
            frb_he[k] += [{"x": p["w"], "y": p["nu"] * 1e9 * p["y"], "label": p["label"]} for p in srs["points"]]
    lpt_he = [{"x": math.sqrt(o["W_min"] * o["W_max"]),
               "y": o["nu_GHz"] * 1e9 * math.sqrt(o["S_min"] * o["S_max"]) * o["D_kpc"] ** 2 * SD2_TO_LNU,
               "label": o["name"], "ref": o["ref"]} for o in manual["lpt"]]
    he.append({"name": "FRBs, z from DM (radio, ν L_ν)", "cls": "frb_dm", "ref": META.get("frb_catalog", ""), "radio": True,
               "points": frb_he["frb_dm"], "note": "Radio ν L_ν at the CHIME peak frequency against burst width."})
    he.append({"name": "FRBs, z measured (radio, ν L_ν)", "cls": "frb_z", "ref": META.get("frb_catalog", ""), "radio": True,
               "points": frb_he["frb_z"], "note": "Radio ν L_ν at the CHIME peak frequency against burst width."})
    he.append({"name": "Long-period transients (radio, ν L_ν)", "cls": "lpt", "ref": "see each object", "radio": True, "points": lpt_he})
    for c in manual["he"]:
        he.append({"name": c["name"], "cls": c["cls"], "ref": c["ref"], "note": c.get("note", ""), "label_pos": c.get("label_pos", "top"), "callout": c.get("callout"),
                   "box": {"x": c["t"], "y": c["L"]},
                   "points": [dict(p, label=p["label"] + (" [AUTO]" if p.get("status") == "auto" else "")) for p in c.get("points", [])]})

    out = {"source_note": manual["source_note"], "frb_catalog": META.get("frb_catalog"), "radio": radio, "he": he}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for s in radio:
        print(f"radio {s['name']:32s} {len(s['points'])}")
    print(f"he classes: {len(he)}  -> {OUT} ({OUT.stat().st_size // 1024} kB)")


if __name__ == "__main__":
    build()
