package com.tacticalstrike;

import android.Manifest;
import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.widget.Toast;

public class LauncherActivity extends Activity {

    private static final String ENGINE_ACTIVITY =
            "su.xash.engine.XashActivity";

    private static final String GAME_DIR = "cstrike";
    private static final String ENGINE_ARGS =
            "-dev 2 -log -dll @yapb";

    private static final int REQ_ALL_FILES = 1001;
    private static final int REQ_LEGACY_STORAGE = 1002;

    private boolean launched = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ensureStorageThenLaunch();
    }

    private void ensureStorageThenLaunch() {

        if (Build.VERSION.SDK_INT >= 30) {
            if (!Environment.isExternalStorageManager()) {
                try {
                    Intent intent = new Intent(
                            Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                            Uri.parse("package:" + getPackageName())
                    );
                    startActivityForResult(intent, REQ_ALL_FILES);
                    return;
                } catch (Exception e) {
                    showPermissionError();
                    return;
                }
            }

            launchEngine();
            return;
        }

        if (Build.VERSION.SDK_INT >= 23) {
            if (checkSelfPermission(
                    Manifest.permission.WRITE_EXTERNAL_STORAGE
            ) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(
                        new String[]{
                                Manifest.permission.WRITE_EXTERNAL_STORAGE
                        },
                        REQ_LEGACY_STORAGE
                );
                return;
            }
        }

        launchEngine();
    }

    @Override
    protected void onActivityResult(
            int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == REQ_ALL_FILES) {
            if (Environment.isExternalStorageManager()) {
                launchEngine();
            } else {
                showPermissionError();
            }
        }
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode,
            String[] permissions,
            int[] grantResults) {

        super.onRequestPermissionsResult(
                requestCode, permissions, grantResults
        );

        if (requestCode == REQ_LEGACY_STORAGE) {
            if (grantResults.length > 0
                    && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                launchEngine();
            } else {
                showPermissionError();
            }
        }
    }

    private void showPermissionError() {
        Toast.makeText(
                this,
                "Storage permission is required to run Tactical Strike.",
                Toast.LENGTH_LONG
        ).show();
        finish();
    }

    private void launchEngine() {
        if (launched) return;
        launched = true;

        Intent intent = new Intent();
        intent.setComponent(new ComponentName(
                getPackageName(),
                ENGINE_ACTIVITY
        ));

        intent.putExtra("gamedir", GAME_DIR);
        intent.putExtra(
                "gamelibdir",
                getApplicationInfo().nativeLibraryDir
        );
        intent.putExtra("argv", ENGINE_ARGS);
        intent.putExtra("package", getPackageName());

        intent.setFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK
                        | Intent.FLAG_ACTIVITY_CLEAR_TOP
        );

        try {
            startActivity(intent);
        } catch (Exception e) {
            Toast.makeText(
                    this,
                    "Engine start failed: " + e,
                    Toast.LENGTH_LONG
            ).show();
        }

        finish();
    }
}
