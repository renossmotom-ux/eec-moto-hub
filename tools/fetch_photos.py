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
FACT = re.compile(r"factory|workshop|plant|production|assembl|warehouse|exhibition|showroom|facilit|office|company|team|line|厂|车间|公司", re.I)
CERT = re.compile(r"certif|license|licence|patent|award|证书", re.I)
ATTRS = ("data-original", "data-src", "data-lazy", "data-lazy-src", "lazy-src", "data-url", "data-echo", "src")

def get(url, **kw):
    return requests.get(url, headers=H, timeout=25, **kw)

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
            isfact = bool(FACT.search(alt) or FACT.search(u))
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

def main():
    F = json.load(open(f"{ROOT}/data/factories.json"))
    only = set(sys.argv[1:])
    path = f"{ROOT}/data/photos.json"
    try: out = json.load(open(path))
    except Exception: out = {}
    todo = [f for f in F if (not only or f["id"] in only)]
    with ThreadPoolExecutor(10) as ex:
        for f, res in zip(todo, ex.map(one, todo)):
            if res: out[f["id"]] = res
            print(f"{f['id']}: {len(res['products']) if res else 0} products, {len(res['factory']) if res else 0} factory")
    weak = [f for f in todo if len(out.get(f["id"], {}).get("products", [])) < 2]
    print(f"browser pass for {len(weak)} factories")
    for f in weak:
        res = one(f, use_browser=True)
        if res and len(res["products"]) > len(out.get(f["id"], {}).get("products", [])):
            out[f["id"]] = res
        print(f"  {f['id']}: {len(res['products']) if res else 0} products (browser)")
    json.dump(out, open(path, "w"), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    have = sum(1 for f in F if out.get(f["id"]))
    print(f"SUMMARY: {have}/{len(F)} factories have photos; {sum(len(v['products']) for v in out.values())} product, {sum(len(v['factory']) for v in out.values())} factory photos")

if __name__ == "__main__":
    main()
