# Hand-checked suppliers found on Facebook, TikTok and YouTube (2026-11-01).
# Contacts are only what the page itself shows. Run: python tools/social_suppliers.py .  -> data/factories.json, data/helmets.json, data/social.json
import json, re, sys
ROOT = sys.argv[1]
FB, YT, TT = "Facebook", "YouTube", "TikTok"
# name, kind(moto|helmet), types, city, prov, social links, contacts {wa,wc,emails,web}, src (where contacts are shown), photos
NEW = [
 ("Yuanchi E-Bike Factory (远驰)", "moto", ["Electric", "Scooter"], None, None, [], {"wc": "+86 13060758587"}, "Facebook page “远驰E-Bike-Factory” (screenshot)", {"factory": ["data/social/yuanchi-factory-1.jpg", "data/social/yuanchi-factory-2.jpg"]}, "Facebook bio: “Canton Fair, China Manufacturer”. 16K followers."),
 ("Yide Scooter (bestyide)", "moto", ["Electric", "Scooter"], None, None, ["https://www.facebook.com/yidescooter/"], {"wa": "+86 159 5835 8515", "emails": ["bruce@bestyide.com"]}, "https://www.facebook.com/yidescooter/videos/m6-electric-motorcycle-%EF%B8%8Ffor-inquirywhatsappimessage0086-159-5835-8515brucebestyi/1337916793223870/", None, "Electric motorcycle M6 shown in their Facebook video."),
 ("Tianjin Yulue Bike", "moto", ["Electric"], "Tianjin", "Tianjin", ["https://www.tiktok.com/@tianjinyulue_bike"], {"wa": "+86 17772617810", "wc": "+86 18531222022"}, "https://www.tiktok.com/@tianjinyulue_bike/video/7504200739988720926", None, "Electric bicycles. TikTok post: “From a manufacturing factory in China”."),
 ("Saige Electric Cargo Tricycle", "moto", ["Electric", "Tricycle"], None, None, ["https://www.youtube.com/watch?v=DvA21HIbJEk"], {"wa": "+86 15895306051"}, "https://www.youtube.com/watch?v=DvA21HIbJEk", {"yt": ["DvA21HIbJEk"]}, "Electric cargo tricycles; video says EEC and COC. Posted by the channel CNRollformer, so it may be an agent."),
 ("YS Helmet", "helmet", ["Full face"], None, None, ["https://www.youtube.com/channel/UCNXxbTd3gl7_3fazvMdWE9w"], {"wa": "+86 18316821270", "emails": ["alyseliu233@gmail.com"], "web": "https://www.yshelmets.com"}, "https://www.youtube.com/channel/UCNXxbTd3gl7_3fazvMdWE9w", None, "OEM motorcycle helmets (YouTube channel “OEM Motorcycle Helmets”)."),
 ("XNT E-Bike", "moto", ["Electric"], None, None, ["https://www.youtube.com/@XNTebike"], {"wa": "+86 18967623620", "phone": "+86 18967623812"}, "https://www.youtube.com/@XNTebike", None, "Electric bikes. A second WhatsApp/phone is listed: +86 18967623812."),
 ("Yi Ebike (yielife)", "moto", ["Electric"], None, None, ["https://www.youtube.com/@yiebike"], {"wa": "+86 15579787035", "emails": ["info@yielife.com"]}, "https://www.youtube.com/@yiebike", None, "Electric bikes."),
 ("Yongkang Lohas Vehicle Co., Ltd.", "moto", ["Electric", "Scooter"], "Yongkang", "Zhejiang", ["https://www.youtube.com/@LOHASVEHICLE"], {"wa": "+86 13506799175", "wc": "+86 13506799175", "emails": ["sales@cnkcgroup.com"]}, "https://www.youtube.com/@LOHASVEHICLE", None, "Electric scooters and vehicles."),
 ("Disiyuan Ebike Factory", "moto", ["Electric"], None, None, ["https://www.youtube.com/@DISIYUAN"], {"wc": "+86 15113813917", "web": "https://www.disiyuan.com"}, "https://www.youtube.com/@DISIYUAN", None, "Electric bikes. Alibaba shop: www.disiyuan.cn."),
 ("Shenzhen Rooder Technology Co., Ltd.", "moto", ["Electric", "Scooter"], "Shenzhen", "Guangdong", ["https://www.youtube.com/@Rooder2010"], {"wa": "+86 13632905138", "wc": "gavin782", "emails": ["rooder@roodergroup.com", "rooder.tec@gmail.com"], "web": "https://www.roodergroup.com"}, "https://www.youtube.com/@Rooder2010", None, "Citycoco, e-scooters and e-bikes. Second site: www.rooderchina.com."),
 ("Kavaki Motorcycle (Guangzhou Kavaki Motorcycle Industry Co., Limited)", "moto", ["Street", "Electric", "Tricycle"], "Guangzhou", "Guangdong", ["https://www.youtube.com/@kavakiMotorcycle", "https://www.facebook.com/kavakimotorcycle/"], {"wa": "+86 13318864687", "wc": "+86 13318864687"}, "https://www.youtube.com/@kavakiMotorcycle", None, "Petrol and electric motorcycles and tricycles."),
 ("Huameng Electric Tricycle Factory", "moto", ["Electric", "Tricycle"], None, None, ["https://www.youtube.com/channel/UCi_8_jnI9ckvjwTSTqH52uQ"], {"wa": "+86 19962787871", "emails": ["huamengevtricycle@outlook.com"]}, "https://www.youtube.com/channel/UCi_8_jnI9ckvjwTSTqH52uQ", None, "Electric tricycles."),
 ("Mademoto", "moto", ["Electric", "Off-road", "Scooter"], None, None, ["https://www.youtube.com/factoryprc"], {"emails": ["sales@mademoto.com"]}, "https://www.youtube.com/watch?v=mNdWLhDclOk", {"yt": ["mNdWLhDclOk", "wYgi83mUkOg"]}, "ATVs, Citycoco e-scooters and electric motorcycles."),
 ("Wuxi Zhongfa Electric Bike", "moto", ["Electric"], "Wuxi", "Jiangsu", ["https://www.facebook.com/zhongfa.ebike/"], {"web": "https://www.zhongfaev.com"}, None, None, "Electric bikes."),
]
# Facebook / TikTok pages whose contacts robots cannot read: name, kind, types, city, prov, link
FBONLY = [
 ("Wujie Motors", "moto", ["Street"], None, None, "https://www.facebook.com/WujieMotors/"),
 ("Chongqing Hengjian Motorcycle Manufacturing Co., Ltd.", "moto", ["Street"], "Chongqing", "Chongqing", "https://www.facebook.com/HJmotorcycles/"),
 ("Leichten Electric Bicycle", "moto", ["Electric"], None, None, "https://www.facebook.com/leichtenelectricbike/"),
 ("DOFA Bike", "moto", ["Electric"], None, None, "https://www.facebook.com/dofabike/"),
 ("YiLing Ebike", "moto", ["Electric"], "Wuxi", "Jiangsu", "https://www.facebook.com/yilingebike/"),
 ("Guangzhou Yansan Technology", "moto", ["Electric"], "Guangzhou", "Guangdong", "https://www.facebook.com/p/Guangzhou-Yansan-Technology-100067976497619/"),
 ("Jueshuai Ebike", "moto", ["Electric"], None, None, "https://www.facebook.com/JueshuaiEbike/"),
 ("Foshan Haojun Motorcycle Co., Ltd.", "moto", ["Street"], "Foshan", "Guangdong", "https://www.facebook.com/p/Foshan-Haojun-Motorcycle-Co-Ltd-61553851738214/"),
 ("Chongqing Trikmoto Motorcycle Factory", "moto", ["Off-road"], "Chongqing", "Chongqing", "https://www.facebook.com/250ccmotocross/"),
 ("Wanhoo Motos", "moto", ["Street", "Tricycle"], None, None, "https://www.facebook.com/wanhoomotos/"),
 ("Chongqing BULL Motorcycle & Engine Co.", "moto", ["Street", "Off-road"], "Chongqing", "Chongqing", "https://www.facebook.com/bullmotorcycle/"),
 ("Wuxi Holi Vehicle Co., Ltd", "moto", ["Electric"], "Wuxi", "Jiangsu", "https://www.facebook.com/p/Wuxi-Holi-Vehicle-Co-Ltd-61550753457168/"),
 ("Wuxi Mifun Electric Vehicle", "moto", ["Electric"], "Wuxi", "Jiangsu", "https://www.facebook.com/Mifun888/"),
 ("Wuxi Ladea EV", "moto", ["Electric"], "Wuxi", "Jiangsu", "https://www.facebook.com/LadeaEV.Wuxi/"),
 ("Wuxi Aiyada Electric Vehicle Co., Ltd", "moto", ["Electric"], "Wuxi", "Jiangsu", "https://www.facebook.com/ebikesfactory/"),
 ("Wuxi Maya Scooter Technology Co., Ltd.", "moto", ["Electric", "Scooter"], "Wuxi", "Jiangsu", "https://www.facebook.com/mayamotorcycle/"),
 ("Tianjin Danni Electric Vehicle Factory", "moto", ["Electric"], "Tianjin", "Tianjin", "https://www.facebook.com/Danni8866"),
 ("Libon Tianjin Technology Co., Ltd.", "moto", ["Electric"], "Tianjin", "Tianjin", "https://www.facebook.com/ebikesbikeOEM/"),
 ("Tianjin Yulu New Energy Technology Co., Ltd.", "moto", ["Electric"], "Tianjin", "Tianjin", "https://www.facebook.com/YuluNewEnergy/"),
 ("TEYIN Motorcycle", "moto", ["Street"], None, None, "https://www.facebook.com/TeyinMotorcycle/"),
 ("YIQI Motorcycle", "moto", ["Street"], None, None, "https://www.facebook.com/YIQImotor/"),
 ("Jin Lang Moto (劲浪摩托)", "moto", ["Street"], None, None, "https://www.facebook.com/p/Jin-lang-moto%E5%8A%B2%E6%B5%AA%E6%91%A9%E6%89%98-100063969975033/"),
 ("QSMOTOR", "moto", ["Electric"], None, None, "https://www.facebook.com/cnqsmotor/"),
 ("JiangMen LeiLong Motorcycle Co., Ltd", "moto", ["Street"], "Jiangmen", "Guangdong", "https://www.facebook.com/leilongmotor/"),
 ("Jiangmen Shi Better Motorcycle Co., Ltd", "moto", ["Street"], "Jiangmen", "Guangdong", "https://www.facebook.com/bettermotorcycle/"),
 ("KAMAX Group", "moto", ["Electric"], None, None, "https://www.facebook.com/kamax2001/"),
 ("Wuxi Kaining Electric Technology Co., Ltd", "moto", ["Electric"], "Wuxi", "Jiangsu", "https://www.facebook.com/Kainingwuxi/"),
 ("Wuxi KingChe Vehicle Technology Co., Ltd.", "moto", ["Electric"], "Wuxi", "Jiangsu", "https://www.facebook.com/p/WUXI-KingChe-Vehicle-Technology-Co-Ltd-100063646977022/"),
 ("Taizhou UMI Electrombile", "moto", ["Electric"], "Taizhou", "Zhejiang", "https://www.facebook.com/p/Taizhou-UMI-electrombile-100064838208176/"),
 ("XDAO Electric Vehicle", "moto", ["Electric"], None, None, "https://www.facebook.com/xdaoelectricvehicle/"),
 ("SYING Motos", "moto", ["Off-road"], None, None, "https://www.facebook.com/SYMOTOS/"),
 ("Shuo Ke E-Bike", "moto", ["Electric"], None, None, "https://www.tiktok.com/@kewand.ebikefactory"),
 ("E-bird Electric Motorcycle", "moto", ["Electric"], None, None, "https://www.tiktok.com/@ebird.electric.mo"),
 ("Jiekai Helmet China", "helmet", ["Full face", "Modular / flip-up"], None, None, "https://www.facebook.com/jiekaihelmet/"),
 ("Helmet Factory China - BTL", "helmet", ["Full face"], None, None, "https://www.facebook.com/Helmet.Factory.China/"),
 ("Yunman Helmet Factory", "helmet", ["Full face"], None, None, "https://www.facebook.com/YunmanHelmetFactory/"),
 ("Masei Helmet", "helmet", ["Full face"], None, None, "https://www.facebook.com/MaseiHelmet/"),
 ("Sunning Sports Limited", "helmet", ["Full face"], None, None, "https://www.facebook.com/sunninghelmet/"),
 ("Dongguan Kuyou Helmets Co., Ltd.", "helmet", ["Full face"], "Dongguan", "Guangdong", "https://www.facebook.com/p/Dongguan-Kuyou-Helmets-Co-Ltd-100047581038128/"),
]
# Existing profiles: id -> (links, contacts, src)
EXIST = {
 "wuxi-chaoya-e-vehicle": (["https://www.facebook.com/electricscooters4you/", "https://www.youtube.com/channel/UCh_BKA1g_o7g9E9QFQx5PMw"], {"wa": "+86 15988835090", "emails": ["admin@ewheelscooter.com"], "web": "https://www.ewheelscooter.com"}, "https://www.youtube.com/channel/UCh_BKA1g_o7g9E9QFQx5PMw"),
 "linyi-youyuan-vehicle": (["https://www.facebook.com/Youyuanebike/", "https://www.youtube.com/channel/UCMAnlvsOyjIq4C1lP9MNnNA"], {"wa": "+86 18596389272", "phone": "+86 18596389272", "emails": ["sales1@youyuanev.com", "sales3@youyuanev.com"], "web": "https://www.y2ebike.com"}, "https://www.youtube.com/channel/UCMAnlvsOyjIq4C1lP9MNnNA"),
 "jiangmen-sonlink-motorcycle": (["https://www.facebook.com/sonlinkfactory/", "https://www.facebook.com/sonlinkmotorcycle/", "https://www.youtube.com/channel/UCtnmLUHbapmvA9cq4A8XbWA"], {"wa": "+86 15710765395", "wc": "+86 15710765395", "emails": ["sonlinksale02@sonlink-motor.com"]}, "https://www.youtube.com/channel/UCtnmLUHbapmvA9cq4A8XbWA"),
 "h-jiangmen-sonlink-motorcycle": (["https://www.youtube.com/channel/UCtnmLUHbapmvA9cq4A8XbWA"], {"wa": "+86 15710765395", "wc": "+86 15710765395", "emails": ["sonlinksale02@sonlink-motor.com"]}, "https://www.youtube.com/channel/UCtnmLUHbapmvA9cq4A8XbWA"),
}
FBEXIST = {
 "wuxi-dongma-vehicle": "https://www.facebook.com/wxdongma/", "jianshe": "https://www.facebook.com/jianshemotorcycle/",
 "chongqing-xcross-motorcycle": "https://www.facebook.com/xcrossmotorcycle/", "chongqing-rato-power": "https://www.facebook.com/Ratomotor/",
 "chongqing-beiyi-vehicle": "https://www.facebook.com/DAYANGTRICYCLE/", "lifan": "https://www.facebook.com/enjoylifan/",
 "chongqing-hongli-motorcycle": "https://www.facebook.com/p/Chongqing-Hongli-Motorcycle-Manufacture-Co-Ltd-100085324951183/",
 "zongshen": "https://www.facebook.com/ZonsenCyclone/", "bashan": "https://www.facebook.com/aerobs1/",
 "guangzhou-tianheng-motorcycle": "https://www.facebook.com/tianheng.motor/", "guangzhou-fekon-motorcycle": "https://www.facebook.com/fekonmotor/",
 "haojin": "https://www.facebook.com/Haojinofficial/", "wuxi-tenghui-electric-vehicles": "https://www.facebook.com/wxtenghui/",
 "jiangmen-blujet-motos": "https://www.facebook.com/symcot/", "jiangmen-qipai-motorcycle": "https://www.facebook.com/qipaimotor/",
 "baotian": "https://www.facebook.com/Baotianmotor/", "qjmotor": "https://www.facebook.com/QJMOTORGlobal/",
 "taizhou-okla-automobile": "https://www.facebook.com/okla.evehicles/", "wuxi-sino": "https://www.facebook.com/SinotechMotors/",
}
def slug(s): return "s-" + re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", re.sub(r"\(.*?\)", "", s.lower()))).strip("-")[:40]
def cfmt(c, src):
    o = {}
    if c.get("emails"): o["emails"] = [{"v": e, "src": src} for e in c["emails"]]
    for k in ("wa", "wc", "phone"):
        if c.get(k): o[k] = {"v": c[k], "src": src}
    if c.get("web"): o["web"] = c["web"]
    return o
F = json.load(open(f"{ROOT}/data/factories.json")); H = json.load(open(f"{ROOT}/data/helmets.json"))
F = [r for r in F if r.get("via") != "social"]; H = [r for r in H if r.get("via") != "social"]
ids = {r["id"] for r in F + H}
S = {}
def row(name, kind, types, city, prov, links, web, note, src):
    i = slug(name); assert i not in ids, i; ids.add(i)
    r = {"id": i, "name": name, "legal": None, "city": city or "", "prov": prov or "Not stated", "since": None, "emp": None, "cap": None, "markets": None,
         "web": web, "contact": links[0] if links else None, "emails": [], "emailNotes": [], "phone": None, "wa": None, "wc": None,
         "types": types, "cc": None, "eec": [], "non": [], "src": [u for u in [src] + links if u and u.startswith("http")][:3], "notes": note,
         "products": None, "bt": "Not stated", "via": "social", "tier": "basic", "sky": ["#28457a", "#7d9ccf"], "c": "#d98a1c", "social": links}
    if kind == "helmet": r.update({"kind": "helmet", "addr": None, "area": None, "usd": None, "maker": False})
    (H if kind == "helmet" else F).append(r); return i
for name, kind, types, city, prov, links, c, src, ph, note in NEW:
    i = row(name, kind, types, city, prov, links, c.get("web"), note, src or (links[0] if links else None))
    s = cfmt(c, src or c.get("web")) if src or c.get("web") else {}
    s.pop("web", None); s["links"] = links
    if ph:
        pics = [{"u": u, "alt": name + " factory", "from": src} for u in ph.get("factory", [])]
        prods = [{"u": f"https://i.ytimg.com/vi/{v}/hqdefault.jpg", "alt": name, "from": f"https://www.youtube.com/watch?v={v}"} for v in ph.get("yt", [])]
        s["ph"] = {"page": src, "products": prods, "factory": pics, "hero": [p["u"] for p in prods][:1]}
    S[i] = s
for name, kind, types, city, prov, link in FBONLY:
    i = row(name, kind, types, city, prov, [link], None, "Found on social media. Contacts are on their page (" + ("TikTok" if "tiktok" in link else "Facebook") + ").", link)
    S[i] = {"links": [link]}
allids = {r["id"] for r in F + H}
for i, (links, c, src) in EXIST.items():
    assert i in allids, i; s = cfmt(c, src); s["links"] = links; S[i] = s
for i, link in FBEXIST.items():
    assert i in allids, i; S.setdefault(i, {"links": []})["links"].append(link)
json.dump(F, open(f"{ROOT}/data/factories.json", "w"), ensure_ascii=False)
json.dump(H, open(f"{ROOT}/data/helmets.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(S, open(f"{ROOT}/data/social.json", "w"), ensure_ascii=False, indent=1, sort_keys=True)
newc = [i for i in S if i.startswith("s-")]
print("new profiles", len(newc), "moto", sum(1 for r in F if r.get("via") == "social"), "helmet", sum(1 for r in H if r.get("via") == "social"))
cnt = lambda ks: sum(len(S[i].get("emails", [])) + sum(1 for k in ("wa", "wc", "phone") if S[i].get(k)) for i in ks)
print("contacts on new", cnt(newc), "on existing", cnt(EXIST), "existing profiles with new social links", len(set(EXIST) | set(FBEXIST)))
