#!/usr/bin/env python3
"""TOP1 site: second pass for the models whose first photo was wrong (wrong article, wrong car, old generation,
interior shot, or a license outside CC0 / public domain / CC BY / CC BY-SA).

Run on the AIGEN station, from this folder, after fetch_photos.py:
    python3 fix_photos.py [fixes-3.json]   # picks a new photo for every entry of the file, then rebuilds out/
Reads fixes.json: for each model a list of exact Wikipedia article titles to try, filename keywords the photo must
contain (kw), words it must not contain (neg), the oldest model year allowed in the filename (min_year) and,
for older generations, the newest model year allowed (max_year).
Takes the article's infobox photo if it passes, otherwise the best matching photo on that article.
If nothing passes, the model gets no photo (the site shows its shape thumbnail instead).
Only GET requests to en.wikipedia.org and commons.wikimedia.org, slowly; downloads happen in fetch_photos.main().
"""
import json, os, re, time
import fetch_photos as fp

HERE = fp.HERE
OUT = fp.OUT
BAD = re.compile(r"interior|interieur|innenraum|innen|cockpit|dashboard|armaturen|engine|rear|heckansicht|hinten|"
                 r"badge|logo|emblem|wheel|felge|seats|sitze|trunk|kofferraum|steering|lenkrad|display|screen|"
                 r"taillight|headlight|scheinwerfer|detail|drawing|sketch|\.svg$|\.gif$|\.tif", re.I)
YEAR = re.compile(r"(?<!\d)(19[5-9]\d|20[0-3]\d)(?!\d)")
# model year as photographers write it: at the start ("1997 BMW 318i ...") or in brackets ("Golf (1998)");
# a date later in the name is when the photo was taken, so it is not used for max_year
MODEL_YEAR = re.compile(r"^(19[5-9]\d|20[0-3]\d)(?!\d)|\((19[5-9]\d|20[0-3]\d)(?!\d)")


def ok_name(f, fx):
    name = f[5:] if f.startswith("File:") else f
    if BAD.search(name):
        return False
    if fx["kw"] and not any(k.lower() in name.lower() for k in fx["kw"]):
        return False
    if any(n.lower() in name.lower() for n in fx["neg"]):
        return False
    ys = [int(y) for y in YEAR.findall(name)]
    if ys and min(ys) < fx.get("min_year", 0):
        return False
    my = MODEL_YEAR.search(name)
    if my and fx.get("max_year") and int(my.group(1) or my.group(2)) > fx["max_year"] + 1:
        return False
    return True


def score(f):
    name = f.lower()
    s = 0
    if "front" in name or "vorne" in name or "frontansicht" in name:
        s += 3
    ys = [int(y) for y in YEAR.findall(name)]
    if ys:
        s += (max(ys) - 1990) / 100.0
    return s


def resolve(title):
    r = fp.api("en.wikipedia.org", action="query", prop="pageimages", piprop="name", titles=title, redirects="1")
    pg = r["query"]["pages"][0]
    if pg.get("missing") or pg.get("invalid"):
        return None, None
    return pg["title"], pg.get("pageimage")


def page_files(title):
    r = fp.api("en.wikipedia.org", action="query", prop="images", titles=title, imlimit="200")
    return [i["title"] for i in r["query"]["pages"][0].get("images", [])]


def licensed(files):
    """files: 'File:...' titles (max 20). Returns {title: meta} for those with an allowed license."""
    r = fp.api("commons.wikimedia.org", action="query", prop="imageinfo", titles="|".join(files),
               iiprop="url|extmetadata", iiurlwidth=640)
    good = {}
    for pg in r["query"]["pages"]:
        if "imageinfo" not in pg:
            continue
        ii = pg["imageinfo"][0]
        md = ii.get("extmetadata", {})
        lic = fp.strip(md.get("LicenseShortName", {}).get("value"))
        if not fp.OK_LIC.match(lic):
            continue
        good[pg["title"]] = {"thumb": ii.get("thumburl") or ii["url"], "page": ii.get("descriptionurl"),
                             "license": lic, "license_url": fp.strip(md.get("LicenseUrl", {}).get("value")),
                             "author": fp.strip(md.get("Artist", {}).get("value"))[:120] or "Wikimedia Commons"}
    return good


def pick(fx):
    tried = []
    for title in fx["titles"]:
        real, pimg = resolve(title)
        time.sleep(0.5)
        if not real:
            tried.append(title + ": no article")
            continue
        cands = []
        if pimg and ok_name("File:" + pimg, fx):
            cands.append("File:" + pimg)
        rest = [f for f in page_files(real) if ok_name(f, fx) and f not in cands]
        time.sleep(0.5)
        rest.sort(key=score, reverse=True)
        cands += rest[:19]
        if not cands:
            tried.append(real + ": no matching photo")
            continue
        good = licensed(cands)
        time.sleep(0.5)
        for f in cands:
            if f in good:
                md = good[f]
                md["file"] = f[5:]
                md["article"] = real
                return md, tried
        tried.append(real + ": no free license")
    return None, tried


def main(path="fixes.json"):
    fixes = json.load(open(os.path.join(HERE, path), encoding="utf-8"))
    cache_p = os.path.join(OUT, "cache.json")
    cache = json.load(open(cache_p, encoding="utf-8"))
    report = []
    for n, fx in enumerate(fixes):
        try:
            md, tried = pick(fx)
        except Exception as e:
            print("%2d/%d %-30s ERROR %s (run again later)" % (n + 1, len(fixes), fx["name"], e), flush=True)
            continue
        c = {"article": md["article"] if md else "", "file": None, "manual": True}
        if md:
            c.update(md)
        else:
            c["skip"] = "manual: no good free photo (" + "; ".join(tried)[:200] + ")"
        cache[fx["slug"]] = c
        img = os.path.join(OUT, "img", fx["slug"] + ".jpg")
        if os.path.exists(img):
            os.remove(img)
        json.dump(cache, open(cache_p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        line = "%2d/%d %-30s %s" % (n + 1, len(fixes), fx["name"], ("OK " + c["file"]) if md else c["skip"])
        print(line, flush=True)
        report.append(line)
    open(os.path.join(OUT, "fix-report.txt"), "w", encoding="utf-8").write("\n".join(report) + "\n")
    fp.main()
    review(fixes)


def review(fixes):
    """out/review-fixes.jpg: only the re-picked models, with their names, for a quick visual check."""
    from PIL import Image, ImageDraw
    W, H = 240, 150
    rows = (len(fixes) + 9) // 10
    rev = Image.new("RGB", (W * 10, (H + 18) * rows), (0, 0, 0))
    d = ImageDraw.Draw(rev)
    for k, f in enumerate(fixes):
        x, y = (k % 10) * W, (k // 10) * (H + 18)
        p = os.path.join(OUT, "img", f["slug"] + ".jpg")
        if os.path.exists(p):
            im = Image.open(p).convert("RGB")
            s = max(W / im.width, H / im.height)
            im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
            l, t = (im.width - W) // 2, max(0, int((im.height - H) * 0.45))
            rev.paste(im.crop((l, t, l + W, t + H)), (x, y))
        d.text((x + 3, y + H + 3), ("%d %s" % (k, f["name"]))[:38], fill=(255, 255, 0))
    rev.save(os.path.join(OUT, "review-fixes.jpg"), quality=72)


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "fixes.json")
