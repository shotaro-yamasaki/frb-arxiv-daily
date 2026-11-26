"""Add Astronomer's Telegrams that mention repeating FRBs to data/repeater_reports.json.

Reads the ATel RSS feed (latest telegrams only), keeps telegrams whose title or text names an FRB
(FRB 20xxxxxxA), and adds them as reports with "status": "auto" and "type": "atel".
The weekly literature routine later reads them and records whether they report a detection.
"""
import datetime as dt
import email.utils
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REP = ROOT / "data" / "repeater_reports.json"
FEEDS = ["https://www.astronomerstelegram.org/?rss", "https://www.astronomerstelegram.org/?rss=all"]
NAME = re.compile(r"FRB\s?(20\d{6}[A-Z]{0,2})")


def fetch():
    for url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "frb-arxiv-daily"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            print(f"{url}: {e}", file=sys.stderr)
    return None


def main():
    raw = fetch()
    if not raw:
        print("ATel feed not reachable: nothing added.")
        return
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"ATel feed could not be parsed: {e}")
        return
    doc = json.loads(REP.read_text(encoding="utf-8"))
    have = {(r.get("frb"), (r.get("source") or {}).get("url")) for r in doc["reports"]}
    added = 0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
        link = (item.findtext("link") or "").strip()
        names = sorted(set(NAME.findall(title + " " + desc)))
        if not names:
            continue
        date = item.findtext("pubDate")
        try:
            date = email.utils.parsedate_to_datetime(date).date().isoformat()
        except Exception:  # noqa: BLE001
            date = dt.date.today().isoformat()
        num = re.search(r"(\d{4,6})", link)
        for n in names:
            if (n, link) in have:
                continue
            doc["reports"].append({"frb": n, "date": date, "type": "atel", "telescope": None,
                                   "note": title[:200], "source": {"atel": num.group(1) if num else None, "url": link},
                                   "status": "auto", "added": dt.date.today().isoformat()})
            have.add((n, link))
            added += 1
    REP.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ATel feed: {added} new FRB telegram(s) added")


if __name__ == "__main__":
    main()
