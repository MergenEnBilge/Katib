// Raises the oldest Android the app supports.
//
// Capacitor generates the project asking for Android 6, but the barcode scanner needs Android 8,
// and the build fails outright if the two disagree. Android 8 is from 2017. Run this once after
// `npm run add:android`; running it again changes nothing.

import { readFile, writeFile } from 'node:fs/promises';

const FILE = 'android/variables.gradle';
const NEEDED = 26;

const gradle = await readFile(FILE, 'utf8');
const match = gradle.match(/minSdkVersion\s*=\s*(\d+)/);
if (!match) throw new Error(`${FILE} does not set minSdkVersion`);

const current = Number(match[1]);
if (current >= NEEDED) {
  console.log(`${FILE} already asks for Android API ${current}`);
} else {
  await writeFile(FILE, gradle.replace(match[0], `minSdkVersion = ${NEEDED}`));
  console.log(`${FILE}: minSdkVersion ${current} -> ${NEEDED}`);
}
