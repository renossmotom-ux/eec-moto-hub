"""Collect real photos for every factory from its own website or B2B showroom.

Runs in GitHub Actions (the hosting/cloud sandboxes can't reach these sites).
Writes data/photos.json: {id: {page, products:[{u,alt,w,h}], factory:[...], at}}.
Only images published by the factory itself on those pages are kept; each one is
downloaded once to check it loads without a Referer and is a real photo (size, not a logo).
"""
import hashlib, io, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = __file__.rsplit("/tools/", 1)[0]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,zh;q=0.6"}
MAX_PROD, MAX_FACT, MAX_TRY = 8, 4, 40
SKIP = re.compile(r"logo|icon|sprite|transparent|avatar|flag|qr|loading|blank|placeholder|default|banner-?bg|\.svg|\.gif|micstatic\.com|captcha|pixel|wechat|whatsapp|share|arrow|button", re.I)
FACT = re.compile(r"^(our |the )?(factory|workshop|plant|production( line)?|assembly( line)?|warehouse|exhibition|showroom|facilit\w*|office|company|team|工厂|车间|公司)\b", re.I)

def norm(x):
    return re.sub(r"[^a-z0-9]", "", x.lower())

def is_factory(alt, u, f):
    """Company/factory photo vs product photo. Product titles often say "Factory supply ...", so match short labels only."""
    a = alt.strip()
    if "company-profile" in u or "/company" in u.lower(): return True
    if re.search(r"made-in-china\.com/\w+/made-in-china\.(webp|jpe?g|png)$", u): return True  # showroom company album
    if a and norm(a) in {norm(f.get("name", "")), norm(f.get("legal") or "")}: return True
    return bool(FACT.search(a)) and len(a.split()) <= 5
CERT = re.compile(r"certif|license|licence|patent|award|证书", re.I)
ATTRS = ("data-original", "data-src", "data-lazy", "data-lazy-src", "lazy-src", "data-url", "data-echo", "src")

def get(url, **kw):
    for i in range(3):
        r = requests.get(url, headers=H, timeout=25, **kw)
        if r.status_code not in (403, 429, 503) or kw.get("stream"): return r
        time.sleep(5 * (i + 1))
    return r

def candidates(html, base):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for m in soup.select('meta[property="og:image"], meta[name="og:image"]'):
        if m.get("content"): out.append((m["content"], soup.title.get_text(" ", strip=True) if soup.title else ""))
    for img in soup.find_all("img"):
        src = next((img.get(a) for a in ATTRS if img.get(a) and not img.get(a).startswith("data:")), None)
        if not src and img.get("srcset"): src = img["srcset"].split(",")[0].split()[0]
        if not src: continue
        alt = (img.get("alt") or img.get("title") or "").strip()
        if not alt:
            p = img.find_parent(["a", "div", "li"])
            alt = (p.get("title") or p.get_text(" ", strip=True)[:120]) if p else ""
        out.append((src, alt))
    for el in soup.select("[style*=background]"):
        for u in re.findall(r"url\(['\"]?([^'\")]+)", el.get("style", "")):
            out.append((u, el.get("title") or ""))
    seen, res = set(), []
    for src, alt in out:
        u = urljoin(base, src.strip())
        if not u.startswith("http") or u in seen or SKIP.search(u.split("?")[0]): continue
        seen.add(u); res.append((u, alt))
    links = [urljoin(base, a["href"]) for a in soup.find_all("a", href=True)
             if re.search(r"company[-_ ]?(profile|info)|about|factory|company-", a["href"] + " " + a.get_text(" ", strip=True), re.I)]
    return res, links

def check(u):
    """Download once: must load with no Referer, be a photo-sized raster image."""
    try:
        r = get(u, stream=True)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"): return None
        data = r.raw.read(6_000_000, decode_content=True)
        im = Image.open(io.BytesIO(data)); w, h = im.size
        if w < 300 or h < 200 or not (0.45 < w / h < 2.6): return None
        return w, h, hashlib.md5(data).hexdigest()
    except Exception:
        return None

def pages_for(f):
    ps = [f.get("web"), f.get("contact")] + [s for s in f.get("src", []) if "made-in-china.com" in s or "globalsources.com" in s]
    out = []
    for p in ps:
        if p and p.startswith("http") and p not in out: out.append(p)
    return out[:3]

def render(url):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(user_agent=UA)
            pg.goto(url, timeout=45000, wait_until="domcontentloaded")
            for _ in range(6): pg.mouse.wheel(0, 1600); pg.wait_for_timeout(600)
            html = pg.content(); b.close(); return html
    except Exception as e:
        print("  render fail", url, e, file=sys.stderr); return ""

def one(f, use_browser=False):
    prods, facts, hashes, page, tried = [], [], set(), None, 0
    queue = [(p, 0) for p in pages_for(f)]
    visited = set()
    while queue and (len(prods) < MAX_PROD or len(facts) < MAX_FACT) and tried < MAX_TRY:
        url, depth = queue.pop(0)
        if url in visited: continue
        visited.add(url)
        html = ""
        if use_browser: html = render(url)
        else:
            try:
                r = get(url)
                if r.status_code != 200: print("  page", r.status_code, url, file=sys.stderr)
                elif len(r.text) < 3000 or re.search(r"captcha|slide to verify|验证", r.text[:20000], re.I): print("  page blocked?", len(r.text), url, file=sys.stderr)
                if r.status_code == 200: r.encoding = r.apparent_encoding if not r.encoding or r.encoding == "ISO-8859-1" else r.encoding; html = r.text
            except Exception as e:
                print("  page fail", url, type(e).__name__, file=sys.stderr)
        if not html: continue
        cands, links = candidates(html, url)
        if depth == 0:
            host = urlparse(url).netloc
            queue += [(l, 1) for l in links[:3] if urlparse(l).netloc == host]
        for u, alt in cands:
            if tried >= MAX_TRY: break
            isfact = is_factory(alt, u, f)
            if CERT.search(alt): continue
            if isfact and len(facts) >= MAX_FACT: continue
            if not isfact and len(prods) >= MAX_PROD: continue
            tried += 1
            c = check(u)
            if not c or c[2] in hashes: continue
            hashes.add(c[2])
            item = {"u": u, "alt": alt[:140], "w": c[0], "h": c[1]}
            (facts if isfact else prods).append(item)
            page = page or url
    return {"page": page, "products": prods, "factory": facts, "at": time.strftime("%Y-%m-%d")} if (prods or facts) else None

def commons(f):
    """Fallback for big brands whose own sites can't be read: freely licensed photos on Wikimedia Commons, with credit."""
    brand = f["name"].split(" / ")[0].split()[0]
    if len(brand) < 3: return None
    try:
        j = get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": f'"{brand}" motorcycle', "gsrlimit": 25, "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 900}).json()
    except Exception as e:
        print("  commons fail", f["id"], e, file=sys.stderr); return None
    items = []
    for pg in sorted(j.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99)):
        ii = (pg.get("imageinfo") or [{}])[0]
        title = pg.get("title", "")
        if ii.get("mime") not in ("image/jpeg", "image/png", "image/webp") or norm(brand) not in norm(title): continue
        if ii.get("width", 0) < 500 or SKIP.search(title): continue
        md = ii.get("extmetadata", {})
        artist = re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", "")).strip()
        lic = md.get("LicenseShortName", {}).get("value", "")
        if not lic: continue
        alt = re.sub(r"^File:|\.\w+$", "", title).replace("_", " ")
        items.append({"u": ii.get("thumburl") or ii["url"], "alt": alt[:140], "w": ii.get("thumbwidth", ii["width"]), "h": ii.get("thumbheight", ii["height"]),
                      "credit": f"{artist or 'Unknown'} · {lic} · Wikimedia Commons", "link": ii.get("descriptionurl")})
        if len(items) >= 6: break
    if not items: return None
    return {"page": "https://commons.wikimedia.org/w/index.php?search=" + requests.utils.quote(f'"{brand}" motorcycle'), "via": "commons",
            "products": items, "factory": [], "at": time.strftime("%Y-%m-%d")}

def main():
    F = json.load(open(f"{ROOT}/data/factories.json"))
    only = set(sys.argv[1:])
    path = f"{ROOT}/data/photos.json"
    try: out = json.load(open(path))
    except Exception: out = {}
    byid = {f["id"]: f for f in F}
    for k, v in out.items():  # re-sort existing photos with the current rule
        if k in byid and v.get("via") != "commons":
            allp = v["products"] + v["factory"]
            v["factory"] = [x for x in allp if is_factory(x["alt"], x["u"], byid[k])][:MAX_FACT]
            v["products"] = [x for x in allp if not is_factory(x["alt"], x["u"], byid[k])][:MAX_PROD]
    full = "--all" in only; only.discard("--all")
    if only: todo = [f for f in F if f["id"] in only]
    else: todo = [f for f in F if full or len(out.get(f["id"], {}).get("products", [])) < 2]
    print(f"fetching {len(todo)} factories")
    with ThreadPoolExecutor(4) as ex:
        for f, res in zip(todo, ex.map(one, todo)):
            if res and len(res["products"]) + len(res["factory"]) > len(out.get(f["id"], {}).get("products", [])) + len(out.get(f["id"], {}).get("factory", [])): out[f["id"]] = res
            print(f"{f['id']}: {len(res['products']) if res else 0} products, {len(res['factory']) if res else 0} factory")
    # A real browser only helps brand sites that build pages with JavaScript; B2B showrooms serve plain HTML.
    weak = [f for f in todo if f.get("tier") == "full" and len(out.get(f["id"], {}).get("products", [])) < 2]
    print(f"browser pass for {len(weak)} factories")
    for f in weak:
        res = one(f, use_browser=True)
        if res and len(res["products"]) > len(out.get(f["id"], {}).get("products", [])):
            out[f["id"]] = res
        print(f"  {f['id']}: {len(res['products']) if res else 0} products (browser)")
    for f in todo:
        if f.get("tier") == "full" and not out.get(f["id"], {}).get("products"):
            res = commons(f)
            if res: out[f["id"]] = res
            print(f"  {f['id']}: {len(res['products']) if res else 0} products (commons)")
    json.dump(out, open(path, "w"), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    have = sum(1 for f in F if out.get(f["id"]))
    print(f"SUMMARY: {have}/{len(F)} factories have photos; {sum(len(v['products']) for v in out.values())} product, {sum(len(v['factory']) for v in out.values())} factory photos")

if __name__ == "__main__":
    main()
