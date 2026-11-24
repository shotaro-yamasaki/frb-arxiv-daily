"""Track citations to my papers with NASA ADS, and flag recent FRB papers that probably should cite them.

Writes docs/data/citations.json, which the hidden page docs/me.html displays.

Needs the secret ADS_TOKEN (free: https://ui.adsabs.harvard.edu/user/settings/token).
Without it the script exits quietly, so the main site keeps working.
Optional: ANTHROPIC_API_KEY lets Claude judge each "missing citation" candidate.
Only the Python standard library is needed.
"""
import datetime as dt
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"
PAPERS = ROOT / "docs" / "data" / "papers.json"
OUT = ROOT / "docs" / "data" / "citations.json"
ADS_URL = "https://api.adsabs.harvard.edu/v1/search/query"

CITE_FL = "bibcode,title,author,author_count,pub,year,pubdate,entry_date,identifier,doi,property,reference,doctype"
MINE_FL = "bibcode,alternate_bibcode,title,year,pub,identifier,citation_count,abstract,reference,property"


# ---------------- ADS ----------------

def ads_search(q, fl, rows=2000, sort="date desc"):
    """Return all documents for a query (handles pagination)."""
    token = os.environ["ADS_TOKEN"]
    docs, start = [], 0
    while True:
        params = urllib.parse.urlencode({"q": q, "fl": fl, "rows": rows, "start": start, "sort": sort})
        req = urllib.request.Request(f"{ADS_URL}?{params}", headers={"Authorization": f"Bearer {token}"})
        for i in range(3):
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    res = json.loads(r.read())["response"]
                break
            except Exception as e:  # noqa: BLE001
                if i == 2:
                    raise
                print(f"ADS retry {i + 1}: {e}", file=sys.stderr)
                time.sleep(5 * (i + 1))
        docs += res["docs"]
        start += len(res["docs"])
        if not res["docs"] or start >= res["numFound"]:
            return docs


# ---------------- helpers ----------------

def arxiv_id(doc):
    for ident in doc.get("identifier", []) or []:
        m = re.search(r"(\d{4}\.\d{4,5})", ident)
        if m and ("arXiv" in ident or re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", ident)):
            return m.group(1)
    m = re.search(r"arXiv(\d{4})(\d{4,5})", doc.get("bibcode", ""))
    return f"{m.group(1)}.{m.group(2)}" if m else None


def is_journal(doc):
    pub = (doc.get("pub") or "").lower()
    return "arxiv" not in pub and "arXiv" not in doc.get("bibcode", "")


def title_of(doc):
    t = doc.get("title") or [""]
    return t[0] if isinstance(t, list) else t


def is_self(authors, patterns):
    return any(a.startswith(p) for a in authors for p in patterns)


STOP = set("""a an the of and or in on for to with by from at as is are was were be been this that these those we our
us it its their which using use used can may also than then into over under between both such via based new show
shows find found here paper study results result model models data observed observations observation present
two one three first however within among more most less large small high low each other whereas while thus""".split())


def tokens(text):
    return [w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", text.lower()) if w not in STOP]


class TfIdf:
    def __init__(self, corpus):
        self.n = len(corpus) or 1
        df = Counter()
        for doc in corpus:
            df.update(set(tokens(doc)))
        self.idf = {w: math.log((1 + self.n) / (1 + c)) + 1 for w, c in df.items()}

    def vec(self, text):
        tf = Counter(tokens(text))
        v = {w: (1 + math.log(c)) * self.idf.get(w, math.log(1 + self.n) + 1) for w, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / norm for w, x in v.items()}

    @staticmethod
    def cos(a, b):
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(w, 0.0) for w, x in a.items())


# ---------------- optional LLM judgement ----------------

def llm_judge(cand, mine):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = os.environ.get("ANTHROPIC_MODEL") or "claude-haiku-5-5"
    prompt = (
        "Paper A is a new paper. Paper B is an earlier paper. Paper A does not cite paper B.\n"
        "Decide whether paper A should reasonably have cited paper B, judging only from relevance of the topics and results.\n\n"
        f"A title: {cand['title']}\nA abstract: {cand['abstract']}\n\n"
        f"B title: {mine['title']}\nB abstract: {mine['abstract']}\n\n"
        'Reply with JSON only: {"verdict": "strong" | "maybe" | "no", '
        '"reason_en": "<one short sentence>", "reason_ja": "<日本語で一文>"}'
    )
    body = json.dumps({"model": model, "max_tokens": 300,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = json.loads(r.read())["content"][0]["text"]
        return json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    except Exception as e:  # noqa: BLE001
        print(f"LLM judge failed: {e}", file=sys.stderr)
        return None


# ---------------- main steps ----------------

def load_state():
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {"citations": [], "missing": [], "missing_checked": {}, "baseline_date": None}


def fetch_my_papers(me):
    docs = ads_search(me["papers_query"], MINE_FL)
    if me.get("include_bibcodes"):
        q = "bibcode:(" + " OR ".join(f'"{b}"' for b in me["include_bibcodes"]) + ")"
        docs += ads_search(q, MINE_FL)
    excl = set(me.get("exclude_bibcodes", []))
    seen, out = set(), []
    for d in docs:
        if d["bibcode"] in excl or d["bibcode"] in seen:
            continue
        seen.add(d["bibcode"])
        out.append(d)
    return out


def bibcode_query(bibcodes):
    return "bibcode:(" + " OR ".join(f'"{b}"' for b in bibcodes) + ")"


def update_citations(state, mine, me, today):
    alias = {}  # any bibcode of my paper -> canonical bibcode
    for d in mine:
        alias[d["bibcode"]] = d["bibcode"]
        for a in d.get("alternate_bibcode") or []:
            alias[a] = d["bibcode"]

    # Query by my bibcodes in chunks (ADS queries are limited to ~1000 characters).
    citing = {}
    canon = [d["bibcode"] for d in mine]
    for i in range(0, len(canon), 20):
        for doc in ads_search(f"citations({bibcode_query(canon[i:i + 20])})", CITE_FL):
            citing[doc["bibcode"]] = doc

    first_run = not state["citations"]
    if first_run:
        state["baseline_date"] = today
    old = {c["key"]: c for c in state["citations"]}
    patterns = me.get("self_author_patterns", [])
    result = []
    for doc in citing.values():
        ax = arxiv_id(doc)
        key = f"arXiv:{ax}" if ax else doc["bibcode"]
        cited = sorted({alias[b] for b in doc.get("reference") or [] if b in alias})
        authors = doc.get("author") or []
        rec = old.get(key, {})
        journal = is_journal(doc)
        entry = {
            "key": key,
            "bibcode": doc["bibcode"],
            "arxiv": ax,
            "doi": (doc.get("doi") or [None])[0],
            "title": title_of(doc),
            "authors": authors[:10],
            "n_authors": doc.get("author_count") or len(authors),
            "pub": doc.get("pub") or "",
            "year": doc.get("year"),
            "journal": journal,
            "refereed": "REFEREED" in (doc.get("property") or []),
            "self": is_self(authors, patterns),
            "cited": cited or rec.get("cited", []),
            "first_seen": rec.get("first_seen", today),
            "baseline": rec.get("baseline", first_run),
            "journal_seen": rec.get("journal_seen"),
            "entry_date": (doc.get("entry_date") or "")[:10],
        }
        # An arXiv-only citation that has now appeared in a journal.
        if journal and rec and not rec.get("journal") and not rec.get("journal_seen"):
            entry["journal_seen"] = today
        result.append(entry)
    result.sort(key=lambda c: (c["journal_seen"] or c["first_seen"], c["first_seen"], c["entry_date"]), reverse=True)
    state["citations"] = result

    counts = Counter(b for c in result for b in c["cited"])
    recent_cut = (dt.date.fromisoformat(today) - dt.timedelta(days=30)).isoformat()
    recent = Counter(b for c in result if c["first_seen"] >= recent_cut and not c["baseline"] for b in c["cited"])
    state["my_papers"] = sorted([{
        "bibcode": d["bibcode"],
        "title": title_of(d),
        "year": d.get("year"),
        "pub": d.get("pub"),
        "arxiv": arxiv_id(d),
        "refereed": "REFEREED" in (d.get("property") or []),
        "citation_count": d.get("citation_count") or counts.get(d["bibcode"], 0),
        "new_30d": recent.get(d["bibcode"], 0),
    } for d in mine], key=lambda p: (p["year"] or "", p["bibcode"]), reverse=True)
    return alias


def find_missing(state, mine, alias, me, today):
    cfg = me.get("missing", {})
    if not PAPERS.exists():
        return
    feed = json.loads(PAPERS.read_text(encoding="utf-8"))["papers"]
    t0 = dt.date.fromisoformat(today)
    lo = (t0 - dt.timedelta(days=cfg.get("max_age_days", 30))).isoformat()
    hi = (t0 - dt.timedelta(days=cfg.get("min_age_days", 3))).isoformat()
    checked = state.setdefault("missing_checked", {})
    todo = [p for p in feed if lo <= p["date"] <= hi and checked.get(p["id"]) != "done"]
    # Forget bookkeeping for papers that have left the window.
    for k in [k for k in checked if not any(p["id"] == k for p in feed if p["date"] >= lo)]:
        checked.pop(k)
    if not todo:
        return

    corpus = [p["title"] + " " + p["abstract"] for p in feed] + [title_of(d) + " " + (d.get("abstract") or "") for d in mine]
    tf = TfIdf(corpus)
    mine_vec = {d["bibcode"]: tf.vec(title_of(d) + " " + (d.get("abstract") or "")) for d in mine}
    mine_refs = {d["bibcode"]: set(d.get("reference") or []) for d in mine}
    mine_by = {d["bibcode"]: d for d in mine}
    patterns = me.get("self_author_patterns", [])
    existing = {(m["arxiv"], m["my_bibcode"]) for m in state["missing"]}

    for i in range(0, len(todo), 20):
        chunk = todo[i:i + 20]
        q = "identifier:(" + " OR ".join(f'"arXiv:{p["id"]}"' for p in chunk) + ")"
        docs = {arxiv_id(d): d for d in ads_search(q, "bibcode,identifier,reference,author")}
        for p in chunk:
            d = docs.get(p["id"])
            refs = set((d or {}).get("reference") or [])
            if not refs:
                checked[p["id"]] = "pending"  # ADS has not parsed the reference list yet
                continue
            checked[p["id"]] = "done"
            if is_self(p["authors"] + ((d or {}).get("author") or []), patterns):
                continue
            cited = {alias[b] for b in refs if b in alias}
            v = tf.vec(p["title"] + " " + p["abstract"])
            scored = []
            for b, md in mine_by.items():
                if b in cited:
                    continue
                sim = tf.cos(v, mine_vec[b])
                shared = len(refs & mine_refs[b])
                if sim >= cfg.get("text_threshold", 0.3) or shared >= cfg.get("shared_refs_threshold", 6):
                    scored.append((sim + 0.03 * shared, sim, shared, b))
            for score, sim, shared, b in sorted(scored, reverse=True)[:cfg.get("max_per_paper", 2)]:
                if (p["id"], b) in existing:
                    continue
                item = {
                    "arxiv": p["id"], "title": p["title"], "authors": p["authors"][:10],
                    "n_authors": len(p["authors"]), "date": p["date"], "primary": p.get("primary"),
                    "cites_me_elsewhere": bool(cited),
                    "my_bibcode": b, "my_title": title_of(mine_by[b]), "my_year": mine_by[b].get("year"),
                    "text_sim": round(sim, 3), "shared_refs": shared, "score": round(score, 3),
                    "found": today,
                }
                j = llm_judge({"title": p["title"], "abstract": p["abstract"]},
                              {"title": title_of(mine_by[b]), "abstract": mine_by[b].get("abstract") or ""})
                if j:
                    if j.get("verdict") == "no":
                        continue
                    item.update(verdict=j.get("verdict"), reason_en=j.get("reason_en"), reason_ja=j.get("reason_ja"))
                state["missing"].append(item)
                existing.add((p["id"], b))
    state["missing"].sort(key=lambda m: (m["found"], m["score"]), reverse=True)
    state["missing"] = state["missing"][:300]


def main():
    if not os.environ.get("ADS_TOKEN"):
        print("ADS_TOKEN is not set: skipping citation tracking.")
        return
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    me = cfg["me"]
    today = os.environ.get("TODAY") or dt.date.today().isoformat()
    state = load_state()
    mine = fetch_my_papers(me)
    print(f"{len(mine)} of my papers")
    alias = update_citations(state, mine, me, today)
    print(f"{len(state['citations'])} citing papers")
    find_missing(state, mine, alias, me, today)
    print(f"{len(state['missing'])} missing-citation candidates")
    state["updated"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
