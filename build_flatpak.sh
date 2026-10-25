#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

APP_ID="io.github.Antux912012.debian-cachy-os-kernel-updater"
VERSION=$(grep -m1 '^APP_VERSION' main.py | sed -E 's/.*"([^"]+)".*/\1/')
BUILD_DIR="flatpak_build"
REPO_DIR="flatpak_repo"
BUNDLE_DIR="deb_dist"
BUNDLE_FILE="${BUNDLE_DIR}/${APP_ID}.flatpak"
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

if false; then
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
    install -D -m 644 io.github.Antux912012.debian-cachy-os-kernel-updater.desktop "${FLATPAK_DEST}/share/applications/io.github.Antux912012.debian-cachy-os-kernel-updater.desktop"
    install -D -m 644 io.github.Antux912012.debian-cachy-os-kernel-updater.metainfo.xml "${FLATPAK_DEST}/share/metainfo/io.github.Antux912012.debian-cachy-os-kernel-updater.metainfo.xml"
    install -D -m 644 io.github.Antux912012.debian-cachy-os-kernel-updater.metainfo.xml "${FLATPAK_DEST}/share/appdata/io.github.Antux912012.debian-cachy-os-kernel-updater.appdata.xml"
    install -D -m 644 assets/io.github.Antux912012.debian-cachy-os-kernel-updater.svg "${FLATPAK_DEST}/share/icons/hicolor/scalable/apps/io.github.Antux912012.debian-cachy-os-kernel-updater.svg"
    install -D -m 644 assets/logo_48.png "${FLATPAK_DEST}/share/icons/hicolor/48x48/apps/io.github.Antux912012.debian-cachy-os-kernel-updater.png"
    install -D -m 644 assets/logo_128.png "${FLATPAK_DEST}/share/icons/hicolor/128x128/apps/io.github.Antux912012.debian-cachy-os-kernel-updater.png"
    install -D -m 644 assets/logo_256.png "${FLATPAK_DEST}/share/icons/hicolor/256x256/apps/io.github.Antux912012.debian-cachy-os-kernel-updater.png"
    install -D -m 644 assets/logo_512.png "${FLATPAK_DEST}/share/icons/hicolor/512x512/apps/io.github.Antux912012.debian-cachy-os-kernel-updater.png"
    install -D -m 644 assets/logo_256.png "${FLATPAK_DEST}/share/pixmaps/io.github.Antux912012.debian-cachy-os-kernel-updater.png"

    mkdir -p "${FLATPAK_DEST}/share/app-info/xmls" "${FLATPAK_DEST}/share/app-info/icons/flatpak/128x128" "${FLATPAK_DEST}/share/app-info/icons/flatpak/64x64"
    install -m 644 assets/logo_128.png "${FLATPAK_DEST}/share/app-info/icons/flatpak/128x128/${APP_ID}.png"
    install -m 644 assets/logo_48.png "${FLATPAK_DEST}/share/app-info/icons/flatpak/64x64/${APP_ID}.png"

    if command -v appstream-compose >/dev/null 2>&1; then
        echo "[*] Running appstream-compose for Software Center & Bazaar..."
        appstream-compose --prefix="${FLATPAK_DEST}" --origin="${APP_ID}" --basename="${APP_ID}" "${APP_ID}" || true
    fi

    # Ensure composed AppStream XML exists and contains full <screenshots> block for Software Center, KDE Discover, and Bazaar
    python3 - "${FLATPAK_DEST}/share/app-info/xmls/${APP_ID}.xml.gz" "${FLATPAK_DEST}/share/app-info/xmls/flatpak.xml.gz" "${APP_ID}.metainfo.xml" "${APP_ID}" << 'PYEOF'
import gzip, sys, os

xml_gz_path = sys.argv[1]
flatpak_gz_path = sys.argv[2]
metainfo_path = sys.argv[3]
app_id = sys.argv[4]

if not os.path.exists(xml_gz_path):
    with open(metainfo_path, "r", encoding="utf-8") as mf:
        raw_meta = mf.read()
    body = raw_meta.split("<component", 1)[1]
    composed = f'<?xml version="1.0" encoding="UTF-8"?>\n<components version="0.8" origin="{app_id}">\n  <component{body}\n</components>\n'
    with gzip.open(xml_gz_path, "wt", encoding="utf-8") as f:
        f.write(composed)

if os.path.exists(xml_gz_path):
    with gzip.open(xml_gz_path, "rt", encoding="utf-8") as f:
        content = f.read()
    if "<screenshots>" not in content:
        screenshots_xml = """    <screenshots>
      <screenshot type="default">
        <caption>Main Dashboard — Kernel Selection, Isolated Container Build &amp; UEFI Secure Boot Status</caption>
        <image type="source" width="1296" height="770">https://raw.githubusercontent.com/Antux912012/debian-cachy-kernel-updater/main/assets/screenshots/screenshot-1-main.png</image>
      </screenshot>
      <screenshot>
        <caption>Advanced Kernel &amp; CPU Tuning — Fine-Grained Compiler, LTO, BORE Scheduler &amp; Tick Rate</caption>
        <image type="source" width="1296" height="770">https://raw.githubusercontent.com/Antux912012/debian-cachy-kernel-updater/main/assets/screenshots/screenshot-2-tuning.png</image>
      </screenshot>
      <screenshot>
        <caption>Live Kernel Compilation Progress &amp; Adaptive Build Log Terminal</caption>
        <image type="source" width="1296" height="770">https://raw.githubusercontent.com/Antux912012/debian-cachy-kernel-updater/main/assets/screenshots/screenshot-3-compiling.png</image>
      </screenshot>
    </screenshots>
"""
        content = content.replace("    <releases>", screenshots_xml + "    <releases>", 1)
        with gzip.open(xml_gz_path, "wt", encoding="utf-8") as f:
            f.write(content)
    with open(xml_gz_path, "rb") as src, open(flatpak_gz_path, "wb") as dst:
        dst.write(src.read())
PYEOF

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
    flatpak build-update-repo "${REPO_DIR}" || true
fi

echo "=== Packaging Flatpak Bundle: ${BUNDLE_FILE} ==="
flatpak build-bundle "${REPO_DIR}" "${BUNDLE_FILE}" "${APP_ID}"

echo "=== Flatpak Bundle Created Successfully ==="
ls -lh "${BUNDLE_FILE}"
