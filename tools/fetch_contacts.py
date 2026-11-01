"""Find public email, WhatsApp, WeChat and phone contacts for every company on EEC Moto Hub.

Runs in GitHub Actions (the cloud sandbox can't reach these sites). Respects robots.txt and
never retries a page that refused us. Only values printed on a company's own pages are kept:
  * the company's official website (home page + its contact / about pages),
  * its own made-in-china showroom (contact + company-info pages; a "Website" listed there is followed),
  * its own directory page (tradewheel, sourceready, b2brazil, reevol...) when robots.txt allows it.
A WhatsApp / WeChat value is kept only when the page labels it as WhatsApp / WeChat
(or it is a wa.me / api.whatsapp.com link). Nothing is guessed. Every value keeps the URL it came from.

Writes data/contacts.json: {id: {emails: [{v, src}], wa: {v, src}, wc: {v, src}, phone: {v, src}, web}}.
"""
import collections, json, re, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urljoin, unquote
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = __file__.rsplit("/tools/", 1)[0]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
LOCK = threading.Lock()
_robots, BLOCKED, HOST_LAST, DEAD = {}, set(), {}, set()
DEBUG = "--debug" in sys.argv
SAMPLES = {}

def allowed(url):
    base = "{0.scheme}://{0.netloc}".format(urlparse(url))
    with LOCK:
        rp = _robots.get(base)
    if rp is None:
        rp = RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers=H, timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        with LOCK: _robots[base] = rp
    return rp.can_fetch(UA, url)

def polite(host, gap=1.0):
    key = ".".join(host.split(".")[-2:])  # one queue per site (all *.made-in-china.com share one)
    while True:
        with LOCK:
            wait = HOST_LAST.get(key, 0) + gap - time.time()
            if wait <= 0: HOST_LAST[key] = time.time(); return
        time.sleep(wait)

def get(url, kind="page"):
    if not url or url in BLOCKED: return None
    if not allowed(url):
        print("  robots.txt disallows", url, file=sys.stderr); BLOCKED.add(url); return None
    host = urlparse(url).netloc
    if host in DEAD: return None
    for i in range(2):
        polite(host)
        try:
            r = requests.get(url, headers=H, timeout=20)
        except Exception as e:
            print("  fail", url, type(e).__name__, file=sys.stderr)
            if "made-in-china" not in host: DEAD.add(host); return None
            time.sleep(2); continue
        if r.status_code in (403, 429):
            BLOCKED.add(url); print("  refused", r.status_code, url, file=sys.stderr)
            if "made-in-china" not in host: DEAD.add(host)  # don't keep knocking on a site that refused us
            return None
        ctype = r.headers.get("content-type", "html")
        if r.status_code == 200 and ("html" in ctype or "text" in ctype or url.endswith(".md")):
            if re.search(r"slide to verify|captcha", r.text[:30000], re.I) and len(r.text) < 40000:
                BLOCKED.add(url); print("  captcha", url, file=sys.stderr); return None
            if DEBUG:
                with LOCK:
                    if len(SAMPLES.setdefault(kind, [])) < 4: SAMPLES[kind].append((url, r.text))
                    if "made-in-china" in host and len(SAMPLES.setdefault("anchors", [])) < 6:
                        SAMPLES["anchors"].append((url, "\n".join(str(a)[:400] for a in BeautifulSoup(r.text, "html.parser").find_all("a")
                                                                  if re.search(r"website|homepage|官网", str(a), re.I))))
            return r.text
        if r.status_code in (404, 410): return None
        time.sleep(3)
    return None

# ---------- extraction ----------
EMAIL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+\-]{0,63}@[A-Za-z0-9.\-]+\.[A-Za-z]{2,10}")
PLATFORM = re.compile(r"made-in-china|micstatic|globalsources|alibaba|aliexpress|tradewheel|sourceready|b2brazil|reevol|freshdi|ec21|"
                      r"example\.|domain\.|yourdomain|email\.com$|sentry|wixpress|w3\.org|schema\.org|cloudflare|godaddy|google|facebook|"
                      r"\.png$|\.jpe?g$|\.gif$|\.webp$|\.svg$|\.css$|\.js$|wordpress|jquery|bootstrap|placeholder|test@|xxx|abc@|name@|user@|"
                      r"youremail|your@|someone@|info@company|mail@mail|admin@admin|@2x|\.wav$|\.mp4$", re.I)
FREEMAIL = re.compile(r"@(163|126|qq|sina|sohu|yeah|139|foxmail|aliyun|gmail|hotmail|outlook|yahoo|live|msn|icloud)\.(com|cn|com\.cn)$", re.I)
NUM = r"(\+?\s?\(?\d[\d\s\-().]{6,22}\d)"
WA_LINK = re.compile(r"(?:wa\.me/|whatsapp\.com/send/?\?(?:[^\"'\s]*?&)?phone=|whatsapp://send/?\?(?:[^\"'\s]*?&)?phone=)\+?(\d{7,15})", re.I)
LABEL = re.compile(r"((?:(?:whats\s?app|wechat|we\s?chat|weixin|微信|tel(?:ephone)?|phone|mobile|mob|cell(?:phone)?|手机|电话|skype|viber|line)"
                   r"\s*(?:no\.?|number|num|id|号)?\s*(?:[/&|,]|and|or|\+)?\s*){1,5})\s*[:：]?\s*" + NUM, re.I)
WC_ID = re.compile(r"(?:wechat|we\s?chat|weixin|微信)\s*(?:id|号|account)?\s*[:：]\s*([A-Za-z][-_A-Za-z0-9]{5,19})\b", re.I)

MARKETS = [("Morocco", r"morocc|maroc"), ("Algeria", r"algeri"), ("Tunisia", r"tunisi"), ("Egypt", r"egypt"), ("Nigeria", r"nigeri"),
           ("France", r"\bfrance\b|french"), ("Spain", r"\bspain\b|spanish"), ("Italy", r"\bital(y|ian)"), ("Germany", r"german"),
           ("Middle East", r"middle[- ]east|mideast|\bgcc\b"), ("Africa", r"africa"), ("Europe", r"europe|\beu\b"),
           ("South America", r"south america|latin america|latam"), ("Central America", r"central america"), ("North America", r"north america|\busa\b"),
           ("Asia", r"south[- ]?east asia|\basia"), ("Oceania", r"oceania|australia")]
TITLE = re.compile(r"(?:general |regional |area |overseas |international |export |sales |marketing |business |account )*"
                   r"(?:manager|director|representative|sales|supervisor|executive|ceo|president|owner|specialist)", re.I)
PERSON = re.compile(r"\b(?:Mr|Ms|Mrs|Miss|Dr)\.?\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)")
CPERSON = re.compile(r"(?:Contact\s*Person|Contact\s*Name|Contact|Sales\s*Contact|联系人)\s*[:：]\s*((?:(?:Mr|Ms|Mrs|Miss)\.?\s+)?[A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){0,2})", re.I)
NOT_NAME = re.compile(r"^(?:Us|Now|Supplier|Information|Info|Details|Form|Person|Name|Email|Phone|Tel|Address|We|Me|Our|The|Sales|Company|Seller)\b", re.I)

def staff_of(text, emails, url):
    """People and the markets they handle, read from the page: a name / title / market close to an email or a Contact Person label."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    out = []
    for i, l in enumerate(lines):
        es = [e for e in emails if e in l.lower()]
        m = CPERSON.search(l) or (CPERSON.search(l + " " + lines[i + 1]) if i + 1 < len(lines) and re.search(r"contact\s*person|联系人", l, re.I) else None)
        if not es and not m: continue
        ctx = " ".join(lines[max(0, i - 3): i + 1]) if es else " ".join(lines[i: i + 3])
        name = m.group(1).strip() if m else (PERSON.search(ctx).group(0) if PERSON.search(ctx) else None)
        if name and (NOT_NAME.search(re.sub(r"^(?:Mr|Ms|Mrs|Miss)\.?\s+", "", name)) or len(name) > 40): name = None
        mk = next((k for k, rx in MARKETS if re.search(rx, ctx, re.I)), None)
        tm = TITLE.search(ctx)
        if not (name or mk): continue
        out.append({"name": name, "role": tm.group(0).strip().title() if tm else None, "market": mk, "email": es[0] if es else None, "src": url})
    return out

def clean_num(s):
    s = re.sub(r"\s+", " ", s).strip(" -.")
    d = re.sub(r"\D", "", s)
    if not 7 <= len(d) <= 16: return None
    if re.fullmatch(r"(19|20)\d\d(19|20)\d\d", d): return None  # year ranges
    return s

def page_text(soup):
    for x in soup(["script", "style", "noscript", "svg"]): x.decompose()
    return re.sub(r"[ \t\r\f\v ]+", " ", soup.get_text("\n", strip=True))

def extract(html, url):
    """Return {emails: set, wa, wc, phone, web, links} found on one page."""
    out = {"emails": [], "wa": None, "wc": None, "phone": None, "web": None, "links": [], "staff": []}
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(url).netloc
    for a in soup.find_all("a", href=True):
        h = a["href"].strip()
        if h.lower().startswith("mailto:"):
            e = unquote(h[7:].split("?")[0]).strip()
            if EMAIL.fullmatch(e) and e not in out["emails"]: out["emails"].append(e)
        m = WA_LINK.search(unquote(h))
        if m and not out["wa"]: out["wa"] = "+" + m.group(1)
        label = (a.get_text(" ", strip=True) + " " + h).lower()
        if re.search(r"contact|about|联系|关于|lianxi|guanyu|company-info|contact-info", label) and len(out["links"]) < 8:
            u = urljoin(url, h).split("#")[0]
            if urlparse(u).netloc == host and u not in out["links"]: out["links"].append(u)
    text = page_text(soup)
    for e in EMAIL.findall(text):
        if e not in out["emails"]: out["emails"].append(e)
    out["emails"] = [e.strip(".").lower() for e in out["emails"] if not PLATFORM.search(e)]
    for m in LABEL.finditer(text):
        lab, num = m.group(1).lower(), clean_num(m.group(2))
        if not num: continue
        if re.search(r"whats\s?app", lab) and not out["wa"]: out["wa"] = num
        if re.search(r"wechat|we\s?chat|weixin|微信", lab) and not out["wc"]: out["wc"] = num
        if re.search(r"tel|phone|mobile|mob|cell|手机|电话", lab) and not out["phone"]: out["phone"] = num
    if not out["wc"]:
        m = WC_ID.search(text)
        if m and not re.fullmatch(r"(?i)scan|follow|official|account|public|qrcode|code", m.group(1)): out["wc"] = m.group(1)
    out["staff"] = staff_of(text, out["emails"], url)
    # Directory pages (made-in-china showroom, tradewheel): the named sales contact, with title / department when shown.
    if re.search(r"made-in-china\.com|tradewheel\.com", host):
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for i, l in enumerate(lines):
            if re.fullmatch(r"(?:Mr|Ms|Mrs|Miss)\.?\s+[A-Za-z][A-Za-z'\- ]{1,38}", l):
                prev = lines[i - 1] if i else ""
                nxt = lines[i + 1:i + 3]
                role = next((x for x in nxt if TITLE.fullmatch(x) or re.fullmatch(r"[A-Za-z ]{2,30}(?:Dept|Department)", x)), None)
                if re.search(r"^(?:\*|To:|Contact Supplier|Contact Details)$", prev) or role or (i > 0 and re.search(r"(?:Co\.,? ?Ltd|Company|Limited|Inc)\.?$", prev, re.I)):
                    name = " ".join(w.capitalize() if w.islower() else w for w in l.split())
                    if not any(p["name"] == name for p in out["staff"]):
                        out["staff"].append({"name": name, "role": " · ".join(x for x in nxt if TITLE.fullmatch(x) or re.search(r"Dept|Department", x))[:60] or None,
                                             "market": None, "email": None, "src": url})
                    if len(out["staff"]) > 4: break
    for a in soup.find_all("a", href=True):
        if re.fullmatch(r"\s*(?:Website|Official Website|Homepage|Home Page|官网|公司网站)\s*", a.get_text(" ", strip=True), re.I):
            h = a["href"].strip()
            if h.startswith("//"): h = "https:" + h
            if h.startswith("http") and urlparse(h).netloc != host and not PLATFORM.search(urlparse(h).netloc) and not out["web"]:
                out["web"] = h
    m = re.search(r"(?:Website|Homepage|Home Page|Web Site|官网|网址)\s*[:：]?\s*((?:https?://)?(?:www\.)?[a-z0-9\-]+(?:\.[a-z0-9\-]+)+(?:/\S*)?)", text, re.I)
    if m and not PLATFORM.search(m.group(1)):
        w = m.group(1).rstrip(".,;)")
        out["web"] = w if w.startswith("http") else "http://" + w
    return out

def email_ok(e, src, web):
    """Keep company-domain mail anywhere; free mail (163/qq/gmail...) only from the company's own pages."""
    d = e.split("@")[1]
    if PLATFORM.search(d): return False
    srch = urlparse(src).netloc
    if web and d.split(".")[-2:] == urlparse(web).netloc.split(".")[-2:]: return True
    if FREEMAIL.search(e): return True
    # other domains: accept only when found on the company's own website (not a directory page)
    return bool(web) and urlparse(web).netloc.split(".")[-2:] == srch.split(".")[-2:]

# ---------- per company ----------
def showroom_of(r):
    for u in [r.get("contact"), r.get("via")] + (r.get("src") or []):
        m = re.search(r"https?://([a-z0-9\-]+)\.en\.made-in-china\.com", u or "")
        if m: return m.group(1)
    return None

DIRECTORY = re.compile(r"tradewheel\.com|sourceready\.com|b2brazil\.com|source\.reevol\.com|ec21\.com|globalsources\.com|freshdi\.com")

def scan(r):
    res = {"emails": [], "wa": None, "wc": None, "phone": None, "web": r.get("web"), "staff": []}
    seen = set()
    def take(found, src, own):
        for e in found["emails"]:
            if email_ok(e, src, res["web"] if own else None) and e not in [x["v"] for x in res["emails"]]:
                res["emails"].append({"v": e, "src": src})
        for p in found["staff"]:
            if p["email"] and not email_ok(p["email"], src, res["web"] if own else None): p["email"] = None
            if not (p["name"] or p["email"]): continue
            if not any((p["name"] and p["name"] == q["name"]) or (p["email"] and p["email"] == q["email"]) for q in res["staff"]):
                res["staff"].append({k: v for k, v in p.items() if v})
        for k in ("wa", "wc", "phone"):
            if found[k] and not res[k]: res[k] = {"v": found[k], "src": src}
    def visit(url, own, kind, follow=True):
        if not url or url in seen or len(seen) > 14: return None
        seen.add(url)
        h = get(url, kind)
        if not h: return None
        f = extract(h, url)
        take(f, url, own)
        if follow:
            for l in f["links"][:4]:
                visit(l, own, kind, follow=False)
        return f
    sub = showroom_of(r)
    if sub:
        base = f"https://{sub}.en.made-in-china.com"
        for p in ("/contact-info.html", "/company-info.html"):
            f = visit(base + p, False, "showroom" + p, follow=False)
            if f and f["web"] and not res["web"]: res["web"] = f["web"]
    for u in [r.get("contact")] + (r.get("src") or []):
        if u and DIRECTORY.search(u):
            if "source.reevol.com" in u and "/suppliers/" in u:
                md = get(u.rstrip("/") + "/ai-card.md", "reevol")
                if md:
                    m = re.search(r"^- Website:\s*(\S+)", md, re.M)
                    if m and m.group(1).startswith("http") and not res["web"]: res["web"] = m.group(1)
                    take(extract("<pre>" + md + "</pre>", u), u, False)
            else:
                f = visit(u, False, "directory", follow=False)
                if f and f["web"] and not res["web"]: res["web"] = f["web"]
    if res["web"]:
        visit(res["web"], True, "official")
        w = res["web"].rstrip("/")
        if not res["emails"] or not res["wa"] or not res["wc"]:
            for p in ("/contact", "/contact-us", "/contact.html", "/contactus.html", "/contact-us.html", "/en/contact.html"):
                if len(seen) > 12: break
                visit(w + p, True, "official", follow=False)
    # Emails on the company's own domain first, then free mail; at most 6.
    dom = urlparse(res["web"]).netloc.split(".")[-2:] if res["web"] else None
    res["emails"].sort(key=lambda x: (x["v"].split("@")[1].split(".")[-2:] != dom, bool(FREEMAIL.search(x["v"]))))
    res["emails"] = res["emails"][:6]
    res["staff"] = res["staff"][:12]
    out = {k: v for k, v in res.items() if v}
    if out.get("web") == r.get("web"): out.pop("web", None)
    return r["id"], out

def main():
    rows = json.load(open(f"{ROOT}/data/factories.json")) + json.load(open(f"{ROOT}/data/helmets.json"))
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    if only: rows = [r for r in rows if r["id"] in only]
    if "--sample" in sys.argv: rows = rows[:12] + [r for r in rows if r.get("kind") == "helmet"][:6]
    out, n = {}, len(rows)
    with ThreadPoolExecutor(6) as ex:
        for i, (fid, c) in enumerate(ex.map(scan, rows), 1):
            if c: out[fid] = c
            print(f"[{i}/{n}] {fid}: " + ", ".join(k + ("=" + str(len(v)) if k == "emails" else "") for k, v in c.items()), file=sys.stderr, flush=True)
    seen = collections.Counter()
    for c in out.values():
        for k in ("wa", "wc", "phone"):
            if c.get(k): seen[re.sub(r"\D", "", c[k]["v"]) or c[k]["v"]] += 1
        for e in c.get("emails", []): seen[e["v"]] += 1
    shared = {v for v, n in seen.items() if n > 1}
    for fid, c in list(out.items()):
        for k in ("wa", "wc", "phone"):
            if c.get(k) and (re.sub(r"\D", "", c[k]["v"]) or c[k]["v"]) in shared: print("  shared, dropped", fid, k, c[k]["v"], file=sys.stderr); c.pop(k)
        if c.get("emails"): c["emails"] = [e for e in c["emails"] if e["v"] not in shared]
        for p in c.get("staff", []):
            if p.get("email") in shared: p.pop("email")
        out[fid] = {k: v for k, v in c.items() if v}
        if not out[fid]: out.pop(fid)
    json.dump(out, open(f"{ROOT}/data/contacts.json", "w"), ensure_ascii=False, indent=1, sort_keys=True)
    if DEBUG:
        import os
        os.makedirs(f"{ROOT}/debug", exist_ok=True)
        with open(f"{ROOT}/debug/samples.txt", "w") as fh:
            for kind, xs in SAMPLES.items():
                for u, h in xs:
                    fh.write(f"\n\n===== {kind} {u}\n" + (h if kind == "anchors" else page_text(BeautifulSoup(h, "html.parser"))[:6000]))
    # coverage, existing hand-checked data included
    def has(r, k):
        c = out.get(r["id"], {})
        if k == "emails": return bool(r.get("emails") or c.get("emails"))
        return bool(r.get(k) or c.get(k))
    for kind, label in (("moto", "Motorcycle factories"), ("helmet", "Helmet companies")):
        rs = [r for r in rows if (r.get("kind") == "helmet") == (kind == "helmet")]
        print(f"\n**{label}: {len(rs)}**  ")
        print(f"- Staff names / market contacts: {sum(bool(out.get(r['id'], {}).get('staff')) for r in rs)}  ")
        for k, name in (("emails", "Email"), ("wa", "WhatsApp"), ("wc", "WeChat"), ("phone", "Phone")):
            print(f"- {name}: {sum(has(r, k) for r in rs)}  ")
        print(f"- Any contact: {sum(any(has(r, k) for k in ('emails','wa','wc','phone')) for r in rs)}  ")
    print("\nRefused / blocked pages:", len(BLOCKED))

if __name__ == "__main__":
    main()
