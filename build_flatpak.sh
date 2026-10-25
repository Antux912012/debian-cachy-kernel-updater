#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

APP_ID="org.cachyos.debian.kernelupdater"
VERSION=$(grep -m1 '^APP_VERSION' main.py | sed -E 's/.*"([^"]+)".*/\1/')
BUILD_DIR="flatpak_build"
REPO_DIR="flatpak_repo"
BUNDLE_DIR="deb_dist"
BUNDLE_FILE="${BUNDLE_DIR}/cachy-kernel-updater_${VERSION}.flatpak"
RUNTIME_VER=$(grep -m1 '^runtime-version:' "${APP_ID}.yml" | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/")

mkdir -p "$BUNDLE_DIR"

# Ensure ambient/inheritable capabilities are cleared if running as non-root inside a container
# so bubblewrap (bwrap) and flatpak-validate-icon do not fail with "Unexpected capabilities but not setuid"
if [ "$(id -u)" != "0" ] && command -v setpriv >/dev/null 2>&1; then
    if ! grep -q '^CapEff:[[:space:]]*0000000000000000$' /proc/self/status 2>/dev/null; then
        exec setpriv --inh-caps=-all --ambient-caps=-all "$0" "$@"
    fi
fi

echo "=== Building Flatpak for ${APP_ID} (v${VERSION}, runtime: org.gnome.Platform//${RUNTIME_VER}) ==="

rm -rf "${BUILD_DIR}"

if bwrap --ro-bind / / true >/dev/null 2>&1 && flatpak info "org.gnome.Sdk//${RUNTIME_VER}" >/dev/null 2>&1; then
    flatpak-builder --disable-rofiles-fuse --force-clean --repo="${REPO_DIR}" "${BUILD_DIR}" "${APP_ID}.yml"
else
    echo "[*] Building Flatpak tree via flatpak build-init / build-finish (container-compatible mode)..."
    mkdir -p "${BUILD_DIR}/files" "${BUILD_DIR}/var"
    cat << EOF > "${BUILD_DIR}/metadata"
[Application]
name=${APP_ID}
runtime=org.gnome.Platform/$(uname -m)/${RUNTIME_VER}
sdk=org.gnome.Sdk/$(uname -m)/${RUNTIME_VER}
EOF

    FLATPAK_DEST="${BUILD_DIR}/files"

    # 1. Install Python dependencies from wheels
    install -d "${FLATPAK_DEST}/lib/python3/site-packages"
    python3 -c '
import glob, zipfile, sys
for whl in glob.glob("flatpak/wheels/*.whl"):
    with zipfile.ZipFile(whl, "r") as z:
        z.extractall(sys.argv[1])
' "${FLATPAK_DEST}/lib/python3/site-packages"

    # 2. Install application files
    install -d "${FLATPAK_DEST}/share/cachy-kernel-updater"
    install -m 644 main.py kernel_manager.py Containerfile "${FLATPAK_DEST}/share/cachy-kernel-updater/"
    install -m 755 sign-kernel.sh "${FLATPAK_DEST}/share/cachy-kernel-updater/"
    cp -r assets "${FLATPAK_DEST}/share/cachy-kernel-updater/"

    # 3. Create launcher script
    install -d "${FLATPAK_DEST}/bin"
    cat << 'EOF' > "${FLATPAK_DEST}/bin/cachy-kernel-updater"
#!/usr/bin/env bash
export PYTHONPATH="/app/lib/python3/site-packages:${PYTHONPATH}"
for sp in /app/lib/python*/site-packages /app/lib64/python*/site-packages; do
    if [ -d "$sp" ]; then
        export PYTHONPATH="${sp}:${PYTHONPATH}"
    fi
done
exec /usr/bin/python3 /app/share/cachy-kernel-updater/main.py "$@"
EOF
    chmod 755 "${FLATPAK_DEST}/bin/cachy-kernel-updater"

    # 4. Install desktop, metainfo, and icons
    install -D -m 644 org.cachyos.debian.kernelupdater.desktop "${FLATPAK_DEST}/share/applications/org.cachyos.debian.kernelupdater.desktop"
    install -D -m 644 org.cachyos.debian.kernelupdater.metainfo.xml "${FLATPAK_DEST}/share/metainfo/org.cachyos.debian.kernelupdater.metainfo.xml"
    install -D -m 644 assets/org.cachyos.debian.kernelupdater.svg "${FLATPAK_DEST}/share/icons/hicolor/scalable/apps/org.cachyos.debian.kernelupdater.svg"
    install -D -m 644 assets/logo_48.png "${FLATPAK_DEST}/share/icons/hicolor/48x48/apps/org.cachyos.debian.kernelupdater.png"
    install -D -m 644 assets/logo_128.png "${FLATPAK_DEST}/share/icons/hicolor/128x128/apps/org.cachyos.debian.kernelupdater.png"
    install -D -m 644 assets/logo_256.png "${FLATPAK_DEST}/share/icons/hicolor/256x256/apps/org.cachyos.debian.kernelupdater.png"
    install -D -m 644 assets/logo_512.png "${FLATPAK_DEST}/share/icons/hicolor/512x512/apps/org.cachyos.debian.kernelupdater.png"
    install -D -m 644 assets/logo_256.png "${FLATPAK_DEST}/share/pixmaps/org.cachyos.debian.kernelupdater.png"

    # 5. Finalize permissions and export to OSTree repository
    flatpak build-finish "${BUILD_DIR}" \
        --command=cachy-kernel-updater \
        --share=ipc \
        --share=network \
        --socket=fallback-x11 \
        --socket=wayland \
        --device=dri \
        --filesystem=host \
        --filesystem=/var/lib/dpkg:ro \
        --filesystem=/boot:ro \
        --filesystem=/sys/firmware/efi/efivars:ro \
        --talk-name=org.freedesktop.Flatpak \
        --talk-name=org.freedesktop.Notifications \
        --system-talk-name=org.freedesktop.PolicyKit1

    flatpak build-export "${REPO_DIR}" "${BUILD_DIR}"
fi

echo "=== Packaging Flatpak Bundle: ${BUNDLE_FILE} ==="
flatpak build-bundle "${REPO_DIR}" "${BUNDLE_FILE}" "${APP_ID}"

echo "=== Flatpak Bundle Created Successfully ==="
ls -lh "${BUNDLE_FILE}"
