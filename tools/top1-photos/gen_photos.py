#!/usr/bin/env python3
"""TOP1 site: photos for the older generations (BMW E36, Golf 4, Corolla E11 ...).

Why a separate script: an English Wikipedia article usually covers many generations, so its main photo is often the
newest one (Astra F showed an Astra K). Here the first source is the Wikimedia Commons category of that exact generation
(gen_cats.py). Only when no category gives a usable photo does it fall back to a Commons search and then to the article,
and then the filename must name the generation (E36, Golf IV, W124 ...) or carry a model year inside the range.

Run on the AIGEN station, from this folder:
    python3 gen_photos.py            # all models of fixes-gen.json
Then out/review-fixes.jpg shows only these models, out/fix-report.txt says where each photo came from.
Only GET requests to commons.wikimedia.org and en.wikipedia.org, slowly.
"""
import json, os, re, sys, time
import fetch_photos as fp
import fix_photos as fx
from gen_cats import C

HERE, OUT = fp.HERE, fp.OUT
BAD = re.compile(r"interior|interieur|interno|innenraum|innen|inside|cockpit|dashboard|armaturen|engine|motorraum|"
                 r"rear|heckansicht|hinten|back view|badge|logo|emblem|wheel|felge|seats|sitze|trunk|kofferraum|steering|"
                 r"lenkrad|display|screen|headlight|taillight|scheinwerfer|detail|drawing|sketch|brochure|prospekt|advert|"
                 r"race|racing|rennen|rally|motorsport|rring|hockenheim|circuit|track|dtm|btcc|wtcc|stw|"
                 r"tuning|tuned|stance|lowered|modified|custom|widebody|drift|wreck|crash|unfall|rost|rusty|"
                 r"abandoned|derelict|scrap|junk|parts|model car|modellauto|toy|diecast|scale|lego|police|polizei|"
                 r"taxi|ambulance|feuerwehr|fire dep|hearse|limousine stretch|\.svg$|\.gif$|\.tif|\.pdf$|\.webm$|\.ogv$", re.I)
SKIP_SUBCAT = re.compile(r"interior|detail|engine|motor|race|racing|rally|motorsport|tuning|modified|police|taxi|"
                         r"model|toy|advert|brochure|wreck|crash|museum|logo|badge|wheel|light", re.I)
MODEL_YEAR = fx.MODEL_YEAR
FRONT = re.compile(r"front|vorne|frontansicht|avant|anteriore|voorkant|3/4|three.quarter|\bfl\b|\bfr\b", re.I)


def model_year(name):
    m = MODEL_YEAR.search(name)
    return int(m.group(1) or m.group(2)) if m else None


def ok(name, f, need_gk):
    if BAD.search(name) or any(n.lower() in name.lower() for n in f["neg"]):
        return False
    y = model_year(name)
    if y and (y < f["min_year"] - 1 or y > f["max_year"] + 1):
        return False
    if need_gk:
        gk = any(g.lower() in name.lower() for g in f["gk"])
        if not gk and not (y and f["min_year"] <= y <= f["max_year"]):
            return False
        if f["kw"] and not any(k.lower() in name.lower() for k in f["kw"]):
            return False
    return True


def score(name, f):
    s = 3 if FRONT.search(name) else 0
    if any(g.lower() in name.lower() for g in f["gk"]):
        s += 1
    y = model_year(name)
    if y and f["min_year"] <= y <= f["max_year"]:
        s += 1
    if re.search(r"\.jpe?g$", name, re.I):
        s += 0.5
    return s


def cat_files(cat, depth=1):
    r = fp.api("commons.wikimedia.org", action="query", list="categorymembers", cmtitle="Category:" + cat,
               cmtype="file|subcat", cmlimit="300")
    time.sleep(0.5)
    files, subs = [], []
    for m in r.get("query", {}).get("categorymembers", []):
        (files if m["ns"] == 6 else subs).append(m["title"])
    if depth and len(files) < 12:
        for s in [s for s in subs if not SKIP_SUBCAT.search(s)][:8]:
            files += cat_files(s[len("Category:"):], depth - 1)
    return files


def search_files(q):
    r = fp.api("commons.wikimedia.org", action="query", list="search", srsearch=q, srnamespace="6", srlimit="50")
    time.sleep(0.5)
    return [h["title"] for h in r.get("query", {}).get("search", [])]


def article_files(title):
    real, pimg = fx.resolve(title)
    time.sleep(0.5)
    if not real:
        return []
    out = (["File:" + pimg] if pimg else []) + fx.page_files(real)
    time.sleep(0.5)
    return out


def choose(cands, f, src):
    seen, uniq = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    uniq.sort(key=lambda c: score(c[5:], f), reverse=True)
    for i in range(0, min(len(uniq), 40), 20):
        good = fx.licensed(uniq[i:i + 20])
        time.sleep(0.5)
        for c in uniq[i:i + 20]:
            if c in good:
                md = good[c]
                md["file"] = c[5:]
                md["article"] = src
                return md
    return None


def pick(f):
    tried = []
    for cat in f["cats"]:
        files = [c for c in cat_files(cat) if ok(c[5:], f, False)]
        if files:
            md = choose(files, f, "Category:" + cat)
            if md:
                return md, tried
            tried.append(cat + ": no free license")
        else:
            tried.append(cat + ": empty or missing")
    files = [c for c in search_files(f["cats"][0]) if ok(c[5:], f, True)]
    if files:
        md = choose(files, f, "search: " + f["cats"][0])
        if md:
            return md, tried
    tried.append("search: nothing named for this generation")
    for t in f["titles"]:
        files = [c for c in article_files(t) if ok(c[5:], f, True)]
        if files:
            md = choose(files, f, t)
            if md:
                return md, tried
    tried.append("article: nothing named for this generation")
    return None, tried


def main(path="fixes-gen.json"):
    fixes = json.load(open(os.path.join(HERE, path), encoding="utf-8"))
    for f in fixes:
        f["cats"], f["gk"] = C[f["name"]]
    cache_p = os.path.join(OUT, "cache.json")
    cache = json.load(open(cache_p, encoding="utf-8"))
    report = []
    for n, f in enumerate(fixes):
        try:
            md, tried = pick(f)
        except Exception as e:
            print("%3d/%d %-34s ERROR %s (run again later)" % (n + 1, len(fixes), f["name"], e), flush=True)
            continue
        c = {"article": md["article"] if md else "", "file": None, "manual": True}
        if md:
            c.update(md)
        else:
            c["skip"] = "manual: no photo for this generation (" + "; ".join(tried)[:220] + ")"
        cache[f["slug"]] = c
        img = os.path.join(OUT, "img", f["slug"] + ".jpg")
        if os.path.exists(img):
            os.remove(img)
        json.dump(cache, open(cache_p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        line = "%3d/%d %-34s %s" % (n + 1, len(fixes), f["name"],
                                    ("OK [%s] %s" % (c["article"], c["file"])) if md else c["skip"])
        print(line, flush=True)
        report.append(line)
    open(os.path.join(OUT, "fix-report.txt"), "w", encoding="utf-8").write("\n".join(report) + "\n")
    fp.main()
    fx.review(fixes)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fixes-gen.json")
