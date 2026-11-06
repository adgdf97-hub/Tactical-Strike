#!/usr/bin/env python3
"""Inspect the FINAL apk. Exits non-zero if any check fails (so CI fails too)."""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ABI = "armeabi-v7a"
ENGINE_LIBS = ["libxash.so", "libSDL2.so", "libfilesystem_stdio.so", "libmenu.so",
               "libref_gles3compat.so", "libref_gles1.so", "libref_gl4es.so",
               "libavcodec.so", "libavformat.so", "libavutil.so",
               "libswresample.so", "libswscale.so"]
CS_LIBS = ["libclient_android_armv7l.so", "libcs_android_armv7l.so",
           "libmenu_android_armv7l.so", "libyapb_android_armv7l.so"]
REQUIRED_ASSETS = ["assets/touch.cfg", "assets/addons/yapb/conf/yapb.cfg",
                   "assets/cacert.pem", "assets/gfx/shell/btns_main.bmp",
                   "assets/userconfig.d/userconfig.cfg"]
SYSTEM_LIBS = {"libc.so", "libm.so", "libdl.so", "liblog.so", "libz.so", "libstdc++.so",
               "libGLESv1_CM.so", "libGLESv2.so", "libGLESv3.so", "libEGL.so",
               "libandroid.so", "libOpenSLES.so", "libjnigraphics.so", "libmediandk.so",
               "libaaudio.so", "libnativewindow.so", "libvulkan.so"}
LAUNCHER_CLASS = b"Lcom/tacticalstrike/LauncherActivity;"
fails, oks = [], []


def check(cond, msg):
    (oks if cond else fails).append(msg)
    print(("PASS  " if cond else "FAIL  ") + msg)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apk")
    ap.add_argument("--cs-apk", required=True)
    ap.add_argument("--package", default="com.tacticalstrike.game")
    ap.add_argument("--build-tools", default="")
    ap.add_argument("--skip-tools", action="store_true", help="dry run without SDK tools")
    a = ap.parse_args()

    z = zipfile.ZipFile(a.apk)
    names = set(z.namelist())
    cs = zipfile.ZipFile(a.cs_apk)
    check(os.path.basename(a.apk) == "Tactical-Strike-All-in-One-armeabi-v7a.apk",
          "final file name")

    so_names = sorted(n for n in names if n.startswith("lib/") and n.endswith(".so"))
    libs = {n.split("/", 2)[2] for n in so_names}
    abis = {n.split("/")[1] for n in so_names}
    check(abis == {ABI}, "only %s native dir present (found %s)" % (ABI, sorted(abis)))
    for l in ENGINE_LIBS:
        check(l in libs, "engine lib in APK: " + l)
    for l in CS_LIBS:
        check(l in libs, "CS16 lib in APK: " + l)

    k = "lib/%s/libclient_android_armv7l.so" % ABI
    if k in names:
        same = hashlib.sha256(z.read(k)).digest() == hashlib.sha256(cs.read(k)).digest()
        check(same, "libclient_android_armv7l.so is the CS16 client (not engine's HL client)")

    bad = []
    for n in so_names:
        d = z.read(n)
        if not (d[:4] == b"\x7fELF" and d[4] == 1 and int.from_bytes(d[18:20], "little") == 40):
            bad.append(n)
    check(not bad, "all .so are ELF32 / EM_ARM %s" % (bad or ""))

    if shutil.which("readelf"):
        missing = {}
        with tempfile.TemporaryDirectory() as td:
            for n in so_names:
                p = os.path.join(td, os.path.basename(n))
                with open(p, "wb") as fh:
                    fh.write(z.read(n))
                out = run(["readelf", "-d", p]).stdout
                for need in re.findall(r"NEEDED.*\[(.+?)\]", out):
                    if need not in SYSTEM_LIBS and need not in libs:
                        missing.setdefault(os.path.basename(n), []).append(need)
        check(not missing, "all non-system DT_NEEDED libs are bundled %s" % (missing or ""))

    dex_names = sorted(n for n in names if re.fullmatch(r"classes\d*\.dex", n))
    blob = b"".join(z.read(n) for n in dex_names)
    check(LAUNCHER_CLASS in blob, "launcher class present in dex")
    check(b"Lsu/xash/engine/XashActivity;" in blob, "engine XashActivity present in dex")
    ld = [n for n in dex_names if LAUNCHER_CLASS in z.read(n)]
    if ld:
        d = z.read(ld[0])
        check(b"github.com" not in d and b"android.intent.action.VIEW" not in d,
              "launcher has no 'download external engine' path")
    for r in REQUIRED_ASSETS:
        check(r in names, "asset present: " + r)
    check(any(n.startswith("assets/sound/radio/") for n in names), "CS radio sounds bundled")
    print("INFO  valve/cstrike game data inside APK: %s (expected: no, copyrighted)" %
          any(n.startswith(("assets/cstrike/", "assets/valve/")) for n in names))

    if not a.skip_tools:
        bt = a.build_tools
        out = run([os.path.join(bt, "aapt2"), "dump", "badging", a.apk]).stdout
        check("package: name='%s'" % a.package in out, "package id = " + a.package)
        check("launchable-activity: name='com.tacticalstrike.LauncherActivity'" in out,
              "launchable activity = LauncherActivity")
        nc = re.findall(r"native-code: (.*)", out)
        check(nc == ["'armeabi-v7a'"], "native-code armeabi-v7a only (%s)" % nc)
        check("uses-permission: name='android.permission.INTERNET'" in out, "INTERNET permission")
        m = re.search(r"targetSdkVersion:'(\d+)'", out)
        check(bool(m) and int(m.group(1)) >= 34, "targetSdk >= 34 (Android 14)")
        check(run([os.path.join(bt, "apksigner"), "verify", "--verbose", a.apk]).returncode == 0,
              "apksigner verify")
        check(run([os.path.join(bt, "zipalign"), "-c", "4", a.apk]).returncode == 0,
              "zipalign check")

    print("\n%d passed, %d failed" % (len(oks), len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
