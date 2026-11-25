"""Fetch new FRB papers from arXiv, classify them by subfield, and update docs/data/papers.json.

Daily mode (default): reads the arXiv RSS announcement feed, keeps only `new` and `cross`
announcements (no replacements), and adds FRB papers.
Backfill mode: `python scripts/fetch.py --backfill 60` queries the arXiv API for the last N days.

Optional: if ANTHROPIC_API_KEY is set, Claude refines the subfield labels and writes a
one-line summary (English and Japanese) for each new paper. Without it, keyword rules are used.
Only the Python standard library is needed.
"""
import argparse
import datetime as dt
import email.utils
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify import Classifier  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"
DATA = ROOT / "docs" / "data" / "papers.json"
# arXiv asks API users to identify themselves. Set ARXIV_CONTACT (e.g. as a repo variable) if you like.
UA = "frb-arxiv-daily/1.0" + (f" ({os.environ['ARXIV_CONTACT']})" if os.environ.get("ARXIV_CONTACT") else "")

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def http_get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if i == retries - 1:
                raise
            print(f"retry {i + 1}: {e}", file=sys.stderr)
            time.sleep(5 * (i + 1))


def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def base_id(arxiv_id):
    return re.sub(r"v\d+$", "", arxiv_id)


# ---------- RSS (daily announcements) ----------

def parse_rss(xml_bytes, keep_types):
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    ch_date = channel.findtext("pubDate") if channel is not None else None
    out = []
    for item in root.iter("item"):
        atype = item.findtext("arxiv:announce_type", namespaces=NS) or ""
        desc = item.findtext("description") or ""
        if not atype:
            m = re.search(r"Announce Type:\s*([\w-]+)", desc)
            atype = m.group(1) if m else ""
        if atype not in keep_types:
            continue
        link = item.findtext("link") or ""
        m = re.search(r"(\d{4}\.\d{4,5})", link) or re.search(r"arXiv:(\d{4}\.\d{4,5})", desc)
        if not m:
            continue
        aid = m.group(1)
        abstract = desc.split("Abstract:", 1)[1] if "Abstract:" in desc else desc
        creators = item.findtext("dc:creator", namespaces=NS) or ""
        authors = [a.strip() for a in re.split(r",\s*|\s+and\s+", creators) if a.strip()]
        cats = [c.text for c in item.findall("category") if c.text]
        date_raw = item.findtext("pubDate") or ch_date
        date = (email.utils.parsedate_to_datetime(date_raw).date().isoformat()
                if date_raw else dt.date.today().isoformat())
        out.append({
            "id": aid,
            "title": clean(item.findtext("title")),
            "abstract": clean(abstract),
            "authors": authors,
            "categories": cats,
            "primary_category": cats[0] if cats else "",
            "announce_type": atype,
            "date": date,
        })
    return out


def fetch_rss(cfg):
    url = "https://rss.arxiv.org/rss/" + "+".join(cfg["rss_categories"])
    print(f"GET {url}")
    return parse_rss(http_get(url), set(cfg["announce_types"]))


# ---------- API (backfill) ----------

def parse_atom(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for e in root.findall("atom:entry", NS):
        aid = base_id(e.findtext("atom:id", "", NS).rsplit("/abs/", 1)[-1])
        if not aid:
            continue
        prim = e.find("arxiv:primary_category", NS)
        cats = [c.get("term") for c in e.findall("atom:category", NS)]
        out.append({
            "id": aid,
            "title": clean(e.findtext("atom:title", "", NS)),
            "abstract": clean(e.findtext("atom:summary", "", NS)),
            "authors": [clean(a.findtext("atom:name", "", NS)) for a in e.findall("atom:author", NS)],
            "categories": cats,
            "primary_category": prim.get("term") if prim is not None else (cats[0] if cats else ""),
            "announce_type": "new",
            "date": e.findtext("atom:published", "", NS)[:10],
        })
    return out


def fetch_api(days):
    now = dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(days=days)).strftime("%Y%m%d0000")
    until = now.strftime("%Y%m%d2359")
    q = (f'(abs:"fast radio burst" OR ti:"fast radio burst" OR abs:FRB OR ti:FRB) '
         f'AND submittedDate:[{since} TO {until}]')
    results, start, step = [], 0, 200
    while True:
        params = urllib.parse.urlencode({
            "search_query": q, "start": start, "max_results": step,
            "sortBy": "submittedDate", "sortOrder": "descending",
        })
        url = "https://export.arxiv.org/api/query?" + params
        print(f"GET {url}")
        batch = parse_atom(http_get(url))
        results += batch
        if len(batch) < step:
            break
        start += step
        time.sleep(3)  # arXiv API etiquette
    return results


# ---------- Optional LLM refinement ----------

def llm_refine(papers, subfields):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or not papers:
        return
    model = os.environ.get("ANTHROPIC_MODEL") or "claude-haiku-5-5"
    menu = "\n".join(f"- {s['id']}: {s['name']}" for s in subfields) + "\n- other: Other"
    valid = {s["id"] for s in subfields} | {"other"}
    for p in papers:
        prompt = (
            "You classify fast radio burst (FRB) papers by subfield.\n"
            f"Subfields:\n{menu}\n\n"
            f"Title: {p['title']}\nAbstract: {p['abstract']}\n\n"
            'Reply with JSON only: {"primary": "<id>", "tags": ["<id>", ...], '
            '"summary_en": "<main result in one English sentence, max 30 words>", '
            '"summary_ja": "<主結果を日本語で1文、80字以内>"}. '
            "tags: up to 3 ids including primary, most relevant first."
        )
        body = json.dumps({
            "model": model, "max_tokens": 400,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = json.loads(r.read())["content"][0]["text"]
            res = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            if res.get("primary") in valid:
                p["primary"] = res["primary"]
                tags = [t for t in res.get("tags", []) if t in valid]
                p["tags"] = tags or [res["primary"]]
            for k in ("summary_en", "summary_ja"):
                if res.get(k):
                    p[k] = clean(res[k])
            p["classified_by"] = "llm"
        except Exception as e:  # noqa: BLE001
            print(f"LLM failed for {p['id']}: {e}", file=sys.stderr)


# ---------- main ----------

def load_db():
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    return {"updated": None, "papers": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=0, help="query the arXiv API for the last N days")
    ap.add_argument("--rss-file", help="parse a local RSS file instead of downloading (testing)")
    ap.add_argument("--atom-file", help="parse a local Atom API file instead of downloading (testing)")
    ap.add_argument("--catchup", type=int, default=0,
                    help="also query the arXiv API for the last N days, so a missed day is not lost")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-run keyword classification on stored papers (after editing config.json)")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    clf = Classifier(cfg)
    db = load_db()
    known = {p["id"] for p in db["papers"]}

    if args.rss_file or args.atom_file:
        raw = []
        if args.rss_file:
            raw += parse_rss(Path(args.rss_file).read_bytes(), set(cfg["announce_types"]))
        if args.atom_file:
            raw += parse_atom(Path(args.atom_file).read_bytes())
    elif args.backfill:
        raw = fetch_api(args.backfill)
    elif args.reclassify:
        raw = []
    else:
        raw = fetch_rss(cfg)
        if args.catchup:
            try:
                raw += fetch_api(args.catchup)  # RSS entries come first, so their dates win
            except Exception as e:  # noqa: BLE001
                print(f"catch-up query failed (continuing with RSS only): {e}", file=sys.stderr)
    print(f"{len(raw)} candidate entries")

    new = []
    for p in raw:
        if p["id"] in known or not clf.is_frb(p["title"], p["abstract"]):
            continue
        c = clf.classify(p["title"], p["abstract"])
        p.update(primary=c["primary"], tags=c["tags"], classified_by="keywords",
                 watch=clf.watch_hits(p["title"], p["abstract"]))
        new.append(p)
        known.add(p["id"])
    print(f"{len(new)} new FRB papers")

    llm_refine(new, cfg["subfields"])

    if args.reclassify:
        for p in db["papers"]:
            if p.get("classified_by") != "llm":
                c = clf.classify(p["title"], p["abstract"])
                p.update(primary=c["primary"], tags=c["tags"])
            p["watch"] = clf.watch_hits(p["title"], p["abstract"])

    db["papers"] = sorted(db["papers"] + new, key=lambda p: (p["date"], p["id"]), reverse=True)
    db["subfields"] = [{"id": s["id"], "name": s["name"], "name_ja": s.get("name_ja", s["name"])}
                       for s in cfg["subfields"]] + [{"id": "other", "name": "Other", "name_ja": "その他"}]
    db["updated"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved {len(db['papers'])} papers -> {DATA}")


if __name__ == "__main__":
    main()
