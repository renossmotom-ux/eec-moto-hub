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
            "kids-motorcycle-helmet", "carbon-fiber-helmet", "helmet-motorcycle", "scooter-helmet", "racing-helmet", "dot-ece-helmet",
            "helmet", "helmets", "moto-helmet", "abs-helmet", "fiberglass-helmet", "dual-visor-helmet", "bluetooth-helmet", "retro-helmet",
            "vintage-helmet", "electric-bike-helmet", "electric-scooter-helmet", "casco-moto", "ece-22-06-helmet", "dot-approved-helmet",
            "motorcycle-helmet-ece", "cross-helmet", "dirt-bike-helmet", "jet-helmet", "helmet-visor", "smart-helmet"]
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

def parse_nodes(h, kw):
    """Supplier blocks on a listing page: /manufacturers/, /company-search/ (.list-node) or /factory/ (.company-item)."""
    s = BeautifulSoup(h, "html.parser")
    out = []
    for n in s.select(".list-node, .company-item"):
        sub = None
        for a in n.find_all("a", href=True):
            m = re.match(r"(?:https?:)?//([\w-]+)\.en\.made-in-china\.com", a["href"])
            if m and m.group(1) != "www": sub = m.group(1); break
        if not sub: continue
        name = txt(n.select_one(".company-name-link") or n.select_one(".company-name"))
        if not name:
            name = next((txt(a) for a in n.find_all("a") if re.search(r"\b(Co|Ltd|Limited|Inc|Company|Corp|Factory|Group)\b", txt(a)) and len(txt(a)) < 120), "")
        if not name: continue
        t = txt(n)
        prods = []
        for a in n.find_all("a", href=True):
            if "/product/" not in a["href"]: continue
            im = a.find("img") or (a.find_parent() and a.find_parent().find("img"))
            title = (im.get("alt") if im else "") or a.get("title") or ""
            prods.append({"t": title, "url": absu(a["href"]), "img": absu(img_src(im)) if im else None, "price": txt(a)})
        co_imgs = [absu(img_src(im)) for im in n.find_all("img") if img_src(im) and norm(im.get("alt", "")) == norm(name)]
        out.append({"sub": sub, "name": name, "bt": field(t, "Business Type") or (re.search(r"(Manufacturer/Factory(?: & Trading Company)?|Trading Company)", t) or [None, ""])[1],
                    "main": field(t, "Main Products", r"(?:Country/Region|R&D Capacity|Business Type|Fast Delivery|Sample Service|Company Profile|Year of Establishment|Number of Employees|Address|Plant Area|Request Free|Send Inquiry)"),
                    "emp": (re.search(r"(\d[\d,+-]*)\s*Number of Employees", t) or [None, None])[1],
                    "area": ((re.search(r"(\d[\d,+-]*)\s*(?:square meters|m2|㎡)?\s*Plant Area", t) or [None, None])[1] or "").strip() or None,
                    "tour": next((absu(a["href"]) for a in n.find_all("a", href=True) if "360-Virtual-Tour" in a["href"]), None),
                    "co_imgs": [u for u in dict.fromkeys(co_imgs) if u], "prods": prods, "kw": kw})
    total = s.select_one(".page-total")
    return out, int(txt(total)) if total and txt(total).isdigit() else None

def paged(kw, url_of, max_pages=MAX_PAGES):
    out, seen = [], set()
    for p in range(1, max_pages + 1):
        h = get(url_of(p))
        if not h: break
        rows, total = parse_nodes(h, kw)
        fresh = [r for r in rows if r["sub"] not in seen]
        if not fresh: break
        seen.update(r["sub"] for r in fresh); out += fresh
        if total and p >= total: break
    return out

def listing(kw):
    """All supplier blocks for one keyword: the supplier list, the verified-factory page, and the per-province company search."""
    out = paged(kw, lambda p: f"https://www.made-in-china.com/manufacturers/{kw}{'' if p == 1 else f'_{p}'}.html")
    h = get(f"https://www.made-in-china.com/factory/{kw}.html")
    if h: out += parse_nodes(h, kw)[0]
    print(f"{kw}: {len(out)} supplier rows", file=sys.stderr)
    return out

# made-in-china's verified-factory pages (/factory/<slug>.html) for helmet words: mostly helmet specialists.
FACTORY_SLUGS = ["ece-helmets", "helmets-ece", "ece-dot-helmets", "dot-ece-helmet", "dot-helmets", "dot-approved-helmets", "ece-casco",
                 "helmets-cross-ece", "open-helmets", "offroad-helmet", "abs-helmets", "open-half-helmets", "atv-helmets", "full-face-helmets",
                 "double-visor", "full-helmets", "half-helmets", "open-face-helmets", "halley-helmets", "pp-helmets", "eps-shell",
                 "modular-helmets", "summer-helmets", "new-helmets", "are-helmets", "kask", "motorcycle-helmets", "helmets", "kids-helmets",
                 "motocross-helmets", "flip-up-helmets", "racing-helmets", "carbon-helmets", "carbon-fiber-helmets", "vintage-helmets",
                 "retro-helmets", "bluetooth-helmets", "dirt-bike-helmets", "casco", "cascos", "casco-moto", "moto-helmets", "helmet-factory",
                 "helmet-manufacturer", "dual-visor-helmets", "jet-helmets", "half-face-helmets", "full-face-helmet", "motorcycle-helmet-factory",
                 "off-road-helmets", "cross-helmets", "fiberglass-helmets", "helmet-shell", "helmet-visor", "helmet-liner", "ece-2206-helmet",
                 "ece-22-06-helmets", "scooter-helmets", "electric-scooter-helmets", "motorbike-helmets", "helmet-moto", "capacete",
                 "kids-motorcycle-helmets", "children-helmets", "adult-helmets", "street-helmets", "sport-helmets", "touring-helmets",
                 "adventure-helmets", "dual-sport-helmets", "smart-helmets", "led-helmets", "motorcycle-helmet-ece", "helmets-dot"]

def factory_page(slug):
    h = get(f"https://www.made-in-china.com/factory/{slug}.html")
    rows = parse_nodes(h, slug)[0] if h else []
    print(f"factory {slug}: {len(rows)} suppliers", file=sys.stderr)
    return rows

PRODUCT_TERMS = ["Motorcycle_Helmet", "Motorcycle_Helmets", "Motorcycle_Helmet_Factory", "Motorcycle_Helmet_Price", "Motorcycle_Helmet_Manufacturer",
                 "Motorcycle_Helmet_Wholesale", "Motorcycle_Helmet_Ece", "Motorcycle_Helmet_DOT", "Ece_Motorcycle_Helmet", "DOT_Motorcycle_Helmet",
                 "Full_Face_Motorcycle_Helmet", "Open_Face_Motorcycle_Helmet", "Half_Face_Motorcycle_Helmet", "Modular_Motorcycle_Helmet",
                 "Motorcycle_Helmet_with_Bluetooth", "Children_Motorcycle_Helmet", "Electric_Scooter_Helmet", "Moto_Helmet", "Casco_Moto",
                 "Helmet", "Full_Face_Helmet", "Modular_Helmet", "Flip_up_Helmet", "Open_Face_Helmet",
                 "Half_Face_Helmet", "Motocross_Helmet", "Off_Road_Helmet", "Ece_Helmet", "DOT_Helmet", "Kids_Motorcycle_Helmet", "Racing_Helmet",
                 "Carbon_Fiber_Helmet", "Fiberglass_Helmet", "Retro_Helmet", "Scooter_Helmet", "Motorbike_Helmet", "Dual_Visor_Helmet"]

def product_search(term, max_pages=30):
    """Product search pages (<term>.html, <term>-2.html, ...): every helmet listing names its supplier's showroom.
    Only finds showrooms; company facts come from company_info."""
    out = {}
    stale = 0
    for p in range(1, max_pages + 1):
        h = get(f"https://www.made-in-china.com/products-search/hot-china-products/{term}{'' if p == 1 else f'-{p}'}.html")
        if not h: break
        s = BeautifulSoup(h, "html.parser")
        before = len(out)
        for a in s.find_all("a", href=True):
            m = re.match(r"(?:https?:)?//([\w-]+)\.en\.made-in-china\.com/product/", a["href"])
            if not m: continue
            im = a.find("img")
            title = (im.get("alt") if im else "") or a.get("title") or txt(a)
            if not moto_helmet(title): continue
            r = out.setdefault(m.group(1), {"sub": m.group(1), "name": "", "bt": "", "main": "", "emp": None, "area": None, "tour": None, "co_imgs": [], "prods": [], "kw": term, "via_products": True})
            r["prods"].append({"t": title, "url": absu(a["href"]).split("?")[0], "img": absu(img_src(im)) if im else None, "price": ""})
        stale = stale + 1 if len(out) == before else 0
        if stale >= 2: break
    print(f"products {term}: {len(out)} suppliers on {p} pages", file=sys.stderr)
    return list(out.values())

def norm(x):
    return re.sub(r"[^a-z0-9]", "", (x or "").lower())

NOT_HELMET = re.compile(r"bag|clean|machine|bluetooth|intercom|headset|headphone|earphone|walkie|decal|sticker|logo|badge|paint|line|mould|mold|"
                        r"safety helmet|hard hat|bump cap|welding|riot|ballistic|tactical|military|police|pad|ski|snow|bicycle|bike helmet|skate|equestrian|horse|climb|cycling|lock|holder|hook|camera", re.I)
SELLER_NOT = re.compile(r"clean|bluetooth|intercom|headphone|earphone|headset|sunglass|goggle|rack|tent|awning|LED|bag|box|vending|bicycle|e-?bike|electric bike|kick scooter|children|toy|fitness", re.I)
RIDING = re.compile(r"motor|moto|scooter|riding|rider|atv|dirt|racing|helmet", re.I)

def helmet_maker(main):
    """Main products name a real motorcycle helmet (not a helmet bag, cleaner, intercom, hard hat...)."""
    return any("helmet" in x.lower() and not NOT_HELMET.search(x) for x in re.split(r"[,;/]", main))

def is_helmet_company(r):
    """"maker" for helmet makers, "seller" for motorcycle parts / riding gear companies that also list motorcycle helmets."""
    blob = r["main"] + " " + " ".join(p["t"] for p in r["prods"])
    if NOT_MOTO.search(r["main"]) and not re.search(r"motor", r["main"], re.I): return None
    if helmet_maker(r["main"]) and MOTO.search(blob): return "maker"
    # Helmet specialists whose name says so ("Wenzhou ... Helmet Co.") and who list helmets.
    if re.search(r"helmet", r["name"], re.I) and not NOT_HELMET.search(r["name"]) and r["prods"]: return "maker"
    if (re.search(r"motor|moto|riding gear|\bATV\b|dirt", r["main"], re.I) and not SELLER_NOT.search(r["main"])
            and sum(bool(moto_helmet(p["t"])) for p in r["prods"]) >= 1): return "seller"
    return None

def moto_helmet(title):
    return "helmet" in title.lower() and MOTO.search(title) and not re.search(r"tactical|riot|ballistic|military|police|welding|hard hat|construction|bag|cleaning|machine|mould|mold|decal|sticker|lock|holder|intercom|headset|camera|paragliding|equestrian|ski\b", title, re.I)

PROVS = ["Zhejiang", "Guangdong", "Jiangsu", "Fujian", "Shandong", "Chongqing", "Shanghai", "Hebei", "Henan", "Anhui", "Hunan", "Hubei",
         "Jiangxi", "Tianjin", "Beijing", "Sichuan", "Liaoning", "Shanxi", "Shaanxi", "Guangxi", "Yunnan", "Guizhou", "Hainan", "Jilin",
         "Heilongjiang", "Inner Mongolia", "Gansu", "Xinjiang", "Ningxia", "Qinghai", "Tibet", "Hong Kong", "Taiwan"]

def company_info(sub):
    h = get(f"https://{sub}.en.made-in-china.com/company-info.html") or get(f"https://{sub}.en.made-in-china.com")
    if not h: return {}
    s = BeautifulSoup(h, "html.parser")
    title = txt(s.title) if s.title else ""
    for x in s(["script", "style", "noscript"]): x.decompose()
    t = txt(s)
    name = title.split(" - ", 1)[1].strip() if title.startswith("Company Overview") and " - " in title else None
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
    return {"name": name, "addr": addr or None, "prov": prov, "city": city, "since": int(yr.group(1)) if yr else None,
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
            if u in seen or not moto_helmet(title): continue
            seen.add(u); t = txt(c)
            items.append({"t": title, "url": u, "img": absu(img_src(im)), "usd": price(t), "moq": moq(t), "extra": t})
        if len(items) >= MAX_MODELS: break
    for x in seed:  # helmets shown on the supplier listing, if the showroom pages gave none
        if x["url"] and x["url"].split("?")[0] not in seen and moto_helmet(x["t"]):
            seen.add(x["url"].split("?")[0])
            items.append({"t": x["t"], "url": x["url"].split("?")[0], "img": x["img"], "usd": price(x["price"]), "moq": moq(x["price"]), "extra": ""})
    return items[:MAX_MODELS]

def slug(name, sub):
    s = re.sub(r"\b(co|ltd|limited|company|corporation|inc|industry|industrial|trading|technology|tech|manufacturing|import|export|and|&)\b", " ", name.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40].strip("-")
    return "h-" + (s or sub)

def build(r):
    info = r.get("info") or company_info(r["sub"])
    items = products(r["sub"], r["prods"])
    if len(items) < (2 if r["tierk"] == "maker" else 3): return None  # a real helmet supplier lists several motorcycle helmets
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
    name = info.get("name") or r["name"]
    f = {"id": slug(name, r["sub"]), "kind": "helmet", "name": name, "legal": name,
         "city": info.get("city") or info.get("prov") or "China", "prov": info.get("prov") or "Not stated",
         "since": info.get("since"), "emp": info.get("emp") or r["emp"], "cap": None, "area": r["area"], "markets": None, "web": None,
         "contact": showroom, "addr": info.get("addr"), "about": info.get("about") or None, "emails": [], "emailNotes": [], "phone": None, "wa": None, "wc": None,
         "types": sorted(types), "cc": None, "eec": ece, "non": non, "usd": [min(prices), max(prices)] if prices else None,
         "src": [showroom, f"https://www.made-in-china.com/manufacturers/{r['kw']}.html"], "notes": None,
         "products": info.get("main") or r["main"], "bt": btn, "via": "made-in-china.com", "tier": "basic", "tour": r["tour"], "maker": r["tierk"] == "maker",
         "sky": ["#5a1030", "#c4608c"], "c": "#b8155e"}
    fact = [{"u": full(u), "t": u, "alt": r["name"], "from": showroom} for u in r["co_imgs"][:4]]
    hero = [p["u"] for p in ph_prod[:3]]
    photos = {"page": showroom, "products": ph_prod, "factory": fact, "hero": hero, "models": models, "at": time.strftime("%Y-%m-%d")}
    return f, photos

# ---------- Reevol Source (source.reevol.com): supplier cards from business registries and trade-fair exhibitor lists ----------
# Its robots.txt allows crawlers (Crawl-delay: 5) and it publishes machine-readable cards at /en/suppliers/<slug>/ai-card.md.
REEVOL = "https://source.reevol.com"
_last_reevol = [0.0]

def reevol_get(url):
    if not allowed(url): print("  robots.txt disallows", url, file=sys.stderr); return None
    for i in range(3):
        wait = 5.2 - (time.time() - _last_reevol[0])
        if wait > 0: time.sleep(wait)
        _last_reevol[0] = time.time()
        try:
            r = requests.get(url, headers=H, timeout=30)
        except Exception as e:
            print("  fail", url, type(e).__name__, file=sys.stderr); continue
        if r.status_code == 429: time.sleep(30 * (i + 1)); continue
        return r.text if r.status_code == 200 else None
    return None

ZH = {"摩托头盔": "Motorcycle helmet", "电动车头盔": "E-bike / scooter helmet", "全盔": "Full face helmet", "半盔": "Half helmet", "3/4盔": "3/4 helmet",
      "揭面盔": "Flip-up helmet", "越野盔": "Off-road helmet", "儿童盔": "Kids helmet", "碳纤盔": "Carbon fiber helmet", "头盔": "Helmet", "复古盔": "Retro helmet",
      "安全帽": "Safety helmet", "骑行头盔": "Cycling helmet", "头盔镜片": "Helmet visor"}
ZH_TYPES = {"全盔": "Full face", "半盔": "Half face", "3/4盔": "Open face (3/4)", "揭面盔": "Modular / flip-up", "越野盔": "Motocross / off-road",
            "儿童盔": "Kids", "碳纤盔": "Carbon fiber", "复古盔": "Retro"}

def card_field(md, label):
    m = re.search(r"^- " + re.escape(label) + r":\s*(.+)$", md, re.M)
    return m.group(1).strip() if m else None

def reevol_card(slug):
    url = f"{REEVOL}/en/suppliers/{slug}/"
    md = reevol_get(url + "ai-card.md")
    if not md: return None
    subs = card_field(md, "Sub-industries") or ""
    summary = md.split("## Summary", 1)[1][:1500] if "## Summary" in md else ""
    blob = subs + " " + summary
    # Motorcycle / e-bike helmets only: not hard hats, bicycle or tactical helmets.
    if not (re.search(r"摩托头盔|电动车头盔|全盔|半盔|揭面盔|越野盔|3/4盔", subs) or re.search(r"motorcycle helmet|motorbike helmet|full[- ]face helmet|off-road helmet", blob, re.I)):
        return None
    name = card_field(md, "Legal name (en)") or slug.replace("-", " ").title()
    loc = card_field(md, "Location") or ""
    prov = next((p for p in PROVS if p.upper() in loc.upper()), None)
    m = re.search(r"based in ([A-Z][a-zA-Z ]+?), " + (prov or "China"), summary) or re.search(r"located in ([A-Z][a-zA-Z ]+?)(?: City)?,", md)
    city = m.group(1).strip() if m else (prov or "China")
    yr = card_field(md, "Year founded")
    words = [x.strip() for x in re.split(r"[,，]", subs) if x.strip()]
    products = ", ".join(dict.fromkeys(ZH.get(w, w) for w in words if re.search(r"盔|helmet", w, re.I)))
    types = sorted({ZH_TYPES[w] for w in words if w in ZH_TYPES}) or ["Full face"]
    bt = (card_field(md, "Business type") or "").lower()
    fairs = card_field(md, "Trade fairs")
    web = card_field(md, "Website")
    return {"id": "h-" + slug[:40].strip("-"), "kind": "helmet", "name": name, "legal": name, "zh": card_field(md, "Legal name (zh-CN)"),
            "city": city, "prov": prov or "Not stated", "since": int(yr) if yr and yr.isdigit() else None,
            "emp": (card_field(md, "Employee range") or "").replace("~", "–") or None, "cap": None, "area": None, "markets": None,
            "web": web if web and web.startswith("http") else None, "contact": url, "addr": None, "about": None,
            "emails": [], "emailNotes": [], "phone": None, "wa": None, "wc": None, "types": types, "cc": None, "eec": [], "non": [], "usd": None,
            "src": [url], "notes": ("Trade fairs: " + fairs) if fairs else None, "products": products or "Motorcycle helmets",
            "bt": "Manufacturer" if "manufacturer" in bt else ("Trading company" if "trad" in bt else "Not stated"), "via": "reevol",
            "tier": "basic", "tour": None, "maker": "manufacturer" in bt or not bt, "sky": ["#5a1030", "#c4608c"], "c": "#b8155e"}

HELMET_SLUG = re.compile(r"helmet|kask|casco|capacete")
MAYBE_SLUG = re.compile(r"motorcycle-fitting|motor-fitting|motorcycle-part|motorcycle-accessor|moto-fitting|safety-protect|sports-goods|sport-goods|protective")

def reevol_suppliers():
    slugs = []
    for i in range(2):
        xml = reevol_get(f"{REEVOL}/sitemap/suppliers/{i}.xml") or ""
        slugs += re.findall(r"/en/suppliers/([a-z0-9-]+)/</loc>", xml)
    slugs = list(dict.fromkeys(slugs))
    sure = [x for x in slugs if HELMET_SLUG.search(x)]
    maybe = [x for x in slugs if not HELMET_SLUG.search(x) and MAYBE_SLUG.search(x)][:350]
    print(f"reevol: {len(slugs)} suppliers in sitemap, {len(sure)} helmet names, {len(maybe)} other candidates", file=sys.stderr)
    out = []
    for slug in sure + maybe:
        f = reevol_card(slug)
        if f: out.append(f)
    print(f"reevol: {len(out)} motorcycle helmet companies", file=sys.stderr)
    return out

def main():
    rows = {}
    with ThreadPoolExecutor(4) as ex:
        for out in ex.map(listing, KEYWORDS):
            for r in out:
                if r["sub"] in rows:
                    rows[r["sub"]]["prods"] += r["prods"]
                    for k in ("main", "bt", "emp", "area"):
                        rows[r["sub"]][k] = rows[r["sub"]][k] or r[k]
                    if not rows[r["sub"]]["tour"]: rows[r["sub"]]["tour"] = r["tour"]
                else:
                    rows[r["sub"]] = r
    with ThreadPoolExecutor(4) as ex:
        for out in ex.map(factory_page, FACTORY_SLUGS):
            for r in out:
                if r["sub"] in rows:
                    rows[r["sub"]]["prods"] += r["prods"]
                    for k in ("main", "bt", "emp", "area"):
                        rows[r["sub"]][k] = rows[r["sub"]][k] or r[k]
                else:
                    rows[r["sub"]] = r
    with ThreadPoolExecutor(4) as ex:
        for out in ex.map(product_search, PRODUCT_TERMS):
            for r in out:
                if r["sub"] in rows: rows[r["sub"]]["prods"] += r["prods"]
                else: rows[r["sub"]] = r
    # Suppliers found only through product search: read their company page for name and main products.
    bare = [r for r in rows.values() if r.get("via_products") and not r["main"]][:3000]
    with ThreadPoolExecutor(4) as ex:
        for r, info in zip(bare, ex.map(lambda r: company_info(r["sub"]), bare)):
            r["info"] = info
            r["name"] = info.get("name") or r["name"] or r["sub"]
            r["main"] = info.get("main") or ""; r["bt"] = info.get("bt") or ""
    for r in rows.values(): r["tierk"] = is_helmet_company(r)
    keep = [r for r in rows.values() if r["tierk"]]
    if "--rows" in sys.argv:
        json.dump([{k: r[k] for k in ("sub", "name", "bt", "main", "kw")} | {"n": len(r["prods"]), "t": [p["t"] for p in r["prods"][:3]], "keep": r["tierk"]} for r in rows.values()],
                  open(f"{ROOT}/data/helmet_rows.json", "w"), ensure_ascii=False, indent=0)
    print(f"SUMMARY: {len(rows)} suppliers listed, {sum(r['tierk'] == 'maker' for r in keep)} helmet makers, {sum(r['tierk'] == 'seller' for r in keep)} sellers", file=sys.stderr)
    res, photos, ids = [], {}, set()
    with ThreadPoolExecutor(4) as ex:
        for r, b in zip(keep, ex.map(build, keep)):
            if not b: continue
            f, ph = b
            base, i = f["id"], 2
            while f["id"] in ids: f["id"] = f"{base}-{i}"; i += 1
            ids.add(f["id"]); res.append(f); photos[f["id"]] = ph
    # Reevol cards add helmet companies made-in-china doesn't list (no helmet list yet: the factory adds it when it claims the profile).
    res += reevol_suppliers()
    # One profile per company (some run two showrooms): keep the one with more helmets.
    best = {}
    for f in res:
        k = norm(re.sub(r"\b(co|ltd|limited)\b", "", f["name"].lower()))
        if k not in best or len(best[k]["eec"]) + len(best[k]["non"]) < len(f["eec"]) + len(f["non"]): best[k] = f
    res = [f for f in res if best.get(norm(re.sub(r"\b(co|ltd|limited)\b", "", f["name"].lower()))) is f]
    res.sort(key=lambda f: (not f["maker"], -len(f["eec"]), f["name"]))
    # Big brands checked by hand (data/helmet_brands.json) come first.
    brands = json.load(open(f"{ROOT}/data/helmet_brands.json"))
    res = brands + [f for f in res if f["id"] not in {b["id"] for b in brands}]
    seen_ids = set()
    for f in res:
        base, i = f["id"], 2
        while f["id"] in seen_ids: f["id"] = f"{base}-{i}"; i += 1
        seen_ids.add(f["id"])
    json.dump(res, open(f"{ROOT}/data/helmets.json", "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump(photos, open(f"{ROOT}/data/helmet_photos.json", "w"), ensure_ascii=False, separators=(",", ":"))
    n_ece = sum(len(f["eec"]) for f in res); n_non = sum(len(f["non"]) for f in res)
    print(f"SUMMARY: {len(res)} helmet factories · {sum(1 for f in res if f['eec'])} with ECE helmets · {n_ece} ECE helmets · {n_non} non-ECE helmets · {sum(1 for f in res if f['prov'] != 'Not stated')} with province")

def probe():
    """Save a few raw pages into debug/ to check page formats and robots.txt answers."""
    import os
    os.makedirs(f"{ROOT}/debug", exist_ok=True)
    urls = ["https://source.reevol.com/robots.txt", "https://source.reevol.com/sitemap.xml", "https://source.reevol.com/llms.txt",
            "https://source.reevol.com/en/suppliers/lanxi-yema-motorcycle-fittings/ai-card.md",
            "https://source.reevol.com/en/search/?q=motorcycle+helmet", "https://source.reevol.com/en/industry/apparel/china/",
            "https://www.alibaba.com/motorcycl-helmet-supplier-china-suppliers.html", "https://www.alibaba.com/motorcycle-helmet-suppliers.html",
            "https://zjwatson.en.alibaba.com/company_profile.html", "https://leiden.en.alibaba.com/company_profile.html",
            "https://freshdi.com/robots.txt", "https://freshdi.com/supplier/Foshan-Nanhai-Fushi-Helmet-Factory"]
    with open(f"{ROOT}/debug/probe.txt", "w") as out:
        for i, u in enumerate(urls):
            ok = allowed(u)
            st, n = "-", 0
            if ok:
                try:
                    r = requests.get(u, headers=H, timeout=30); st, n = r.status_code, len(r.text)
                    open(f"{ROOT}/debug/{i}.html", "w").write(r.text)
                except Exception as e:
                    st = type(e).__name__
            out.write(f"{i} robots_ok={ok} status={st} len={n} {u}\n")

if __name__ == "__main__":
    if "--probe" in sys.argv: probe()
    else: main()
