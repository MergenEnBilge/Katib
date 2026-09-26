#!/bin/sh
# Wraps the PyInstaller output in dist/Katib into a .deb for Debian, Ubuntu and Raspberry Pi OS.
# Run installers/build.py instead of calling this by hand.
#   installers/linux/make-deb.sh 0.1.0
set -eu

VERSION="${1:?Give the version, for example 0.1.0}"
ARCH="$(dpkg --print-architecture)"
ROOT="build/deb/katib_${VERSION}_${ARCH}"

# A frozen app only runs on the C library it was built against or newer, so the package asks for the
# version this machine has. Build on the oldest system you want to support.
GLIBC="$(ldd --version | head -1 | grep -oE '[0-9]+\.[0-9]+$')"

rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/opt/katib" "$ROOT/usr/bin" \
  "$ROOT/usr/share/applications" "$ROOT/usr/share/icons/hicolor/256x256/apps" dist/installers

cp -r dist/Katib/. "$ROOT/opt/katib/"
ln -s /opt/katib/Katib "$ROOT/usr/bin/katib-app"
cp installers/desktop/icon.png "$ROOT/usr/share/icons/hicolor/256x256/apps/katib.png"

cat > "$ROOT/usr/share/applications/katib.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Katib
Comment=Label images for machine learning
Exec=/opt/katib/Katib
Icon=katib
Categories=Graphics;Development;
Terminal=false
DESKTOP

cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: katib
Version: $VERSION
Section: graphics
Priority: optional
Architecture: $ARCH
Maintainer: Katib maintainers <noreply@users.noreply.github.com>
Depends: libc6 (>= $GLIBC), libgtk-3-0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0
Description: Image annotation tool
 Katib lets you draw boxes, outlines, keypoints and text on pictures and
 export them for training. It runs on your own computer.
CONTROL

dpkg-deb --build --root-owner-group "$ROOT" "dist/installers/katib_${VERSION}_${ARCH}.deb"
