#!/usr/bin/env python3
"""Replace the launcher icon of the apktool-decoded engine project.

  python3 scripts/apply_icon.py --engine work/engine --icon branding/icon.png

Finds the resource named by android:icon / android:roundIcon in the manifest, overwrites its
legacy PNGs (circle-cropped, transparent corners) in every density, and replaces the adaptive
icon xml with one built from the logo on a dark-green background.
"""
import argparse, re, sys
from pathlib import Path
from PIL import Image, ImageDraw

DENS = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
BG = "#FF0B1A0B"


def circle(img: Image.Image, size: int, frac: float = 0.985) -> Image.Image:
    img = img.convert("RGBA").resize((size * 4, size * 4), Image.LANCZOS)
    m = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(m)
    pad = img.size[0] * (1 - frac) / 2
    d.ellipse((pad, pad, img.size[0] - pad, img.size[1] - pad), fill=255)
    img.putalpha(m)
    return img.resize((size, size), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, type=Path)
    ap.add_argument("--icon", required=True, type=Path)
    a = ap.parse_args()
    res = a.engine / "res"
    mf = (a.engine / "AndroidManifest.xml").read_text(encoding="utf-8")
    refs = set(re.findall(r'android:(?:icon|roundIcon)="@(\w+)/([\w.]+)"', mf))
    if not refs:
        sys.exit("no @type/name icon reference in manifest")
    src = Image.open(a.icon)
    if src.width != src.height:
        s = min(src.size); src = src.crop(((src.width - s) // 2, (src.height - s) // 2,
                                           (src.width + s) // 2, (src.height + s) // 2))
    for rtype, name in sorted(refs):
        # drop every existing variant (png/webp/xml, any density/qualifier)
        for f in list(res.glob("%s*/%s.*" % (rtype, name))):
            f.unlink()
        for dn, px in DENS.items():
            d = res / ("%s-%s" % (rtype, dn)); d.mkdir(exist_ok=True)
            circle(src, px).save(d / (name + ".png"))
        # adaptive icon (API 26+): foreground = logo inside the safe zone
        (res / "drawable").mkdir(exist_ok=True)
        (res / "drawable-xxxhdpi").mkdir(exist_ok=True)
        fg = Image.new("RGBA", (432, 432), (0, 0, 0, 0))
        logo = circle(src, 300)
        fg.paste(logo, (66, 66), logo)
        fg.save(res / "drawable-xxxhdpi" / "ts_icon_fg.png")
        (res / "drawable" / "ts_icon_bg.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<shape xmlns:android="http://schemas.android.com/apk/res/android">'
            '<solid android:color="%s"/></shape>\n' % BG, encoding="utf-8")
        any26 = res / ("%s-anydpi-v26" % rtype); any26.mkdir(exist_ok=True)
        (any26 / (name + ".xml")).write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">'
            '<background android:drawable="@drawable/ts_icon_bg"/>'
            '<foreground android:drawable="@drawable/ts_icon_fg"/></adaptive-icon>\n',
            encoding="utf-8")
        print("icon replaced: @%s/%s" % (rtype, name))


if __name__ == "__main__":
    main()
