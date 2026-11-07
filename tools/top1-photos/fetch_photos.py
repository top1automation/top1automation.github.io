#!/usr/bin/env python3
"""TOP1 site: one free-licensed photo per car model (Wikipedia infobox image, hosted on Wikimedia Commons).

Run on the AIGEN station, from this folder:
    python3 fetch_photos.py
Reads models.json, writes out/ (photos-N.webp sprite sheets, credits.json, review-N.jpg).
Only GET requests to en.wikipedia.org, commons.wikimedia.org and upload.wikimedia.org, about 3 per model, slowly.
Keeps only CC0 / public domain / CC BY / CC BY-SA images and records author + license for the site credits.
Re-running resumes from out/cache.json.
"""
import html, json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
UA = "TOP1-site-thumbnails/1.0 (small car-care business site, one-time fetch)"
W, H = 240, 150
PER_SHEET = 100
OK_LIC = re.compile(r"^(cc0|cc0 1\.0|public domain|pd|cc[ -]by(-sa)?([ -]\d(\.\d)?)?( [a-z]{2})?)$", re.I)


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** (i + 1))


def api(host, **p):
    p.update(format="json", formatversion="2")
    return json.loads(get("https://%s/w/api.php?%s" % (host, urllib.parse.urlencode(p))))


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def find(q):
    r = api("en.wikipedia.org", action="query", list="search", srsearch=q + " car", srlimit=3, srnamespace=0)
    hits = [h["title"] for h in r["query"]["search"]]
    for title in hits:
        p = api("en.wikipedia.org", action="query", prop="pageimages", piprop="name", titles=title)
        pg = p["query"]["pages"][0]
        if pg.get("pageimage"):
            return title, pg["pageimage"]
    return (hits[0] if hits else ""), None


def meta(fname):
    r = api("commons.wikimedia.org", action="query", prop="imageinfo", titles="File:" + fname,
            iiprop="url|extmetadata", iiurlwidth=640)
    pg = r["query"]["pages"][0]
    if "imageinfo" not in pg:
        return None
    ii = pg["imageinfo"][0]
    md = ii.get("extmetadata", {})
    return {"thumb": ii.get("thumburl") or ii["url"], "page": ii.get("descriptionurl"),
            "license": strip(md.get("LicenseShortName", {}).get("value")),
            "license_url": strip(md.get("LicenseUrl", {}).get("value")),
            "author": strip(md.get("Artist", {}).get("value"))[:120] or "Wikimedia Commons"}


def main():
    from PIL import Image, ImageDraw
    os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
    models = json.load(open(os.path.join(HERE, "models.json"), encoding="utf-8"))
    cache_p = os.path.join(OUT, "cache.json")
    cache = json.load(open(cache_p, encoding="utf-8")) if os.path.exists(cache_p) else {}
    credits, cells = [], []
    for n, m in enumerate(models):
        c = cache.get(m["slug"])
        if c is None:
            c = {"article": "", "file": None}
            try:
                title, f = find(m["q"])
                c["article"] = title
                if f:
                    md = meta(f)
                    if md and OK_LIC.match(md["license"]):
                        c.update(md)
                        c["file"] = f
                    elif md:
                        c["skip"] = "license: " + md["license"]
            except Exception as e:
                c["skip"] = "error: %s" % e
            cache[m["slug"]] = c
            json.dump(cache, open(cache_p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
            time.sleep(0.5)
        img = None
        if c.get("file"):
            p = os.path.join(OUT, "img", m["slug"] + ".jpg")
            if not os.path.exists(p):
                try:
                    data = get(c["thumb"])
                    open(p, "wb").write(data)
                    time.sleep(0.3)
                except Exception as e:
                    c["skip"] = "download: %s" % e
            if os.path.exists(p):
                im = Image.open(p).convert("RGB")
                s = max(W / im.width, H / im.height)
                im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
                l = (im.width - W) // 2
                t = max(0, int((im.height - H) * 0.45))
                img = im.crop((l, t, l + W, t + H))
        idx = len(cells) if img is not None else -1
        if img is not None:
            cells.append(img)
        credits.append({"slug": m["slug"], "name": m["name"], "i": idx, "article": c.get("article"),
                        "author": c.get("author"), "license": c.get("license"),
                        "license_url": c.get("license_url"), "page": c.get("page"), "skip": c.get("skip")})
        print("%3d/%d %-34s %s" % (n + 1, len(models), m["name"], "OK" if img is not None else c.get("skip", "no image")), flush=True)
    for s in range(0, len(cells), PER_SHEET):
        part = cells[s:s + PER_SHEET]
        sheet = Image.new("RGB", (W * 10, H * 10), (21, 25, 29))
        rev = Image.new("RGB", (W * 10, (H + 18) * 10), (0, 0, 0))
        d = ImageDraw.Draw(rev)
        names = [c for c in credits if s <= c["i"] < s + PER_SHEET]
        for k, im in enumerate(part):
            x, row = (k % 10) * W, k // 10
            sheet.paste(im, (x, row * H))
            rev.paste(im, (x, row * (H + 18)))
            d.text((x + 3, row * (H + 18) + H + 3), ("%d %s" % (s + k, names[k]["name"]))[:38], fill=(255, 255, 0))
        sheet.save(os.path.join(OUT, "photos-%d.webp" % (s // PER_SHEET)), quality=74, method=6)
        rev.save(os.path.join(OUT, "review-%d.jpg" % (s // PER_SHEET)), quality=70)
    json.dump({"w": W, "h": H, "per": PER_SHEET, "cols": 10, "items": credits},
              open(os.path.join(OUT, "credits.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    ok = sum(1 for c in credits if c["i"] >= 0)
    print("DONE %d/%d with photo, %d sheets" % (ok, len(credits), (len(cells) + PER_SHEET - 1) // PER_SHEET))


if __name__ == "__main__":
    main()
