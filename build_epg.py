#!/usr/bin/env python3
# build_epg.py — one light XMLTV containing ONLY the playlist's channels
import gzip, io, re, shutil, tempfile, time, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

PLAYLIST   = "yfr-FINAL.m3u"          # your final playlist (with fix6 applied)
OUT_XML    = "epg.xml"
OUT_GZ     = "epg.xml.gz"
OUT_REPORT = "coverage.txt"
HOURS_BACK, HOURS_AHEAD = 6, 96

SOURCES = [                            # only files that contain your IDs
 "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
 "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
 "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
 "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
 "https://epgshare01.online/epgshare01/epg_ripper_AT1.xml.gz",
 "https://epgshare01.online/epgshare01/epg_ripper_CZ1.xml.gz",
 "https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz",
 "https://i.mjh.nz/SamsungTVPlus/all.xml.gz",
 "https://i.mjh.nz/PlutoTV/all.xml.gz",
 "https://i.mjh.nz/Plex/all.xml.gz",
 "https://i.mjh.nz/Roku/all.xml.gz",
]

def open_auto(raw):
    return gzip.GzipFile(fileobj=io.BytesIO(raw)) if raw[:2] == b"\x1f\x8b" else io.BytesIO(raw)
def ts(t):
    return int(re.sub(r"\D", "", t or "")[:14])

utc  = datetime.now(timezone.utc)
lo   = int((utc - timedelta(hours=HOURS_BACK)).strftime("%Y%m%d%H%M%S"))
hi   = int((utc + timedelta(hours=HOURS_AHEAD)).strftime("%Y%m%d%H%M%S"))

ids = set(re.findall(r'tvg-id="([^"]+)"', open(PLAYLIST, encoding="utf-8").read())) - {""}
print(f"unique tvg-ids in playlist: {len(ids)}", flush=True)

chan_elems, seen, per = {}, set(), {i: 0 for i in ids}
tmp = tempfile.TemporaryFile(mode="w+", encoding="utf-8")

for url in SOURCES:
    print("fetch", url, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=900).read()
    ctx = ET.iterparse(open_auto(raw), events=("start", "end"))
    _, root = next(ctx)
    for ev, el in ctx:
        if ev != "end": continue
        if el.tag == "channel":
            cid = el.get("id")
            if cid in ids and cid not in chan_elems:
                chan_elems[cid] = ET.tostring(el, encoding="unicode")
        elif el.tag == "programme":
            cid, st = el.get("channel"), ts(el.get("start"))
            if cid in ids and lo <= st <= hi:
                key = (cid, st, ts(el.get("stop")))
                if key not in seen:
                    seen.add(key)
                    tmp.write(ET.tostring(el, encoding="unicode") + "\n")
                    per[cid] += 1
        else:
            continue
        el.clear(); root.clear()
    print(f"  channels kept: {sum(1 for _ in chan_elems)}  programmes so far: {sum(per.values())}", flush=True)

with open(OUT_XML, "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="rdvtds-personal-epg">\n')
    f.writelines(s + "\n" for s in chan_elems.values())
    tmp.seek(0); shutil.copyfileobj(tmp, f)
    f.write("</tv>\n")
with open(OUT_GZ, "wb") as f:
    with open(OUT_XML, "rb") as src: shutil.copyfileobj(src, f)

lines = [f"{per[i]:6d}  {i}" for i in sorted(ids, key=lambda x: -per[x])]
n0 = sum(1 for i in ids if per[i] == 0)
lines += ["", f"covered: {len(ids)-n0}/{len(ids)}   zero-programme: {n0}"]
lines += ["", "player header:", '#EXTM3U url-tvg="URL_OF_epg.xml.gz" x-tvg-url="URL_OF_epg.xml.gz"']
open(OUT_REPORT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
import os
print(f"epg.xml   {os.path.getsize(OUT_XML)/1e6:.2f} MB")
print(f"epg.xml.gz {os.path.getsize(OUT_GZ)/1e6:.2f} MB")
print("\n".join(lines))
