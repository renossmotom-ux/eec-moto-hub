"""Check which extra public sources (EICMA, Canton Fair, government registries) allow robots, and save what their pages hold.
Writes debug/probe.txt. Runs in GitHub Actions."""
import re, sys, requests
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
URLS = ["https://catalogo.eicma.it/Espositore", "https://catalogo.eicma.it/Espositore?culture=en-US&nazione=CINA", "https://catalogo.eicma.it/Espositore?page=2"]
out = open(sys.argv[1] if len(sys.argv) > 1 else "debug/probe.txt", "w")
for u in URLS:
    base = re.match(r"https?://[^/]+", u).group(0)
    try:
        rr = requests.get(base + "/robots.txt", headers=H, timeout=20); rp = RobotFileParser(); rp.parse(rr.text.splitlines() if rr.status_code == 200 else []); ok = rp.can_fetch(UA, u)
        robots = rr.text[:800] if rr.status_code == 200 else f"(robots {rr.status_code})"
    except Exception as e:
        ok, robots = None, f"robots error {type(e).__name__}"
    try:
        r = requests.get(u, headers=H, timeout=25) if ok is not False else None
        st = r.status_code if r is not None else "skipped"
        body = r.text if r is not None else ""
    except Exception as e:
        st, body = f"error {type(e).__name__}", ""
    s = BeautifulSoup(body, "html.parser")
    links = [a["href"] for a in s.find_all("a", href=True) if re.search(r"exhib|esposit|catalog|company|brand|search", a["href"], re.I)][:80]
    for x in s(["script", "style"]): x.decompose()
    out.write(f"\n\n===== {u}\nallowed={ok} status={st} len={len(body)}\n--- robots\n{robots}\n--- links\n" + "\n".join(links) +
              "\n--- text\n" + re.sub(r"\s+", " ", s.get_text(" "))[:5000] + "\n--- scripts\n" + "\n".join(re.findall(r"https?://[^\"' ]+(?:api|json|exhib)[^\"' ]*", body)[:20]))
    print(u, ok, st, len(body))
    if u.endswith("/Espositore"):
        out.write("\n--- forms\n" + "\n".join(str(f)[:1500] for f in BeautifulSoup(body, "html.parser").find_all(["form", "select"]))[:6000])
        det = [a["href"] for a in BeautifulSoup(body, "html.parser").find_all("a", href=True) if re.search(r"Espositore/|Dettaglio|scheda", a["href"], re.I)]
        out.write("\n--- detail links\n" + "\n".join(det[:60]))
        for d in det[:3]:
            d = d if d.startswith("http") else "https://catalogo.eicma.it" + ("" if d.startswith("/") else "/") + d
            r2 = requests.get(d, headers=H, timeout=25); s2 = BeautifulSoup(r2.text, "html.parser")
            for x in s2(["script", "style"]): x.decompose()
            out.write(f"\n\n===== DETAIL {d} {r2.status_code}\n" + re.sub(r"\s+", " ", s2.get_text(" "))[:3000])
