"""EICMA 2026 exhibitor catalogue (catalogo.eicma.it, no robots.txt): Chinese exhibitors and their public contact card.

1. /Espositore lists every exhibitor card: name, hall/stand, country, and the ids the popup uses.
2. For each CHINA exhibitor, POST /Espositore/GetBrandDetail (what the site's own popup calls) gives its card:
   website, email, phone, address when the exhibitor published them.
3. Exhibitors are matched to our companies by name; the rest are kept in data/eicma_china.json (possible new profiles).

Writes data/eicma.json {fid: {name, stand, emails, phone, web, src}} and data/eicma_china.json. Runs in GitHub Actions.
"""
import json, re, sys, time
import requests
from bs4 import BeautifulSoup
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from fetch_contacts import extract, core, PLATFORM, ROOT, H, page_text

B = "https://catalogo.eicma.it"
SRC = B + "/Espositore?culture=en-US"
SOCIAL = re.compile(r"facebook|instagram|linkedin|youtube|tiktok|twitter|x\.com|eicma|google|apple|whatsapp|wechat|weibo", re.I)

def cards():
    h = requests.get(SRC, headers=H, timeout=90).text
    s = BeautifulSoup(h, "html.parser")
    out = []
    for c in s.select("div.divOpenPopupBrand"):
        name = c.select_one("p.padiglione"); stand = c.select_one("h5.rappresentato"); ctry = c.select_one("p.brand")
        out.append({"name": name.get_text(" ", strip=True) if name else "", "stand": stand.get_text(" ", strip=True) if stand else "",
                    "country": ctry.get_text(" ", strip=True) if ctry else "", "aziendaId": c.get("data-aziendaid"),
                    "catalogoId": c.get("data-catalogoid"), "brandType": c.get("data-brandtype")})
    return out

def detail(c):
    time.sleep(1.2)
    try:
        r = requests.post(B + "/Espositore/GetBrandDetail", headers={**H, "X-Requested-With": "XMLHttpRequest", "Referer": SRC},
                          data={"aziendaId": c["aziendaId"], "catalogoId": c["catalogoId"], "brandType": c["brandType"]}, timeout=30)
    except Exception as e:
        print("  fail", c["name"], type(e).__name__, file=sys.stderr); return None
    if r.status_code != 200: print("  status", r.status_code, c["name"], file=sys.stderr); return None
    f = extract(r.text, SRC)
    s = BeautifulSoup(r.text, "html.parser")
    web = f["web"] or next((a["href"] for a in s.find_all("a", href=True) if a["href"].startswith("http") and not SOCIAL.search(a["href"]) and not PLATFORM.search(a["href"])), None)
    return {"emails": f["emails"], "phone": f["phone"], "wa": f["wa"], "wc": f["wc"], "web": web, "text": page_text(s)[:600]}

def match(name, rows):
    want = set(core(name))
    if not want: return None
    best, score = None, 0
    for r in rows:
        for n in (r.get("legal"), r.get("name")):
            got = set(core(n))
            if not got: continue
            j = len(want & got) / len(want | got)
            if j > score: best, score = r, j
    return best if score >= 0.6 else None

def main():
    rows = json.load(open(f"{ROOT}/data/factories.json")) + json.load(open(f"{ROOT}/data/helmets.json"))
    cs = cards()
    cn = [c for c in cs if re.search(r"\bCHINA\b|\bCN\b|HONG KONG", c["country"], re.I)]
    print(f"EICMA catalogue: {len(cs)} exhibitors, {len(cn)} from China")
    found, extra, samples = {}, [], []
    for i, c in enumerate(cn, 1):
        d = detail(c) or {}
        if len(samples) < 5: samples.append({**c, **d})
        r = match(c["name"], rows)
        item = {"name": c["name"], "stand": c["stand"], "emails": [e for e in (d.get("emails") or []) if "eicma" not in e], "phone": d.get("phone"), "wa": d.get("wa"),
                "wc": d.get("wc"), "web": d.get("web"), "src": SRC}
        if r: found[r["id"]] = item
        else: extra.append(item)
        print(f"[{i}/{len(cn)}] {c['name']} -> {r['id'] if r else '-'} {item['emails']} {item['web']}", file=sys.stderr, flush=True)
    json.dump(found, open(f"{ROOT}/data/eicma.json", "w"), ensure_ascii=False, indent=1, sort_keys=True)
    json.dump(extra, open(f"{ROOT}/data/eicma_china.json", "w"), ensure_ascii=False, indent=1)
    print(f"\nMatched to our companies: {len(found)}  \nWith email: {sum(bool(v['emails']) for v in found.values())}  \n"
          f"Other Chinese exhibitors (not yet on the site): {len(extra)}, with email: {sum(bool(v['emails']) for v in extra)}  ")
    print("\nSample cards:\n```\n" + json.dumps(samples, ensure_ascii=False, indent=1)[:4000] + "\n```")

if __name__ == "__main__":
    main()
