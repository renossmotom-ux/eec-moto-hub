"""Find how the EICMA catalogue loads an exhibitor's details (popup). Writes debug/probe.txt. Runs in GitHub Actions."""
import re, sys, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
B = "https://catalogo.eicma.it"
out = open(sys.argv[1], "w")
h = requests.get(B + "/Espositore?culture=en-US", headers=H, timeout=60).text
srcs = re.findall(r'<script[^>]+src="([^"]+)"', h)
out.write("SCRIPTS\n" + "\n".join(srcs))
for sc in re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", h, re.S):
    if re.search(r"Popup|ajax|fetch\(|url\s*:", sc): out.write("\n----- INLINE\n" + sc[:6000])
for s in srcs:
    if s.startswith("/") or "eicma" in s:
        u = s if s.startswith("http") else B + s
        try: js = requests.get(u, headers=H, timeout=30).text
        except Exception: continue
        for m in re.finditer(r"divOpenPopupBrand|aziendaId|ajax\(|\$\.get|\$\.post|fetch\(", js):
            out.write(f"\n----- {u} @{m.start()}\n" + js[max(0, m.start() - 300): m.start() + 900])
print("ok")
