"""Look inside the EICMA exhibitor catalogue page (catalogo.eicma.it, no robots.txt) to find how exhibitors are listed.
Writes debug/probe.txt. Runs in GitHub Actions."""
import re, sys, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
out = open(sys.argv[1], "w")
r = requests.get("https://catalogo.eicma.it/Espositore?culture=en-US", headers=H, timeout=60)
h = r.text
out.write(f"len={len(h)} china={len(re.findall(r'(?i)china|cina', h))}\n")
for m in list(re.finditer(r"(?i)\bchina\b|\bcina\b", h))[3:9]:
    out.write("\n----- SNIP\n" + h[max(0, m.start() - 2500): m.start() + 800])
hrefs = sorted(set(re.findall(r'href="([^"#]+)"', h)))
out.write("\n\n----- HREFS (%d)\n" % len(hrefs) + "\n".join(x for x in hrefs if "Espositore" in x or "Dettaglio" in x)[:5000])
out.write("\n\n----- ONCLICK\n" + "\n".join(sorted(set(re.findall(r'onclick="([^"]{0,200})"', h)))[:40]))
out.write("\n\n----- AJAX\n" + "\n".join(sorted(set(re.findall(r'["\'](/[A-Za-z]+/[A-Za-z]+[^"\']{0,80})["\']', h)))[:80]))
print("ok", len(h))
