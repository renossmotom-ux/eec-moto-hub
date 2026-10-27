"""Save small local copies of every photo in data/photos.json into data/thumbs/.

Writes data/thumbs.json: {original photo URL: "data/thumbs/<file>.jpg"}. The site shows the local copy
(fast, works even if a factory server blocks outside links) and links to the original.
"""
import hashlib, io, json, os, sys
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

ROOT = __file__.rsplit("/tools/", 1)[0]
OUT = f"{ROOT}/data/thumbs"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SIZE = 360

def name(fid, u):
    return f"{fid}-{hashlib.md5(u.encode()).hexdigest()[:10]}.jpg"

def thumb(job):
    fid, u = job
    path = f"{OUT}/{name(fid, u)}"
    if os.path.exists(path): return u, path
    try:
        r = requests.get(u, headers=H, timeout=25)
        im = Image.open(io.BytesIO(r.content))
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
        im = im.convert("RGB")
        im.thumbnail((SIZE, SIZE), Image.LANCZOS)  # keep the whole motorcycle, no crop
        im.save(path, "JPEG", quality=70, optimize=True, progressive=True)
        return u, path
    except Exception as e:
        print("  thumb fail", fid, u, e, file=sys.stderr); return u, None

def main():
    os.makedirs(OUT, exist_ok=True)
    photos = json.load(open(f"{ROOT}/data/photos.json"))
    jobs = [(fid, x["u"]) for fid, v in photos.items() for x in v.get("products", []) + v.get("factory", [])]
    with ThreadPoolExecutor(12) as ex:
        done = {u: p for u, p in ex.map(thumb, jobs) if p}
    keep = {os.path.basename(p) for p in done.values()}
    for f in os.listdir(OUT):
        if f not in keep: os.remove(f"{OUT}/{f}")
    rel = {u: os.path.relpath(p, ROOT) for u, p in done.items()}
    json.dump(rel, open(f"{ROOT}/data/thumbs.json", "w"), separators=(",", ":"), sort_keys=True)
    print(f"SUMMARY: {len(rel)}/{len(jobs)} thumbnails")

if __name__ == "__main__":
    main()
