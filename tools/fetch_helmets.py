"""Collect Chinese motorcycle helmet manufacturers and their helmets from made-in-china.com.

Runs in GitHub Actions (the cloud sandbox can't reach these sites). Respects robots.txt and
never retries a page that refused us.

1. Supplier listings (/manufacturers/<keyword>_<page>.html) give each company's showroom,
   business type, main products, staff and a company photo.
2. Each showroom's company-info page gives province, city, address and founding year.
3. Its product list pages give the helmets: title, photo, FOB price, MOQ.
   A helmet is "ECE" when its listing names ECE / R22.05 / R22.06, otherwise "Non-ECE"
   with what it does claim (DOT, CCC, EN1078) or "not stated".

Writes data/helmets.json (same shape as factories.json, eec = ECE helmets, non = other helmets)
and data/helmet_photos.json (same shape as photos.json).
"""
import json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import threading

import requests
from bs4 import BeautifulSoup

ROOT = __file__.rsplit("/tools/", 1)[0]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
KEYWORDS = ["motorcycle-helmet", "motorcycle-helmets", "motorbike-helmet", "ece-helmet", "dot-helmet", "full-face-helmet",
            "modular-helmet", "flip-up-helmet", "open-face-helmet", "half-face-helmet", "motocross-helmet", "off-road-helmet",
            "kids-motorcycle-helmet", "carbon-fiber-helmet", "helmet-motorcycle", "scooter-helmet", "racing-helmet", "dot-ece-helmet"]
MAX_PAGES = 20
MAX_PRODUCT_PAGES = 3
MAX_MODELS = 40
LOCK = threading.Lock()
_robots, BLOCKED = {}, set()

def allowed(url):
    base = "{0.scheme}://{0.netloc}".format(urlparse(url))
    with LOCK:
        if base not in _robots:
            rp = RobotFileParser()
            try:
                r = requests.get(base + "/robots.txt", headers=H, timeout=15)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except Exception:
                rp.parse([])
            _robots[base] = rp
        return _robots[base].can_fetch(UA, url)

def get(url):
    if url in BLOCKED: return None
    if not allowed(url):
        print("  robots.txt disallows", url, file=sys.stderr); return None
    for i in range(2):
        try:
            r = requests.get(url, headers=H, timeout=30)
        except Exception as e:
            print("  fail", url, type(e).__name__, file=sys.stderr); time.sleep(3); continue
        time.sleep(0.6)
        if r.status_code in (403, 429):
            BLOCKED.add(url); print("  refused", r.status_code, url, file=sys.stderr); return None
        if r.status_code == 404: return None
        if r.status_code == 200:
            if re.search(r"slide to verify|captcha", r.text[:30000], re.I) and len(r.text) < 40000:
                BLOCKED.add(url); print("  captcha", url, file=sys.stderr); return None
            return r.text
        time.sleep(4)
    return None

txt = lambda el: re.sub(r"\s+", " ", el.get_text(" ", strip=True)).replace("‪", "").replace("‬", "").strip() if el else ""
img_src = lambda im: next((im.get(a) for a in ("data-original", "data-src", "src") if im.get(a) and "micstatic.com" not in im.get(a) and not im.get(a).startswith("data:")), None)
absu = lambda u: ("https:" + u) if u and u.startswith("//") else u
full = lambda u: re.sub(r"(image\.made-in-china\.com/)\d+f\d+j\d\d", r"\g<1>2f0j00", u or "")

def field(text, label, stop=r"(?:Business Type|Main Products|R&D Capacity|Fast Delivery|Year of Establishment|Number of Employees|Address|Plant Area|OEM/ODM|Sample Available|Rating|Request Free|Send Inquiry|Visit My Factory|Management System|Average Response|SGS)"):
    m = re.search(re.escape(label) + r"\s*:?\s*(.+?)\s*(?=" + stop + r"\s*:?|$)", text)
    return m.group(1).strip(" ,") if m else ""

MOTO = re.compile(r"motor|moto|full.?face|modular|flip|motocross|off.?road|open.?face|scooter|\bDOT\b|\bECE\b|racing helmet|casco", re.I)
NOT_MOTO = re.compile(r"hard hat|construction|industrial|mining|miner|firefight|police|military|bulletproof|ballistic|welding|riot|tactical", re.I)

def listing(kw):
    """All supplier blocks for one keyword, page by page."""
    out = []
    for p in range(1, MAX_PAGES + 1):
        url = f"https://www.made-in-china.com/manufacturers/{kw}{'' if p == 1 else f'_{p}'}.html"
        h = get(url)
        if not h: break
        s = BeautifulSoup(h, "html.parser")
        nodes = s.select(".list-node")
        if not nodes: break
        for n in nodes:
            sub = None
            for a in n.find_all("a", href=True):
                m = re.match(r"(?:https?:)?//([\w-]+)\.en\.made-in-china\.com", a["href"])
                if m and m.group(1) not in ("www",): sub = m.group(1); break
            if not sub: continue
            name = txt(n.select_one(".company-name-link") or n.select_one(".company-name"))
            t = txt(n)
            prods = []
            for a in n.find_all("a", href=True):
                if "/product/" not in a["href"]: continue
                im = a.find("img") or (a.find_parent() and a.find_parent().find("img"))
                title = (im.get("alt") if im else "") or a.get("title") or ""
                prods.append({"t": title, "url": absu(a["href"]), "img": absu(img_src(im)) if im else None, "price": txt(a)})
            co_imgs = [absu(img_src(im)) for im in n.find_all("img") if img_src(im) and norm(im.get("alt", "")) == norm(name)]
            out.append({"sub": sub, "name": name, "bt": field(t, "Business Type"), "main": field(t, "Main Products"),
                        "emp": (re.search(r"(\d[\d,+-]*)\s*Number of Employees", t) or [None, None])[1],
                        "area": ((re.search(r"(\d[\d,+-]*)\s*(?:square meters|m2|㎡)?\s*Plant Area", t) or [None, None])[1] or "").strip() or None,
                        "tour": next((absu(a["href"]) for a in n.find_all("a", href=True) if "360-Virtual-Tour" in a["href"]), None),
                        "co_imgs": [u for u in dict.fromkeys(co_imgs) if u], "prods": prods, "kw": kw})
        total = s.select_one(".page-total")
        if total and txt(total).isdigit() and p >= int(txt(total)): break
    print(f"{kw}: {len(out)} supplier rows", file=sys.stderr)
    return out

def norm(x):
    return re.sub(r"[^a-z0-9]", "", (x or "").lower())

def is_helmet_company(r):
    blob = r["main"] + " " + " ".join(p["t"] for p in r["prods"])
    if NOT_MOTO.search(r["main"]) and not re.search(r"motor", r["main"], re.I): return False
    return "helmet" in r["main"].lower() and MOTO.search(blob) is not None

PROVS = ["Zhejiang", "Guangdong", "Jiangsu", "Fujian", "Shandong", "Chongqing", "Shanghai", "Hebei", "Henan", "Anhui", "Hunan", "Hubei",
         "Jiangxi", "Tianjin", "Beijing", "Sichuan", "Liaoning", "Shanxi", "Shaanxi", "Guangxi", "Yunnan", "Guizhou", "Hainan", "Jilin",
         "Heilongjiang", "Inner Mongolia", "Gansu", "Xinjiang", "Ningxia", "Qinghai", "Tibet", "Hong Kong", "Taiwan"]

def company_info(sub):
    h = get(f"https://{sub}.en.made-in-china.com/company-info.html") or get(f"https://{sub}.en.made-in-china.com")
    if not h: return {}
    s = BeautifulSoup(h, "html.parser")
    for x in s(["script", "style", "noscript"]): x.decompose()
    t = txt(s)
    addr = field(t, "Address")
    prov = next((p for p in PROVS if re.search(r"\b" + p + r"\b", addr)), None) or next((p for p in PROVS if re.search(r"\b" + p + r", China", t)), None)
    city = None
    if addr:
        parts = [x.strip() for x in addr.split(",")]
        # "..., Yueqing City, Wenzhou, Zhejiang, China" -> Wenzhou (the part before the province)
        if prov and prov in parts:
            i = parts.index(prov)
            if i > 0: city = re.sub(r"\s*(City|Shi)$", "", parts[i - 1])
        if not city:
            m = re.search(r"([A-Z][a-z]+)\s+City", addr)
            city = m.group(1) if m else None
    yr = re.search(r"(19\d\d|20[0-2]\d)", field(t, "Year of Establishment"))
    about = ""
    for p in s.find_all(["p", "div"]):
        x = txt(p)
        if 150 < len(x) < 900 and re.search(r"(found|establish|located|professional|manufactur)", x, re.I) and "Main Products" not in x:
            about = x; break
    return {"addr": addr or None, "prov": prov, "city": city, "since": int(yr.group(1)) if yr else None,
            "emp": field(t, "Number of Employees") or None, "bt": field(t, "Business Type"), "main": field(t, "Main Products"), "about": about}

ECE = re.compile(r"\bECE\b|\bR\s?22|22[.\-\s]?0[56]\b|\b220[56]\b", re.I)
def cert_of(title):
    if ECE.search(title):
        if re.search(r"22[.\-\s]?06|2206", title): return "ECE 22.06"
        if re.search(r"22[.\-\s]?05|2205", title): return "ECE 22.05"
        return "ECE"
    for k, rx in (("DOT", r"\bDOT\b"), ("CCC", r"\bCCC\b|\b3C\b"), ("EN1078", r"EN\s?1078|\bCE\b"), ("SNELL", r"\bSNELL\b")):
        if re.search(rx, title, re.I): return k
    return None

HTYPES = [("Modular / flip-up", r"modular|flip|flip-up|flip up"), ("Motocross / off-road", r"motocross|off.?road|cross.?country|\bMX\b|dirt|enduro|ATV"),
          ("Open face (3/4)", r"open.?face|3/4|three.?quarter|jet"), ("Half face", r"half.?face|half helmet|half-helmet"),
          ("Kids", r"\bkids?\b|child|children|youth|toddler"), ("Retro", r"retro|vintage"), ("Bluetooth / smart", r"bluetooth|intercom|smart|\bLED\b"),
          ("Carbon fiber", r"carbon"), ("Full face", r"full.?face|integral|racing")]
def htypes(title):
    return [k for k, rx in HTYPES if re.search(rx, title, re.I)]

def price(s):
    m = re.search(r"US\s?\$\s?([\d.]+)(?:\s*-\s*([\d.]+))?", s or "")
    if not m: return None
    lo = float(m.group(1)); hi = float(m.group(2)) if m.group(2) else lo
    return [lo, hi] if lo > 0 else None
def moq(s):
    m = re.search(r"([\d,]+)\s*(?:Pieces?|Pcs|Sets?|Units?)\s*\(?\s*(?:MOQ|Min)", s or "", re.I) or re.search(r"Min\. Order:\s*([\d,]+)", s or "")
    return int(m.group(1).replace(",", "")) if m else None

def products(sub, seed):
    items, seen = [], set()
    for p in range(1, MAX_PRODUCT_PAGES + 1):
        h = get(f"https://{sub}.en.made-in-china.com/product-list-{p}.html")
        if not h: break
        s = BeautifulSoup(h, "html.parser")
        cards = s.select(".prod-result-item") or s.select(".prod-item, .product-item, li.item")
        if not cards: break
        for c in cards:
            a = next((a for a in c.find_all("a", href=True) if "/product/" in a["href"]), None)
            im = c.find("img")
            if not a or not im: continue
            title = (im.get("alt") or im.get("title") or a.get("title") or "").strip()
            u = absu(a["href"]).split("?")[0]
            if u in seen or "helmet" not in title.lower(): continue
            seen.add(u); t = txt(c)
            items.append({"t": title, "url": u, "img": absu(img_src(im)), "usd": price(t), "moq": moq(t), "extra": t})
        if len(items) >= MAX_MODELS: break
    for x in seed:  # helmets shown on the supplier listing, if the showroom pages gave none
        if x["url"] and x["url"].split("?")[0] not in seen and "helmet" in x["t"].lower():
            seen.add(x["url"].split("?")[0])
            items.append({"t": x["t"], "url": x["url"].split("?")[0], "img": x["img"], "usd": price(x["price"]), "moq": moq(x["price"]), "extra": ""})
    return items[:MAX_MODELS]

def slug(name, sub):
    s = re.sub(r"\b(co|ltd|limited|company|corporation|inc|industry|industrial|trading|technology|tech|manufacturing|import|export|and|&)\b", " ", name.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40].strip("-")
    return "h-" + (s or sub)

def build(r):
    info = company_info(r["sub"])
    items = products(r["sub"], r["prods"])
    if not items: return None
    showroom = f"https://{r['sub']}.en.made-in-china.com"
    ece, non, ph_prod, models, types = [], [], [], {}, set()
    for x in items:
        c = cert_of(x["t"])  # the title is what the factory claims for this helmet
        ty = htypes(x["t"]) or ["Full face"]
        types.update(ty)
        m = {"n": x["t"][:120], "cert": c, "ty": ty, "usd": x["usd"], "moq": x["moq"], "url": x["url"]}
        (ece if c and c.startswith("ECE") else non).append(m)
        if x["img"]:
            ph = {"u": full(x["img"]), "t": x["img"], "alt": x["t"][:140], "from": x["url"]}
            ph_prod.append(ph); models[m["n"]] = ph["u"]
    bt = info.get("bt") or r["bt"]
    btn = "Manufacturer" if "Manufacturer" in bt and "Trading" not in bt else ("Trading company" if bt == "Trading Company" else ("Manufacturer & trading" if "Manufacturer" in bt else "Not stated"))
    prices = [m["usd"][0] for m in ece + non if m["usd"]]
    f = {"id": slug(r["name"], r["sub"]), "kind": "helmet", "name": r["name"], "legal": r["name"],
         "city": info.get("city") or info.get("prov") or "China", "prov": info.get("prov") or "Not stated",
         "since": info.get("since"), "emp": info.get("emp") or r["emp"], "cap": None, "area": r["area"], "markets": None, "web": None,
         "contact": showroom, "addr": info.get("addr"), "about": info.get("about") or None, "emails": [], "emailNotes": [], "phone": None, "wa": None, "wc": None,
         "types": sorted(types), "cc": None, "eec": ece, "non": non, "usd": [min(prices), max(prices)] if prices else None,
         "src": [showroom, f"https://www.made-in-china.com/manufacturers/{r['kw']}.html"], "notes": None,
         "products": info.get("main") or r["main"], "bt": btn, "via": "made-in-china.com", "tier": "basic", "tour": r["tour"],
         "sky": ["#5a1030", "#c4608c"], "c": "#b8155e"}
    fact = [{"u": full(u), "t": u, "alt": r["name"], "from": showroom} for u in r["co_imgs"][:4]]
    hero = [p["u"] for p in ph_prod[:3]]
    photos = {"page": showroom, "products": ph_prod, "factory": fact, "hero": hero, "models": models, "at": time.strftime("%Y-%m-%d")}
    return f, photos

def main():
    rows = {}
    with ThreadPoolExecutor(3) as ex:
        for out in ex.map(listing, KEYWORDS):
            for r in out:
                if r["sub"] in rows:
                    rows[r["sub"]]["prods"] += r["prods"]
                    if not rows[r["sub"]]["tour"]: rows[r["sub"]]["tour"] = r["tour"]
                else:
                    rows[r["sub"]] = r
    keep = [r for r in rows.values() if is_helmet_company(r)]
    if "--rows" in sys.argv:
        json.dump([{k: r[k] for k in ("sub", "name", "bt", "main", "kw")} | {"n": len(r["prods"]), "t": [p["t"] for p in r["prods"][:3]], "keep": r in keep} for r in rows.values()],
                  open(f"{ROOT}/data/helmet_rows.json", "w"), ensure_ascii=False, indent=0)
        return
    print(f"SUMMARY: {len(rows)} suppliers listed, {len(keep)} make motorcycle helmets", file=sys.stderr)
    res, photos, ids = [], {}, set()
    with ThreadPoolExecutor(4) as ex:
        for r, b in zip(keep, ex.map(build, keep)):
            if not b: continue
            f, ph = b
            base, i = f["id"], 2
            while f["id"] in ids: f["id"] = f"{base}-{i}"; i += 1
            ids.add(f["id"]); res.append(f); photos[f["id"]] = ph
    res.sort(key=lambda f: (-len(f["eec"]), f["name"]))
    json.dump(res, open(f"{ROOT}/data/helmets.json", "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump(photos, open(f"{ROOT}/data/helmet_photos.json", "w"), ensure_ascii=False, separators=(",", ":"))
    n_ece = sum(len(f["eec"]) for f in res); n_non = sum(len(f["non"]) for f in res)
    print(f"SUMMARY: {len(res)} helmet factories · {sum(1 for f in res if f['eec'])} with ECE helmets · {n_ece} ECE helmets · {n_non} non-ECE helmets · {sum(1 for f in res if f['prov'] != 'Not stated')} with province")

if __name__ == "__main__":
    main()
