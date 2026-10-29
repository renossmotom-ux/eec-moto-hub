"""Collect Chinese motorcycle helmet manufacturers from made-in-china.com supplier listings.

Runs in GitHub Actions (the cloud sandbox can't reach these sites). Respects robots.txt.
--debug saves a few raw pages into debug/ so the parser can be checked.
"""
import json, os, re, sys, time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

ROOT = __file__.rsplit("/tools/", 1)[0]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
_robots = {}

def allowed(url):
    base = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if base not in _robots:
        rp = RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers=H, timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)

def get(url):
    if not allowed(url):
        print("  robots.txt disallows", url, file=sys.stderr); return None
    try:
        r = requests.get(url, headers=H, timeout=25)
    except Exception as e:
        print("  fail", url, e, file=sys.stderr); return None
    print(f"  {r.status_code} {len(r.text)} {url}", file=sys.stderr)
    time.sleep(1)
    return r.text if r.status_code == 200 else None

def debug():
    os.makedirs(f"{ROOT}/debug", exist_ok=True)
    for i, u in enumerate(["https://www.made-in-china.com/factory/dot-ece-helmet.html",
                           "https://www.made-in-china.com/manufacturers/motorcycle-helmet.html",
                           "https://www.made-in-china.com/factory/motorcycle-helmet.html",
                           "https://bybhelmet.en.made-in-china.com",
                           "https://bybhelmet.en.made-in-china.com/product-list-1.html",
                           "https://bybhelmet.en.made-in-china.com/company-info.html",
                           "https://zjhengtai.en.made-in-china.com/product-list-1.html"]):
        h = get(u)
        if h: open(f"{ROOT}/debug/{i}.html", "w").write(h)

if __name__ == "__main__":
    if "--debug" in sys.argv: debug()
