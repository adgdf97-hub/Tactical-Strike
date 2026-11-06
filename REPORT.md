# Tactical Strike All-in-One - status report

## Status (honest)
- **NOT built, NOT run.** The sandbox has no network, apktool, Android SDK or device.
- What *was* checked here, on your two real APKs: contents, manifests, dex strings, ELF arch/deps,
  library-name collisions, and the lib/asset merge logic + manifest patch logic (dry run).
- The final APK is produced by the GitHub Actions workflow; its last step inspects the APK and fails the job on any problem.

## What the inputs really are
| APK | package | role |
|---|---|---|
| Xash3D_FWGS__Test__1 | su.xash.engine.test | the full engine: libxash, SDL2, filesystem_stdio, libmenu, ref_* renderers, ffmpeg libs, XashActivity |
| CS16Client-Android_1 | su.xash.cs16client.test | NOT standalone: a 2.7 KB dex whose MainActivity looks for su.xash.engine / su.xash.engine.test, and if absent opens a GitHub download page. Otherwise it starts su.xash.engine.XashActivity with extras gamedir=cstrike, gamelibdir=<its own nativeLibraryDir>, argv="-dev 2 -log -dll @yapb", package=<itself>. Carries the CS libs, touch UI, YaPB bots, radio sounds, tr_* maps. |

So the external-engine dependency is exactly that launcher; copying libclient.so alone would not remove it.

## Merge design (scripts/merge_project.py + LauncherActivity)
1. Base = the engine APK (decoded with apktool).
2. Add CS libs: libcs / libmenu_android / libyapb (no clash) and libclient_android_armv7l.so.
3. **Collision:** libclient_android_armv7l.so exists in both (engine = Half-Life client 681 KB, CS = 5.3 MB). The CS one wins; the HL client is shadowed (Half-Life itself will not run from this APK).
4. Assets: 741 CS files added; 3 conflicts resolved in favour of CS: gfx/shell/btns_main.bmp, touch_default/numbers.cfg, touch_presets/psvita.cfg.
5. Only lib/armeabi-v7a kept (arm64-v8a, x86 removed).
6. New com.tacticalstrike.LauncherActivity (compiled in CI) replaces the CS MainActivity: always starts the in-APK XashActivity, never looks for or downloads an external engine, and asks for "all files access" (the engine's own manager UI, which normally does that, is no longer the launcher).
7. Engine's MainActivity loses its LAUNCHER filter (class kept). Package renamed to com.tacticalstrike.game, label "Tactical Strike".
8. zipalign + apksigner, then verify_apk.py.

## Unverified assumptions - check on the first CI run / device
- Extra key names and values were read from dex strings of the original CS launcher, not from its code. CI saves build-report/original_cs16_launcher.smali so you can compare with LauncherActivity.
- Package rename is untested: the engine dex hardcodes "su.xash.engine.test.fileprovider" (used by its APK-install feature only). If the app crashes at start, set APP_PACKAGE to su.xash.engine.test in the workflow.
- Which menu lib the engine picks (libmenu.so vs libmenu_android_armv7l.so) and where it looks for valve/ and cstrike/ (base dir) is decided inside the engine; not verifiable offline.
- Online play: INTERNET permission, cleartext config and cacert.pem come from the engine and are kept; real server connection must be tested on device.
- Branding commit b7a4b5c (icons, strings) is not in the APKs, so only the label is applied. Drop a PNG-based icon swap into scripts/merge_project.py if wanted.
- Infinix Smart 9 / Android 14 / 32-bit: only armeabi-v7a is packaged; install on the device is the real test.

## Game data
Counter-Strike 1.6 files (valve/ and cstrike/: maps, models, sounds, pak) are NOT in either APK and are copyrighted. Copy them from your own install to the engine's base directory on the phone. Embedding them in a distributed APK needs a licence.

## How to run
1. Create a repo (or use Tactical-Strike branch android-source), unzip this project into it, commit.
2. Actions -> "Tactical Strike All-in-One (armeabi-v7a)" -> Run workflow.
3. Download artifact Tactical-Strike-All-in-One (APK + build-report/verify.txt, merge_report.json, apk_contents.txt).
4. Optional secrets for a stable signing key: KEYSTORE_B64, KEYSTORE_PASS, KEY_ALIAS, KEY_PASS. Without them a throw-away key is used.
