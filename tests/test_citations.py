"""Offline test of scripts/citations.py with a fake ADS. Run: python tests/test_citations.py

It uses a temporary copy of the data files, so the real docs/data is not touched.
"""
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import citations  # noqa: E402

MINE = [
    {"bibcode": "2024ApJ...900....1Y", "alternate_bibcode": ["2024arXiv240100001Y"],
     "title": ["Energy functions of hyperactive repeating FRBs"], "year": "2024", "pub": "The Astrophysical Journal",
     "identifier": ["arXiv:2401.00001"], "citation_count": 2, "property": ["REFEREED"],
     "abstract": "We measure the energy function of hyperactive repeating fast radio bursts and compare waiting time distributions and burst rate of repeaters.",
     "reference": ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]},
    {"bibcode": "2025PASJ...77....2Y", "alternate_bibcode": [],
     "title": ["Missing baryons and the Macquart relation from localized FRBs"], "year": "2025", "pub": "PASJ",
     "identifier": ["arXiv:2502.00002"], "citation_count": 1, "property": ["REFEREED"],
     "abstract": "Localized fast radio bursts constrain the cosmic baryon fraction through the Macquart relation of dispersion measure and redshift.",
     "reference": ["C1", "C2"]},
]

WORLD = {"day": 1}


def cite_docs():
    docs = [
        {"bibcode": "2026arXiv260100010A", "title": ["Old citing preprint"], "author": ["Author, A.", "Other, B."],
         "author_count": 2, "pub": "arXiv e-prints", "year": "2026", "identifier": ["arXiv:2601.00010"],
         "property": [], "reference": ["2024arXiv240100001Y"], "entry_date": "2026-01-05T00:00:00Z"},
        {"bibcode": "2025MNRAS.500..100Y", "title": ["Self citation"], "author": ["Yamasaki, Shotaro"],
         "author_count": 1, "pub": "MNRAS", "year": "2025", "identifier": ["arXiv:2503.00011"],
         "property": ["REFEREED"], "reference": ["2025PASJ...77....2Y"], "entry_date": "2025-03-05T00:00:00Z"},
    ]
    if WORLD["day"] >= 2:
        # A brand-new citation, and the old preprint is now published in ApJ.
        docs.append({"bibcode": "2026arXiv261100099C", "title": ["A new paper citing both"],
                     "author": ["Cite, C."], "author_count": 1, "pub": "arXiv e-prints", "year": "2026",
                     "identifier": ["arXiv:2611.00099"], "property": [],
                     "reference": ["2024ApJ...900....1Y", "2025PASJ...77....2Y"], "entry_date": "2026-11-27T00:00:00Z"})
        docs[0] = dict(docs[0], bibcode="2026ApJ...950...10A", pub="The Astrophysical Journal", property=["REFEREED"])
    return docs


def fake_ads(q, fl, rows=2000, sort="date desc"):
    if q.startswith("citations("):
        wanted = set(re.findall(r'"([^"]+)"', q))
        return [d for d in cite_docs() if set(d["reference"]) & (wanted | {"2024arXiv240100001Y"})]
    if q.startswith("identifier:("):
        ids = re.findall(r'arXiv:(\d{4}\.\d{4,5})', q)
        refs = {
            "2611.00001": ["R1", "R2", "R3", "R4", "R5", "R6", "X"],  # repeater paper, doesn't cite me
            "2611.00002": ["2025PASJ...77....2Y", "C1"],              # cosmology paper, cites me
            "2611.00005": [],                                         # not parsed yet -> pending
        }
        return [{"bibcode": f"2026arXiv{i.replace('.', '')}X", "identifier": [f"arXiv:{i}"],
                 "reference": refs.get(i, ["Z"]), "author": ["Someone, X."]} for i in ids]
    return MINE


def main():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "docs" / "data").mkdir(parents=True)
    shutil.copy(ROOT / "config.json", tmp / "config.json")
    os.system(f'cd "{tmp}" && cp -r "{ROOT}/scripts" . && python3 scripts/fetch.py --rss-file "{ROOT}/tests/sample_rss.xml" > /dev/null')
    citations.CONFIG, citations.PAPERS, citations.OUT = (tmp / "config.json", tmp / "docs/data/papers.json",
                                                         tmp / "docs/data/citations.json")
    citations.ads_search = fake_ads
    os.environ["ADS_TOKEN"] = "fake"
    os.environ.pop("ANTHROPIC_API_KEY", None)

    os.environ["TODAY"] = "2026-11-27"
    citations.main()
    s = json.loads(citations.OUT.read_text())
    assert s["baseline_date"] == "2026-11-27"
    assert all(c["baseline"] for c in s["citations"]) and len(s["citations"]) == 2  # both entered ADS long ago
    assert any(c["self"] for c in s["citations"])

    WORLD["day"] = 2
    os.environ["TODAY"] = "2026-11-28"
    citations.main()
    s = json.loads(citations.OUT.read_text())
    by = {c["key"]: c for c in s["citations"]}
    new = by["arXiv:2611.00099"]
    assert not new["baseline"] and new["first_seen"] == "2026-11-28"
    assert new["cited"] == ["2024ApJ...900....1Y", "2025PASJ...77....2Y"]
    pub = by["arXiv:2601.00010"]
    assert pub["journal"] and pub["journal_seen"] == "2026-11-28" and pub["cited"] == ["2024ApJ...900....1Y"]
    assert len(s["citations"]) == 3, "preprint and journal version must be merged"

    miss = {(m["arxiv"], m["my_bibcode"]) for m in s["missing"]}
    assert ("2611.00001", "2024ApJ...900....1Y") in miss, s["missing"]
    assert not any(a == "2611.00002" and b == "2025PASJ...77....2Y" for a, b in miss)
    assert s["missing_checked"].get("2611.00005") == "pending"
    # First run: a citation entered in ADS within 30 days is shown as new right away.
    os.environ["TODAY"] = "2026-01-20"
    citations.OUT.unlink()
    WORLD["day"] = 1
    citations.main()
    s2 = json.loads(citations.OUT.read_text())
    c = {x["key"]: x for x in s2["citations"]}["arXiv:2601.00010"]
    assert not c["baseline"] and c["first_seen"] == "2026-01-05", c
    print("my papers:", [(p["bibcode"], p["new_30d"]) for p in s["my_papers"]])
    print("missing:", [(m["arxiv"], m["my_bibcode"], m["text_sim"], m["shared_refs"]) for m in s["missing"]])
    shutil.rmtree(tmp)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
