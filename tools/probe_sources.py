"""Check which extra public sources (EICMA, Canton Fair, government registries) allow robots, and save what their pages hold.
Writes debug/probe.txt. Runs in GitHub Actions."""
import re, sys, requests
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
URLS = [
  "https://www.eicma.it/en/exhibitors/", "https://www.eicma.it/en/exhibitors-list/", "https://www.eicma.it/espositori/", "https://www.eicma.it/en/",
  "https://www.cantonfair.org.cn/en-US/", "https://www.cantonfair.org.cn/en-US/exhibitors", "https://ex.cantonfair.org.cn/",
  "https://www.gsxt.gov.cn/", "https://cpzgg.miit.gov.cn/", "https://www.cccauthority.com/", "https://www.cqc.com.cn/",
  "https://vpic.nhtsa.dot.gov/api/vehicles/GetManufacturerDetails/loncin?format=json",
  "https://www.intermot.de/en/exhibitors/", "https://www.motorcycleshow.co.uk/", "https://www.automechanika-dubai.com/",
]
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
    links = [a["href"] for a in s.find_all("a", href=True) if re.search(r"exhib|esposit|catalog|company|brand|search", a["href"], re.I)][:40]
    for x in s(["script", "style"]): x.decompose()
    out.write(f"\n\n===== {u}\nallowed={ok} status={st} len={len(body)}\n--- robots\n{robots}\n--- links\n" + "\n".join(links) +
              "\n--- text\n" + re.sub(r"\s+", " ", s.get_text(" "))[:2500] + "\n--- scripts\n" + "\n".join(re.findall(r"https?://[^\"' ]+(?:api|json|exhib)[^\"' ]*", body)[:20]))
    print(u, ok, st, len(body))
