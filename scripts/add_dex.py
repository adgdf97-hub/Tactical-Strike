#!/usr/bin/env python3
"""Append a dex file to an APK as the next free classesN.dex (native multidex, minSdk>=21)."""
import re
import sys
import zipfile

src, dex, out = sys.argv[1:4]
zin = zipfile.ZipFile(src)
idx = set()
for n in zin.namelist():
    m = re.fullmatch(r"classes(\d*)\.dex", n)
    if m:
        idx.add(int(m.group(1) or 1))
nxt = (max(idx) + 1) if idx else 1
new = "classes%d.dex" % nxt if nxt > 1 else "classes.dex"
with zipfile.ZipFile(out, "w") as zout:
    for info in zin.infolist():
        zout.writestr(info, zin.read(info.filename))
    zout.write(dex, new, compress_type=zipfile.ZIP_DEFLATED)
print("added", dex, "as", new)
