/**
 * Opening Katib on a phone.
 *
 * Someone invited to a project scans a code and lands here in their phone's browser. If they have
 * the Katib app we would rather hand them over to it; if they do not, the same tap should fetch it.
 * Android has one mechanism for both: an `intent:` link carrying the address to open and, as a
 * fallback, somewhere to send the browser when nothing on the phone answers it.
 */

/** The Android package the app is published under. It must match capacitor.config.json. */
export const ANDROID_PACKAGE = 'io.github.mergenenbilge.katib';

/** The custom scheme the app registers. Also set in installers/mobile/configure-android.mjs. */
export const APP_SCHEME = 'katib';

/**
 * True for a phone browser that could hand over to the app. The app's own webview reports itself
 * as `wv`, and offering to open the app from inside the app would be a loop.
 */
export function isAndroidBrowser(userAgent: string): boolean {
  return /Android/i.test(userAgent) && !/\bwv\b/.test(userAgent);
}

/**
 * A link that opens `path` on `origin` in the Katib app, or downloads the app when it is missing.
 */
export function appLink(origin: string, path: string, downloadUrl: string): string {
  const target = `open?server=${encodeURIComponent(origin)}&path=${encodeURIComponent(path)}`;
  const fallback = encodeURIComponent(downloadUrl);
  return (
    `intent://${target}#Intent;scheme=${APP_SCHEME};package=${ANDROID_PACKAGE};` +
    `S.browser_fallback_url=${fallback};end`
  );
}
