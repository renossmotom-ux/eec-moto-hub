"""Save one small local thumbnail per factory (data/thumbs/<id>.jpg) from data/photos.json.

Cards then load a ~20 KB local file instead of the full photo from the factory's server.
"""
import io, json, os, sys
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

ROOT = __file__.rsplit("/tools/", 1)[0]
OUT = f"{ROOT}/data/thumbs"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def thumb(item):
    fid, v = item
    path = f"{OUT}/{fid}.jpg"
    x = (v.get("products") or v.get("factory") or [None])[0]
    if not x: return fid, False
    if os.path.exists(path) and v.get("t_src") == x["u"]: return fid, True
    try:
        r = requests.get(x["u"], headers=H, timeout=25)
        im = Image.open(io.BytesIO(r.content))
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
        im = im.convert("RGB")
        w, h = im.size; s = min(w, h)  # centre square crop, cards are square
        im = im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((360, 360), Image.LANCZOS)
        im.save(path, "JPEG", quality=72, optimize=True, progressive=True)
        v["t_src"] = x["u"]
        return fid, True
    except Exception as e:
        print("  thumb fail", fid, e, file=sys.stderr); return fid, False

def main():
    os.makedirs(OUT, exist_ok=True)
    p = f"{ROOT}/data/photos.json"
    photos = json.load(open(p))
    with ThreadPoolExecutor(8) as ex:
        ok = dict(ex.map(thumb, photos.items()))
    for fid, v in photos.items():
        if ok.get(fid): v["t"] = f"data/thumbs/{fid}.jpg"
        else: v.pop("t", None)
    for f in os.listdir(OUT):
        if f[:-4] not in photos or not ok.get(f[:-4]): os.remove(f"{OUT}/{f}")
    json.dump(photos, open(p, "w"), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    print(f"SUMMARY: {sum(ok.values())} thumbnails")

if __name__ == "__main__":
    main()
