#!/bin/sh
# Builds dist/pse-triglav_<version>_all.deb from this repository.
# Needs: dpkg-deb, python3. Run from the repository root: sh packaging/build_deb.sh
set -eu
VERSION=$(python3 -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
ROOT=$(mktemp -d)
PKG="$ROOT/pse-triglav_${VERSION}_all"
mkdir -p "$PKG/DEBIAN" "$PKG/usr/lib/python3/dist-packages" "$PKG/usr/bin" \
         "$PKG/usr/lib/systemd/user" "$PKG/usr/share/doc/pse-triglav"
cp -r triglav "$PKG/usr/lib/python3/dist-packages/"
find "$PKG" -name "__pycache__" -type d -prune -exec rm -rf {} +
cat > "$PKG/usr/bin/triglav" <<'SH'
#!/usr/bin/python3
from triglav.cli import main
raise SystemExit(main())
SH
chmod 755 "$PKG/usr/bin/triglav"
cp packaging/triglav.service "$PKG/usr/lib/systemd/user/triglav.service"
cp README.md GUIDE-EN.md VODIC-SR.md ROADMAP.md LICENSE "$PKG/usr/share/doc/pse-triglav/" 2>/dev/null || true
cat > "$PKG/DEBIAN/control" <<CTL
Package: pse-triglav
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-cryptography
Maintainer: Andrej Ristic / Zerava Technologies Inc. <info@zeravatech.ca>
Homepage: https://github.com/zeravatechnologies/pse-triglav
Description: PSE Triglav: agents that measure their theta against their mission
 Distributed oversight for teams of AI agents on the PSE framework: units beside
 our agents measure, SHARED_LIB alone concludes, the Guardian stops enemies on
 this system and the Physician takes our turned agents out of work. GPL-3.0.
CTL
mkdir -p dist
dpkg-deb --root-owner-group --build "$PKG" "dist/pse-triglav_${VERSION}_all.deb" >/dev/null
rm -rf "$ROOT"
echo "dist/pse-triglav_${VERSION}_all.deb"
