"""Keep only real motorcycle (and factory) photos, pick each brand's hero photos, and link photos to EEC models.

Reads data/photos.json + data/thumbs/ and looks at every thumbnail with an image model (CLIP, zero-shot),
so vans, cars, ads, banners, logos, people and unrelated products (other companies on B2B sites) are dropped.
Writes back data/photos.json with, per factory: products (best studio shots first), factory, hero:[urls],
models:{model name: url}; and data/photo_rejects.json (URLs never to collect again).
"""
import json, os, sys

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

sys.path.insert(0, os.path.dirname(__file__))
from models import match

ROOT = __file__.rsplit("/tools/", 1)[0]
VEHICLE = ["a photo of a motorcycle", "a photo of a motor scooter", "a photo of an electric scooter or moped",
           "a photo of a dirt bike", "a photo of an ATV quad bike", "a photo of a motorcycle with a sidecar",
           "a photo of a three-wheeled motor tricycle", "a photo of an off-road buggy or UTV", "a photo of a go-kart",
           "a photo of an electric bicycle", "a photo of a motorcycle engine", "a photo of a person riding a motorcycle",
           "a photo of motorcycles in a showroom"]
FACTORY = ["a photo of a factory assembly line", "a photo of a factory building", "a photo of a factory workshop with machines",
           "a photo of a warehouse"]
BAD = ["a photo of a car", "a photo of a van or minibus", "a photo of a truck or bus", "an advertisement poster with large text",
       "a website screenshot", "a phone screenshot", "a logo", "a portrait photo of a person", "a photo of a crowd of people",
       "a photo of bags of powder or chemicals", "a photo of household products", "a photo of a helmet or riding clothes",
       "a grey placeholder silhouette with no photo", "a document or certificate", "a chart or diagram", "a photo of machine parts",
       "a photo of furniture", "a photo of food", "a photo of a shop front", "a photo of a bicycle without motor"]
STUDIO = ["a studio photo of one motorcycle on a plain white background", "a photo with text, people, buildings or scenery"]
LABELS = VEHICLE + FACTORY + BAD
NV, NF = len(VEHICLE), len(FACTORY)

def ahash(path):
    im = Image.open(f"{ROOT}/{path}").convert("L").resize((12, 12)); px = list(im.getdata()); avg = sum(px) / len(px)
    return "".join("1" if q > avg else "0" for q in px)

def main():
    photos = json.load(open(f"{ROOT}/data/photos.json"))
    thumbs = json.load(open(f"{ROOT}/data/thumbs.json"))
    F = {f["id"]: f for f in json.load(open(f"{ROOT}/data/factories.json"))}
    rp = f"{ROOT}/data/photo_rejects.json"
    rejects = set(json.load(open(rp))) if os.path.exists(rp) else set()
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
    proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    with torch.no_grad():
        tl = proc(text=LABELS, return_tensors="pt", padding=True); te = model.get_text_features(**tl); te = te / te.norm(dim=-1, keepdim=True)
        ts = proc(text=STUDIO, return_tensors="pt", padding=True); se = model.get_text_features(**ts); se = se / se.norm(dim=-1, keepdim=True)
    scale = model.logit_scale.exp()

    jobs = [(fid, x) for fid, v in photos.items() for x in v.get("products", []) + v.get("factory", []) if thumbs.get(x["u"])]
    score = {}
    for i in range(0, len(jobs), 64):
        batch = jobs[i:i + 64]; ims, keep = [], []
        for fid, x in batch:
            try: ims.append(Image.open(f"{ROOT}/{thumbs[x['u']]}").convert("RGB")); keep.append(x["u"])
            except Exception: pass
        if not ims: continue
        with torch.no_grad():
            ie = model.get_image_features(**proc(images=ims, return_tensors="pt")); ie = ie / ie.norm(dim=-1, keepdim=True)
            p = (scale * ie @ te.T).softmax(-1); s = (scale * ie @ se.T).softmax(-1)[:, 0]
        for u, pr, st in zip(keep, p.tolist(), s.tolist()):
            score[u] = (sum(pr[:NV]), sum(pr[NV:NV + NF]), max(range(len(pr)), key=pr.__getitem__), st)
        print(f"  scored {min(i + 64, len(jobs))}/{len(jobs)}", file=sys.stderr)

    def vehicle(x):
        sc = score.get(x["u"]); return bool(sc) and sc[0] >= 0.5 and sc[2] < NV
    def factory(x):
        sc = score.get(x["u"]); return bool(sc) and sc[0] + sc[1] >= 0.5 and sc[2] < NV + NF

    kept = dropped = 0
    for fid in list(photos):
        v, f = photos[fid], F.get(fid, {})
        allp = v.get("products", []) + v.get("factory", [])
        prods = [x for x in v.get("products", []) if vehicle(x)]
        facts = [x for x in v.get("factory", []) if factory(x)] + [x for x in v.get("products", []) if not vehicle(x) and factory(x) and score[x["u"]][2] >= NV]
        good = {x["u"] for x in prods + facts}
        for x in allp:
            if x["u"] not in good and x["u"] in score: rejects.add(x["u"])
        dropped += len(allp) - len(good); kept += len(good)
        prods.sort(key=lambda x: -score[x["u"]][3])  # clean studio shots first
        seen = set(); prods = [x for x in prods if not (ahash(thumbs[x["u"]]) in seen or seen.add(ahash(thumbs[x["u"]])))]  # same photo under two URLs
        models = {}
        for x in prods:
            for n in match(f, (x.get("alt") or "") + " " + (x.get("m") or "")):
                models.setdefault(n, x["u"])
        hero = [x["u"] for x in prods if score[x["u"]][3] >= 0.5][:3] or [x["u"] for x in prods][:3]
        if not prods and not facts: del photos[fid]; continue
        v.update(products=prods, factory=facts[:4], hero=hero, models=models)
    json.dump(photos, open(f"{ROOT}/data/photos.json", "w"), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    json.dump(sorted(rejects), open(rp, "w"), indent=0)
    nm = sum(len(v["models"]) for v in photos.values()); ne = sum(len(f.get("eec", [])) for f in F.values())
    print(f"SUMMARY: kept {kept} photos, dropped {dropped} (vans, cars, ads, logos, other products); {len(photos)} factories with photos; {nm} model photos for {ne} EEC models")

if __name__ == "__main__":
    main()
