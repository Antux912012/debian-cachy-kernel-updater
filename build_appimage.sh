#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=== Preparing staging environment in AppDir ==="
mkdir -p AppDir/usr/share/cachy-kernel-updater
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/pixmaps
mkdir -p AppDir/usr/share/icons/hicolor/scalable/apps
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps
mkdir -p AppDir/usr/share/icons/hicolor/512x512/apps

cp -v main.py kernel_manager.py AppDir/usr/share/cachy-kernel-updater/

# Copy official icons into AppDir
cp -v assets/org.cachyos.debian.kernelupdater.svg AppDir/usr/share/icons/hicolor/scalable/apps/
cp -v assets/logo_256.png AppDir/usr/share/icons/hicolor/256x256/apps/org.cachyos.debian.kernelupdater.png
cp -v assets/logo_512.png AppDir/usr/share/icons/hicolor/512x512/apps/org.cachyos.debian.kernelupdater.png
cp -v assets/logo_256.png AppDir/usr/share/pixmaps/org.cachyos.debian.kernelupdater.png
cp -v assets/logo_256.png AppDir/org.cachyos.debian.kernelupdater.png
cp -v assets/org.cachyos.debian.kernelupdater.svg AppDir/org.cachyos.debian.kernelupdater.svg

# Create desktop file in AppDir
cat << 'EOF' > AppDir/usr/share/applications/org.cachyos.debian.kernelupdater.desktop
[Desktop Entry]
Name=CachyOS Kernel Updater
GenericName=Kernel Updater
Comment=Check, compile, install, and rollback CachyOS kernels on Debian
Exec=usr/bin/python3 usr/share/cachy-kernel-updater/main.py
Icon=org.cachyos.debian.kernelupdater
Terminal=false
Type=Application
Categories=System;Settings;GTK;
StartupNotify=true
EOF
cp -v AppDir/usr/share/applications/org.cachyos.debian.kernelupdater.desktop AppDir/org.cachyos.debian.kernelupdater.desktop

# Ensure fake apt-key exists to bypass deprecated Debian 12 check in appimage-builder
if [ ! -f "apt-key" ]; then
    echo -e '#!/bin/bash\nexit 0' > apt-key
    chmod +x apt-key
fi

echo "=== Building AppImage ==="
PATH="$PWD:$PATH" appimage-builder --recipe AppImageBuilder.yml --skip-test

echo "=== Build Complete ==="
ls -lh *.AppImage
