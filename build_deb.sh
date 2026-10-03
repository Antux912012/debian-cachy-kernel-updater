#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

PKG_NAME="cachy-kernel-updater"
PKG_VER="1.0.0"
DEB_DIR="deb_dist/${PKG_NAME}_${PKG_VER}_all"

echo "=== Cleaning previous deb staging directory ==="
rm -rf deb_dist
mkdir -p "${DEB_DIR}/DEBIAN"
mkdir -p "${DEB_DIR}/usr/bin"
mkdir -p "${DEB_DIR}/usr/share/cachy-kernel-updater"
mkdir -p "${DEB_DIR}/usr/share/applications"
mkdir -p "${DEB_DIR}/usr/share/icons/hicolor/scalable/apps"

echo "=== Creating Debian control file ==="
cat << 'EOF' > "${DEB_DIR}/DEBIAN/control"
Package: cachy-kernel-updater
Version: 1.0.0
Section: admin
Priority: optional
Architecture: all
Maintainer: Antonio <antonio@localhost>
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, python3-requests, gir1.2-gtk-4.0, gir1.2-adw-1, policykit-1 | polkitd, bc, libelf-dev, flex, bison, make, gcc, libssl-dev, rsync
Description: Debian CachyOS Kernel Installer & Updater (GTK4/Adwaita)
 A native GTK4/Libadwaita application to check, compile, install, and
 rollback CachyOS Linux kernels on Debian systems.
EOF

echo "=== Copying application files ==="
cp -v main.py kernel_manager.py "${DEB_DIR}/usr/share/cachy-kernel-updater/"
chmod 644 "${DEB_DIR}/usr/share/cachy-kernel-updater/"*.py

echo "=== Creating launcher binary (/usr/bin/cachy-kernel-updater) ==="
cat << 'EOF' > "${DEB_DIR}/usr/bin/cachy-kernel-updater"
#!/usr/bin/env bash
exec /usr/bin/python3 /usr/share/cachy-kernel-updater/main.py "$@"
EOF
chmod 755 "${DEB_DIR}/usr/bin/cachy-kernel-updater"

echo "=== Creating Desktop launcher entry ==="
cat << 'EOF' > "${DEB_DIR}/usr/share/applications/org.cachyos.debian.kernelupdater.desktop"
[Desktop Entry]
Name=CachyOS Kernel Updater
GenericName=Kernel Updater
Comment=Check, compile, install, and rollback CachyOS kernels on Debian
Exec=/usr/bin/cachy-kernel-updater
Icon=org.cachyos.debian.kernelupdater
Terminal=false
Type=Application
Categories=System;Settings;GTK;
StartupNotify=true
EOF
chmod 644 "${DEB_DIR}/usr/share/applications/org.cachyos.debian.kernelupdater.desktop"

echo "=== Creating SVG Application Icon ==="
cat << 'EOF' > "${DEB_DIR}/usr/share/icons/hicolor/scalable/apps/org.cachyos.debian.kernelupdater.svg"
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#3584e4"/>
      <stop offset="100%" stop-color="#1c71d8"/>
    </linearGradient>
    <linearGradient id="chip" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#241f31"/>
      <stop offset="100%" stop-color="#3d3846"/>
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#33d17a"/>
      <stop offset="100%" stop-color="#26a269"/>
    </linearGradient>
  </defs>
  <!-- Background squircle -->
  <rect x="8" y="8" width="112" height="112" rx="28" fill="url(#bg)"/>
  <!-- Central CPU / Kernel Chip -->
  <rect x="32" y="32" width="64" height="64" rx="12" fill="url(#chip)" stroke="#111" stroke-width="2"/>
  <!-- Pins -->
  <rect x="42" y="24" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="58" y="24" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="74" y="24" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="42" y="96" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="58" y="96" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="74" y="96" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="24" y="42" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="24" y="58" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="24" y="74" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="96" y="42" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="96" y="58" width="8" height="8" rx="2" fill="#e5a50a"/>
  <rect x="96" y="74" width="8" height="8" rx="2" fill="#e5a50a"/>
  <!-- Upgrade arrow inside chip -->
  <path d="M64 44 L78 60 L70 60 L70 76 L58 76 L58 60 L50 60 Z" fill="url(#accent)"/>
  <circle cx="64" cy="83" r="3" fill="url(#accent)"/>
</svg>
EOF
chmod 644 "${DEB_DIR}/usr/share/icons/hicolor/scalable/apps/org.cachyos.debian.kernelupdater.svg"

echo "=== Building .deb package with dpkg-deb ==="
dpkg-deb --root-owner-group --build "${DEB_DIR}" "deb_dist/${PKG_NAME}_${PKG_VER}_all.deb"

echo "=== Debian Package Created Successfully ==="
ls -lh "deb_dist/${PKG_NAME}_${PKG_VER}_all.deb"
