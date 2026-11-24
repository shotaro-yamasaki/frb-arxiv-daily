"""Keyword-based subfield classifier for FRB papers (stdlib only)."""
import re


def _is_case_sensitive(kw):
    # Acronyms / names such as FAST, CHIME, RM, H0, MeerKAT, TeV are matched case-sensitively.
    return any(c.isdigit() for c in kw) or any(c.isupper() for c in kw[1:])


def _compile(kw):
    esc = re.escape(kw)
    if _is_case_sensitive(kw):
        return re.compile(r"(?<![A-Za-z0-9])" + esc + r"(?![A-Za-z])")
    # Case-insensitive, start-of-word match (so stems like "cosmolog" work).
    return re.compile(r"(?<![A-Za-z])" + esc, re.IGNORECASE)


class Classifier:
    def __init__(self, config):
        self.min_score = config.get("min_score", 2)
        self.subfields = []
        for sf in config["subfields"]:
            rules = [(_compile(k), w) for k, w in sf["keywords"].items()]
            self.subfields.append({"id": sf["id"], "name": sf["name"], "rules": rules})
        self.frb_patterns = [re.compile(p, 0 if "FRB" in p else re.IGNORECASE)
                             for p in config["frb_patterns"]]
        self.watch = [(w, _compile(w)) for w in config.get("watchlist", [])]

    def is_frb(self, title, abstract):
        text = f"{title}\n{abstract}"
        return any(p.search(text) for p in self.frb_patterns)

    def score(self, title, abstract):
        scores = {}
        for sf in self.subfields:
            s = 0
            for rx, w in sf["rules"]:
                if rx.search(title):
                    s += 2 * w  # title hits count double
                elif rx.search(abstract):
                    s += w
            scores[sf["id"]] = s
        return scores

    def classify(self, title, abstract):
        scores = self.score(title, abstract)
        order = [sf["id"] for sf in self.subfields]
        ranked = sorted(order, key=lambda i: (-scores[i], order.index(i)))
        top = scores[ranked[0]]
        if top < self.min_score:
            return {"primary": "other", "tags": [], "scores": scores}
        # Secondary tags must be reasonably strong compared with the primary one.
        floor = max(self.min_score + 1, 0.5 * top)
        tags = [ranked[0]] + [i for i in ranked[1:] if scores[i] >= floor]
        primary = tags[0]
        return {"primary": primary, "tags": tags[:4], "scores": scores}

    def watch_hits(self, title, abstract):
        text = f"{title}\n{abstract}"
        return [w for w, rx in self.watch if rx.search(text)]
