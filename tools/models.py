"""Match photo captions to a factory's EEC model names ("125-G1" ~ "Zontes ZT125-G1", "VOGE DS900X" ~ "DS 900 X")."""
import re

def brand_words(f):
    return {w.lower() for w in re.split(r"[\s/]+", f.get("name", "")) if len(w) > 2}

def tokens(s, brands=()):
    s = re.sub(r"\(.*?\)", " ", str(s).lower())
    return [t for t in re.findall(r"[a-z]+|\d+", s) if t not in brands]

def pattern(name, brands=()):
    """Regex for a model name: same letter/number groups in order, any separators, an optional short letter prefix (ZT, QJ)."""
    t = tokens(name, brands)
    if not t or sum(len(x) for x in t) < 2 or (sum(len(x) for x in t) < 3 and not (any(x.isalpha() for x in t) and any(x.isdigit() for x in t))): return None
    if t[0].isalpha() and len(t[0]) <= 2 and len(t) > 2 and t[1].isdigit(): t = t[1:]  # "ZT703-F" -> 703 f
    body = r"[\s\-_./]*".join(map(re.escape, t))
    return re.compile(r"(?<![a-z0-9])(?:[a-z]{1,3}[\s\-]?)?" + body + r"(?![a-z0-9])")

def match(f, caption):
    """EEC model names this caption shows (longest name first, so "SRK 800 RR" beats "SRK 800")."""
    brands = brand_words(f)
    cap = " ".join(tokens(caption, brands))
    hits = []
    for m in sorted(f.get("eec", []) + f.get("non", []), key=lambda m: -len(m["n"])):
        p = pattern(m["n"], brands)
        if p and p.search(cap) and not any(p.search(" ".join(tokens(h, brands))) for h in hits):
            hits.append(m["n"])
    return hits
