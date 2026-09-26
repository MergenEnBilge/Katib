# Branding

Everything that shows Katib's logo comes from two files in this folder:

| File | Used for |
|------|----------|
| `logo.svg` | The logo inside the app, the browser tab icon and the loading screens. Any square vector logo works. |
| `logo.png` | The source for every app icon: the installers, the phone app, the home-screen icon and the favicon. Use a square PNG of at least 1024 by 1024 pixels with the logo filling most of it. |

The files here are placeholders. To use your own logo:

1. Replace `logo.svg` and `logo.png` with yours.
2. Run `python scripts/apply_brand.py`.
3. Rebuild the web app with `pnpm --dir web build`.

The script rewrites the icons in `web/public`, `installers/desktop` and `installers/mobile/resources`. It does not touch anything else, so you can run it as often as you like.

If your logo has a solid background color, the script picks it up from the top-left pixel of `logo.png` and uses it behind the icons that need padding, such as the Android adaptive icon.

The name and colors used in the interface live in `web/src/lib/brand.ts` and `web/src/tokens.css`.
