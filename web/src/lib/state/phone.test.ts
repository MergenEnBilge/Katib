import { describe, expect, it } from 'vitest';
import { appLink, isAndroidBrowser } from './phone';

const CHROME_ON_ANDROID =
  'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36';
const KATIB_APP =
  'Mozilla/5.0 (Linux; Android 14; Pixel 7; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0 Mobile Safari/537.36';
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15';

describe('isAndroidBrowser', () => {
  it('is true in a phone browser that could hand over to the app', () => {
    expect(isAndroidBrowser(CHROME_ON_ANDROID)).toBe(true);
  });

  it('is false inside the app, which would otherwise offer to open itself', () => {
    expect(isAndroidBrowser(KATIB_APP)).toBe(false);
  });

  it('is false on a phone the app is not published for', () => {
    expect(isAndroidBrowser(IPHONE)).toBe(false);
  });
});

describe('appLink', () => {
  const link = appLink('http://192.168.1.20:8420', '/invite/abc123', 'https://example.com/app.apk');

  it('carries the server and the page to open', () => {
    expect(link).toContain('server=http%3A%2F%2F192.168.1.20%3A8420');
    expect(link).toContain('path=%2Finvite%2Fabc123');
  });

  it('falls back to the download when no app answers', () => {
    expect(link).toContain('S.browser_fallback_url=https%3A%2F%2Fexample.com%2Fapp.apk');
    expect(link.endsWith(';end')).toBe(true);
  });
});
