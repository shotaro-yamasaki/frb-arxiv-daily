"""Download CHIME/FRB Catalog 2 (CSV) from the official CHIME/FRB API into data/chimefrbcat2.csv.

The official site documents the API: https://chime-frb.ca/tutorials
Does nothing once data/chimefrbcat2.source says the file is the official one.
"""
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "chimefrbcat2.csv"
SRC = ROOT / "data" / "chimefrbcat2.source"
API = "https://chime-frb.ca/api/v1/catalogs/catalog2"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "frb-arxiv-daily"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    if SRC.exists() and SRC.read_text().startswith("official"):
        print("Catalog 2 is already the official file")
        return
    try:
        info = json.loads(get(API))
        url = next(f["url"] for f in info["downloads"] if str(f.get("format", "")).lower() == "csv")
        data = get(url)
    except Exception as e:  # noqa: BLE001
        print(f"Could not download Catalog 2 from the official API ({e}). Keeping the current file.")
        return
    head = data[:2000].decode("utf-8", "replace")
    if "tns_name" not in head or data.count(b"\n") < 4000:
        print("Downloaded file does not look like Catalog 2. Keeping the current file.")
        return
    CSV.parent.mkdir(exist_ok=True)
    CSV.write_bytes(data)
    SRC.write_text(f"official {url} {date.today()}\n")
    print(f"Saved the official Catalog 2: {data.count(b'\n')} lines from {url}")


if __name__ == "__main__":
    sys.exit(main())
