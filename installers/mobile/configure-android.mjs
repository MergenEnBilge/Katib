// Two changes Capacitor cannot make for us, applied to the generated Android project.
//
// Run this once after `npm run add:android`; running it again changes nothing.

import { readFile, writeFile } from 'node:fs/promises';

// Capacitor generates the project asking for Android 6, but the barcode scanner needs Android 8,
// and the build fails outright if the two disagree. Android 8 is from 2017.
const GRADLE = 'android/variables.gradle';
const NEEDED = 26;

const gradle = await readFile(GRADLE, 'utf8');
const match = gradle.match(/minSdkVersion\s*=\s*(\d+)/);
if (!match) throw new Error(`${GRADLE} does not set minSdkVersion`);

const current = Number(match[1]);
if (current >= NEEDED) {
  console.log(`${GRADLE} already asks for Android API ${current}`);
} else {
  await writeFile(GRADLE, gradle.replace(match[0], `minSdkVersion = ${NEEDED}`));
  console.log(`${GRADLE}: minSdkVersion ${current} -> ${NEEDED}`);
}

// Let an invite link open the app. Android hands katib:// addresses to whatever declares them, so
// the invite page can offer "Open in the Katib app" and fall back to downloading it when nothing
// answers. Capacitor writes the scheme into strings.xml but leaves the filter out.
const STRINGS = 'android/app/src/main/res/values/strings.xml';
const MANIFEST = 'android/app/src/main/AndroidManifest.xml';
const SCHEME = 'katib';

const strings = await readFile(STRINGS, 'utf8');
const scheme = /(<string name="custom_url_scheme">)[^<]*(<\/string>)/;
if (!scheme.test(strings)) throw new Error(`${STRINGS} does not set custom_url_scheme`);
await writeFile(STRINGS, strings.replace(scheme, `$1${SCHEME}$2`));

const manifest = await readFile(MANIFEST, 'utf8');
if (manifest.includes('custom_url_scheme')) {
  console.log(`${MANIFEST} already opens ${SCHEME}:// links`);
} else {
  const launcher = '<category android:name="android.intent.category.LAUNCHER" />\n            </intent-filter>';
  if (!manifest.includes(launcher)) throw new Error(`${MANIFEST} has no launcher intent filter`);
  const filter = `${launcher}

            <intent-filter>
                <action android:name="android.intent.action.VIEW" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.BROWSABLE" />
                <data android:scheme="@string/custom_url_scheme" />
            </intent-filter>`;
  await writeFile(MANIFEST, manifest.replace(launcher, filter));
  console.log(`${MANIFEST}: ${SCHEME}:// links now open the app`);
}
