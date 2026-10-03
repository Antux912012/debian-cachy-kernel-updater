#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=== Preparing staging environment in AppDir ==="
mkdir -p AppDir/usr/share/cachy-kernel-updater
cp -v main.py kernel_manager.py AppDir/usr/share/cachy-kernel-updater/

# Ensure fake apt-key exists to bypass deprecated Debian 12 check in appimage-builder
if [ ! -f "apt-key" ]; then
    echo -e '#!/bin/bash\nexit 0' > apt-key
    chmod +x apt-key
fi

echo "=== Building AppImage ==="
PATH="$PWD:$PATH" appimage-builder --recipe AppImageBuilder.yml --skip-test

echo "=== Build Complete ==="
ls -lh *.AppImage
