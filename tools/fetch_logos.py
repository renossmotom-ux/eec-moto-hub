"""Collect each company's logo from its own website (or its B2B showroom page) for the factory list.

Runs in GitHub Actions. Saves data/logos/<id>.png (white background, max 320px) and data/logos.json {id: {p, from}}.
Respects robots.txt like tools/fetch_photos.py.
"""
import io, json, os, re, sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from fetch_photos import ROOT, H, allowed, get, render, requests

OUT = f"{ROOT}/data/logos"
NOT_THEIRS = re.compile(r"tradewheel|b2brazil|autohome|visordown|wikipedia|made-in-china|micstatic|alibaba|alicdn|globalsources|ec21|wikipedia|wikimedia|facebook|twitter|linkedin|youtube|wechat|whatsapp|google|baidu|payment|visa|flag|qr|icon-|sprite", re.I)

def candidates(html, base, f):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("data-original") or img.get("src") or ""
        if not src or src.startswith("data:"): continue
        attrs = " ".join([src, img.get("alt") or "", " ".join(img.get("class") or []), img.get("id") or "",
                          " ".join((p.get("class") and " ".join(p.get("class"))) or (p.get("id") or "") for p in img.parents if p.name in ("a", "div", "header", "span"))[:300]])
        if "logo" not in attrs.lower(): continue
        u = urljoin(base, src.strip())
        if NOT_THEIRS.search(u) or NOT_THEIRS.search(img.get("alt") or ""): continue
        score = 2 if img.find_parent("header") or "header" in attrs.lower() else 1
        out.append((score, u))
    for l in soup.select('link[rel~="apple-touch-icon"], link[rel~="icon"]'):
        if l.get("href") and not l["href"].startswith("data:"): out.append((0, urljoin(base, l["href"])))
    out.sort(key=lambda x: -x[0])
    return list(dict.fromkeys(u for _, u in out))

def load(u, ref):
    r = requests.get(u, headers={**H, "Referer": ref}, timeout=25)
    if r.status_code != 200: return None
    data = r.content
    if b"<svg" in data[:2000]:
        import cairosvg
        data = cairosvg.svg2png(bytestring=data, output_width=480)
    im = Image.open(io.BytesIO(data))
    if im.width < 48 or im.height < 24 or im.width / im.height > 8: return None
    im = im.convert("RGBA"); bbox = im.getbbox()
    if bbox: im = im.crop(bbox)
    # white or near-white logos vanish on a white card: put them on the brand's dark colour instead
    px = [p for p in im.getdata() if p[3] > 128]
    light = px and sum(p[0] + p[1] + p[2] for p in px) / len(px) > 690
    bg = Image.new("RGB", im.size, (26, 45, 90) if light else (255, 255, 255)); bg.paste(im, mask=im.split()[-1])
    bg.thumbnail((320, 160), Image.LANCZOS)
    return bg

def one(f):
    pages = [f.get("web"), f.get("contact")]
    for page in dict.fromkeys(p for p in pages if p and p.startswith("http")):
        if not allowed(page) or NOT_THEIRS.search(page): continue  # directories and news sites, not the company's own site
        try:
            r = get(page)
            html = r.text if r.status_code == 200 else ""
            if not candidates(html, page, f) and r.status_code not in (403, 429): html = render(page)  # sites built with JavaScript
            for u in candidates(html, page, f)[:6]:
                try: im = load(u, page)
                except Exception: im = None
                if im:
                    im.save(f"{OUT}/{f['id']}.png", optimize=True)
                    return f["id"], {"p": f"data/logos/{f['id']}.png", "from": page}
        except Exception as e:
            print("  fail", f["id"], page, type(e).__name__, file=sys.stderr)
    return f["id"], None

def main():
    os.makedirs(OUT, exist_ok=True)
    F = json.load(open(f"{ROOT}/data/factories.json"))
    with ThreadPoolExecutor(8) as ex:
        res = {k: v for k, v in ex.map(one, F) if v}
    json.dump(res, open(f"{ROOT}/data/logos.json", "w"), separators=(",", ":"), sort_keys=True)
    print(f"SUMMARY: {len(res)}/{len(F)} logos")

if __name__ == "__main__":
    main()
