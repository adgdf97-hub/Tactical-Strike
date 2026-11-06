#!/usr/bin/env python3
"""Merge the CS16 client payload into the decoded Xash3D FWGS project.

  --engine  apktool-decoded Xash3D APK directory (modified in place)
  --cs-raw  plain `unzip` of the CS16 client APK
Writes merge_report.json next to --engine.
"""
import argparse, hashlib, json, re, shutil, sys
from pathlib import Path
import xml.etree.ElementTree as ET

ANDROID = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID)
A = lambda n: "{%s}%s" % (ANDROID, n)
ABI = "armeabi-v7a"
LAUNCHER_ACTIVITY = "com.tacticalstrike.LauncherActivity"


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def strip_other_abis(engine: Path, rep: dict):
    removed = []
    for d in sorted((engine / "lib").iterdir()):
        if d.is_dir() and d.name != ABI:
            shutil.rmtree(d)
            removed.append(d.name)
    rep["abis_removed"] = removed


def merge_libs(engine: Path, cs_raw: Path, rep: dict):
    src, dst = cs_raw / "lib" / ABI, engine / "lib" / ABI
    if not src.is_dir():
        sys.exit("CS16 APK has no lib/%s" % ABI)
    dst.mkdir(parents=True, exist_ok=True)
    added, collisions = [], []
    for f in sorted(src.glob("*.so")):
        t = dst / f.name
        if t.exists():
            same = md5(t) == md5(f)
            collisions.append({"lib": f.name, "engine_size": t.stat().st_size,
                               "cs_size": f.stat().st_size, "identical": same,
                               "kept": "identical" if same else "CS16 version"})
        else:
            added.append(f.name)
        shutil.copy2(f, t)
    rep["libs_added_from_cs"] = added
    rep["lib_collisions"] = collisions


def merge_assets(engine: Path, cs_raw: Path, rep: dict):
    src, dst = cs_raw / "assets", engine / "assets"
    added, overridden = 0, []
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = f.relative_to(src)
        t = dst / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        if t.exists():
            if md5(t) != md5(f):
                overridden.append(str(rel))
        else:
            added += 1
        shutil.copy2(f, t)
    rep["assets_added"] = added
    rep["assets_overridden_by_cs"] = overridden

def patch_smali_package(engine: Path, old_pkg: str, new_pkg: str, rep: dict):
    if not old_pkg or not new_pkg or old_pkg == new_pkg:
        rep["smali_package_replacements"] = 0
        return

    replaced = 0
    for smali in engine.rglob("*.smali"):
        content = smali.read_text(encoding="utf-8")
        updated = content.replace(old_pkg, new_pkg)
        if updated != content:
            smali.write_text(updated, encoding="utf-8")
            replaced += 1

    rep["smali_package_replacements"] = replaced
def patch_manifest(engine: Path, new_pkg: str, label: str, rep: dict):
    mf = engine / "AndroidManifest.xml"
    tree = ET.parse(mf)
    root = tree.getroot()
    old_pkg = root.get("package")
    patch_smali_package(engine, old_pkg, new_pkg, rep)

    app = root.find("application")

    # 1. engine's own manager UI stops being the launcher
    removed = 0
    for act in app.findall("activity"):
        if act.get(A("name")) == "su.xash.engine.MainActivity":
            for f in act.findall("intent-filter"):
                if any(c.get(A("name")) == "android.intent.category.LAUNCHER"
                       for c in f.findall("category")):
                    act.remove(f)
                    removed += 1
    rep["engine_launcher_filters_removed"] = removed

    # 2. new launcher -> starts the in-APK engine with cstrike
    act = ET.SubElement(app, "activity", {
        A("name"): LAUNCHER_ACTIVITY, A("exported"): "true", A("label"): label,
        A("theme"): "@android:style/Theme.Translucent.NoTitleBar"})
    f = ET.SubElement(act, "intent-filter")
    ET.SubElement(f, "action", {A("name"): "android.intent.action.MAIN"})
    ET.SubElement(f, "category", {A("name"): "android.intent.category.LAUNCHER"})

    # 3. package rename (also authorities / permission names built from it)
    if new_pkg and new_pkg != old_pkg:
        root.set("package", new_pkg)
        for el in root.iter():
            for k, v in list(el.attrib.items()):
                if k != "package" and (v == old_pkg or v.startswith(old_pkg + ".")):
                    el.set(k, new_pkg + v[len(old_pkg):])
    rep["package"] = {"old": old_pkg, "new": root.get("package")}

    # 4. app label (targeted regex so string escaping is never rewritten)
    lbl = app.get(A("label")) or ""
    if lbl.startswith("@string/"):
        key, n = lbl[8:], 0
        pat = re.compile(r'(<string\s+name="%s"[^>]*>)(.*?)(</string>)' % re.escape(key), re.S)
        for sx in (engine / "res").glob("values*/strings.xml"):
            txt = sx.read_text(encoding="utf-8")
            new, c = pat.subn(lambda m: m.group(1) + label + m.group(3), txt)
            if c:
                sx.write_text(new, encoding="utf-8")
                n += 1
        rep["label_files_patched"] = n
    else:
        app.set(A("label"), label)
    tree.write(mf, encoding="utf-8", xml_declaration=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, type=Path)
    ap.add_argument("--cs-raw", required=True, type=Path)
    ap.add_argument("--package", default="com.tacticalstrike.game")
    ap.add_argument("--label", default="Tactical Strike")
    a = ap.parse_args()
    rep = {}
    strip_other_abis(a.engine, rep)
    merge_libs(a.engine, a.cs_raw, rep)
    merge_assets(a.engine, a.cs_raw, rep)
    patch_manifest(a.engine, a.package, a.label, rep)
    out = a.engine.parent / "merge_report.json"
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(json.dumps(rep, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
