#!/usr/bin/env bash
# ==============================================================================
# Automated Release & Flathub Publisher for Debian CachyOS Kernel Updater
# App ID: io.github.Antux912012.debian-cachy-os-kernel-updater
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEV_ENV="/home/antonio/Projects/dev-env.sh"
APP_ID="io.github.Antux912012.debian-cachy-os-kernel-updater"
GITHUB_USER="Antux912012"

cd "$PROJECT_DIR"

usage() {
    cat <<EOF
Usage: ./scripts/release-flathub.sh <version> ["release notes"] [options]

Arguments:
  <version>         Semantic version (e.g., 1.1.5 or 1.2.0)
  "release notes"   Optional changelog summary (default: "Release version <version>")

Options:
  --first-submission  Target Flathub 'new-pr' branch on your fork (${GITHUB_USER}/flathub)
  --update-flathub    Target existing Flathub app repo (flathub/${APP_ID})
  --no-push           Prepare versions, validate, build packages, and tag locally without git push

Examples:
  ./scripts/release-flathub.sh 1.1.5 "Initial Flathub release" --first-submission
  ./scripts/release-flathub.sh 1.2.0 "Add Linux 6.19 support" --update-flathub
EOF
    exit 1
}

if [ $# -lt 1 ] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    usage
fi

VERSION="${1#v}"
shift

NOTES="Release version ${VERSION}"
if [ $# -gt 0 ] && [[ "$1" != --* ]]; then
    NOTES="$1"
    shift
fi

MODE="none"
NO_PUSH=false

while [ $# -gt 0 ]; do
    case "$1" in
        --first-submission) MODE="first" ;;
        --update-flathub)   MODE="update" ;;
        --no-push)          NO_PUSH=true ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
    shift
done

DATE_TODAY="$(date +%Y-%m-%d)"
TAG="v${VERSION}"

echo "=================================================================="
echo " Preparing Release ${TAG} (${DATE_TODAY}) for ${APP_ID}"
echo "=================================================================="

# 1. Sync version in main.py and kernel_manager.py
echo "[1/6] Syncing APP_VERSION = \"${VERSION}\" in main.py and kernel_manager.py..."
sed -i -E "s/^APP_VERSION = \"[^\"]+\"/APP_VERSION = \"${VERSION}\"/" main.py kernel_manager.py

# 2. Ensure <release version="${VERSION}"> exists in metainfo.xml
echo "[2/6] Updating ${APP_ID}.metainfo.xml..."
python3 - "${APP_ID}.metainfo.xml" "$VERSION" "$DATE_TODAY" "$NOTES" << 'PYEOF'
import sys

path, version, date_today, notes = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

if f'<release version="{version}"' in content:
    print(f"  -> Release {version} already present in {path}, keeping existing entry.")
else:
    entry = f"""  <releases>
    <release version="{version}" date="{date_today}">
      <description>
        <p>{notes}</p>
      </description>
    </release>"""
    content = content.replace("  <releases>", entry, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  -> Inserted <release version=\"{version}\" date=\"{date_today}\"> into {path}.")
PYEOF

# 3. Validate & Rebuild (.deb + .flatpak) inside Podman dev-debian container
echo "[3/6] Running desktop/AppStream validation & package builds inside Podman (dev-debian)..."
"$DEV_ENV" debian run bash -c "
    set -e
    cd /workspace/debian-cachy-kernel-updater
    desktop-file-validate ${APP_ID}.desktop
    appstreamcli validate --pedantic --explain ${APP_ID}.metainfo.xml
    ./build_deb.sh
    ./build_flatpak.sh
"

# 4. Commit and Tag Upstream Release
echo "[4/6] Committing release changes and tagging ${TAG}..."
git add main.py kernel_manager.py "${APP_ID}.metainfo.xml" "${APP_ID}.yml" "${APP_ID}.desktop" build_flatpak.sh
if ! git diff --cached --quiet; then
    git commit -m "Release ${TAG}: ${NOTES}"
fi
git tag -f "$TAG"
COMMIT_SHA="$(git rev-parse HEAD)"
echo "  -> Tagged ${TAG} at commit ${COMMIT_SHA}"

# 5. Update Flathub Submission Manifest with new tag & commit SHA
echo "[5/6] Locking tag (${TAG}) and commit (${COMMIT_SHA}) in flathub_submission/${APP_ID}.yml..."
sed -i -E "s|^([[:space:]]*tag:[[:space:]]*).*|\1${TAG}|" "flathub_submission/${APP_ID}.yml"
sed -i -E "s|^([[:space:]]*commit:[[:space:]]*).*|\1${COMMIT_SHA}|" "flathub_submission/${APP_ID}.yml"

# Keep flathub_submission manifest committed in main branch as well
git add "flathub_submission/${APP_ID}.yml" "flathub_submission/flathub.json"
if ! git diff --cached --quiet; then
    git commit --amend --no-edit
    git tag -f "$TAG"
    COMMIT_SHA="$(git rev-parse HEAD)"
    sed -i -E "s|^([[:space:]]*commit:[[:space:]]*).*|\1${COMMIT_SHA}|" "flathub_submission/${APP_ID}.yml"
fi

if [ "$NO_PUSH" = true ]; then
    echo "[6/6] --no-push specified. Skipping git push and Flathub branch push."
    echo "Done! Local packages are in deb_dist/ and Flathub manifest is in flathub_submission/."
    exit 0
fi

# 6. Push Upstream & Optionally Push Flathub PR Branch
echo "[6/6] Pushing upstream main and tag ${TAG} to origin..."
git push origin main
git push -f origin "$TAG"

if [ "$MODE" = "first" ]; then
    WORK_DIR="$(mktemp -d /tmp/flathub-first.XXXXXX)"
    trap 'rm -rf "$WORK_DIR"' EXIT
    echo "[*] Cloning https://github.com/${GITHUB_USER}/flathub.git (branch: new-pr)..."
    git clone --branch=new-pr --single-branch "https://github.com/${GITHUB_USER}/flathub.git" "$WORK_DIR"
    cd "$WORK_DIR"
    git checkout -b "${APP_ID}" new-pr
    cp "${PROJECT_DIR}/flathub_submission/${APP_ID}.yml" .
    cp "${PROJECT_DIR}/flathub_submission/flathub.json" .
    git add "${APP_ID}.yml" flathub.json
    git commit -m "Add ${APP_ID}"
    git push -f origin "${APP_ID}"
    echo ""
    echo "=================================================================="
    echo " SUCCESS! Open your Initial Flathub Submission PR at:"
    echo " https://github.com/flathub/flathub/compare/new-pr...${GITHUB_USER}:flathub:${APP_ID}?expand=1"
    echo "=================================================================="
elif [ "$MODE" = "update" ]; then
    WORK_DIR="$(mktemp -d /tmp/flathub-update.XXXXXX)"
    trap 'rm -rf "$WORK_DIR"' EXIT
    BRANCH_NAME="release-${TAG}"
    echo "[*] Cloning https://github.com/flathub/${APP_ID}.git..."
    git clone "https://github.com/flathub/${APP_ID}.git" "$WORK_DIR"
    cd "$WORK_DIR"
    git checkout -b "$BRANCH_NAME"
    cp "${PROJECT_DIR}/flathub_submission/${APP_ID}.yml" .
    cp "${PROJECT_DIR}/flathub_submission/flathub.json" .
    git add "${APP_ID}.yml" flathub.json
    git commit -m "Update ${APP_ID} to ${TAG}"
    git push -f origin "$BRANCH_NAME"
    echo ""
    echo "=================================================================="
    echo " SUCCESS! Open your Flathub Release Update PR at:"
    echo " https://github.com/flathub/${APP_ID}/compare/master...${BRANCH_NAME}?expand=1"
    echo "=================================================================="
else
    echo ""
    echo "=================================================================="
    echo " Upstream tag ${TAG} pushed (${COMMIT_SHA})."
    echo " Tip: Pass --first-submission or --update-flathub to also push"
    echo "      directly to your Flathub repository."
    echo "=================================================================="
fi
