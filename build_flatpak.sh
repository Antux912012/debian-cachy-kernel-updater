#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

APP_ID="org.cachyos.debian.kernelupdater"
VERSION="1.1.1"
BUILD_DIR="flatpak_build"
REPO_DIR="flatpak_repo"
BUNDLE_DIR="deb_dist"
BUNDLE_FILE="${BUNDLE_DIR}/cachy-kernel-updater_${VERSION}.flatpak"

mkdir -p "$BUNDLE_DIR"

echo "=== Building Flatpak for ${APP_ID} (v${VERSION}) ==="
flatpak-builder --force-clean --repo="${REPO_DIR}" "${BUILD_DIR}" "${APP_ID}.yml"

echo "=== Packaging Flatpak Bundle: ${BUNDLE_FILE} ==="
flatpak build-bundle "${REPO_DIR}" "${BUNDLE_FILE}" "${APP_ID}"

echo "=== Flatpak Bundle Created Successfully ==="
ls -lh "${BUNDLE_FILE}"
