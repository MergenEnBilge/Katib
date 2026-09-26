# Katib for Android and iPhone

A small app that connects to your Katib server and opens it full screen. Because it opens the
server's own web app, the phone always has the same version as everyone else, and nothing about
your data is stored in the app.

## Android

Download `Katib-android.apk` from the [releases page](https://github.com/MergenEnBilge/Katib/releases)
and open it on your phone. Android asks you to allow installs from your browser or file manager the
first time. The file is signed by the project's build, not by Google Play.

## iPhone and iPad

Apple only lets apps onto a phone through the App Store or through Xcode, so there is no file to
download the way there is on Android. Two ways in:

- **Add Katib to your home screen.** Open your server in Safari, tap the share button and choose
  **Add to Home Screen**. It runs full screen with its own icon and works offline for edits you have
  already made. This needs an `https` address. It is the quickest route and needs no Mac.
- **Build it yourself in Xcode.** On a Mac, follow the steps below and press Run with your iPhone
  connected. A free Apple ID installs it for seven days at a time; a paid developer account installs
  it for a year, or through TestFlight for other people.

## Enter your server

The app asks for the address the first time and remembers it. To change it later, tap the workspace
name on the home page and choose **Other servers**.

If your server does not use `https`, the app tells you before it connects. That is fine on your own
home network. Do not do it over the internet. On iPhone, plain `http` only works for addresses on
your own network.

## Building it yourself

Android needs Node 20 or newer, Java 21 and the Android SDK with platform 35. iOS needs a Mac with
Xcode.

```bash
cd installers/mobile
npm install
npm run add:android      # creates the android/ project (once)
npm run assets           # icons and splash screens from resources/
npm run sync

cd android && ./gradlew assembleDebug     # the APK
```

On a Mac you can also build for iPhone:

```bash
npm run add:ios          # creates the ios/ project (once)
npm run assets:ios
npm run sync
npm run ios              # opens Xcode
```

The APK lands in `android/app/build/outputs/apk/debug/app-debug.apk`. For iOS, `npm run ios` opens
the project in Xcode, where you choose your device and press Run.

The `mobile` workflow does the same steps. It always builds an APK, and it signs that APK when
`ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and
`ANDROID_KEY_PASSWORD` are set in the repository's secrets. It also builds the iOS app unsigned, to
prove it still compiles; that build cannot be installed on a phone.

## Changing the logo

Replace `brand/logo.png` and `brand/logo.svg` in the repository root and run
`python scripts/apply_brand.py`. It rewrites `resources/` and `www/logo.svg` here. Then run
`npm run assets` again.
