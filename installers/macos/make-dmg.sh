#!/bin/sh
# Wraps dist/Katib.app into a disk image people can drag into Applications.
# Run installers/build.py instead of calling this by hand.
#   installers/macos/make-dmg.sh 0.1.0
set -eu

VERSION="${1:?Give the version, for example 0.1.0}"

rm -rf build/dmg
mkdir -p build/dmg dist/installers
cp -R dist/Katib.app build/dmg/
ln -s /Applications build/dmg/Applications

hdiutil create \
  -volname Katib \
  -srcfolder build/dmg \
  -ov -format UDZO \
  "dist/installers/Katib-${VERSION}-macos.dmg"
