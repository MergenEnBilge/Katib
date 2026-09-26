# Katib for Android

A small app that connects to your Katib server and opens it full screen. Because it opens the
server's own web app, the phone always has the same version as everyone else, and nothing about
your data is stored in the app.

## Getting the app

Download `Katib-android.apk` from the [releases page](https://github.com/MergenEnBilge/Katib/releases)
and open it on your phone. Android asks you to allow installs from your browser or file manager the
first time. The file is signed by the project's build, not by Google Play.

Then enter your server's address. Katib remembers it and opens it straight away next time. To use a
different server, open the app's address screen again by clearing the app's storage in Android settings, or
choose one from **Other servers** in the window that opens when you tap the workspace name on the home page.

If your server does not use HTTPS, the app tells you before it connects. It is fine on your own home
network. Do not use it over the internet.

## Building it yourself

You need Node 20 or newer, Java 17 and the Android SDK.

```bash
cd android-app
npm install
npm run add          # creates the android/ project (once)
npm run assets       # icons and splash screen from resources/
npm run sync
cd android && ./gradlew assembleDebug
```

The APK is `android/app/build/outputs/apk/debug/app-debug.apk`. The release workflow does the same
steps and, when a signing key is set up in the repository's secrets, builds a release APK signed
with it (`ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`,
`ANDROID_KEY_PASSWORD`).

## Changing the logo

Replace `brand/logo.png` and `brand/logo.svg` in the repository root and run
`python scripts/apply_brand.py`. It rewrites `android-app/resources` and `android-app/www/logo.svg`.
Then run `npm run assets` again.
