#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
cd "$DIR"

VERSION="${VERSION:-1.1.2}"
KEY_ID="620D1EA9AC45150575E70825BEE28F80428556CF"
REPO_URL="https://antux912012.github.io/debian-cachy-kernel-updater"
REPO_DIR="/tmp/cachyos-apt-repo-staging"

echo "=== 1. Preparing staging directory for APT repository ==="
rm -rf "$REPO_DIR"
mkdir -p "$REPO_DIR/pool/main/c/cachy-kernel-updater"
mkdir -p "$REPO_DIR/dists/stable/main/binary-all"
mkdir -p "$REPO_DIR/dists/stable/main/binary-amd64"

echo "=== 2. Copying .deb and .flatpak packages ==="
if [ ! -f "deb_dist/cachy-kernel-updater_${VERSION}_all.deb" ]; then
    echo "deb_dist package not found, building..."
    ./build_deb.sh
fi

if [ ! -f "deb_dist/cachy-kernel-updater_${VERSION}.flatpak" ]; then
    echo "flatpak bundle not found, building..."
    ./build_flatpak.sh
fi

cp -v deb_dist/cachy-kernel-updater_*.deb "$REPO_DIR/pool/main/c/cachy-kernel-updater/"
cp -v deb_dist/cachy-kernel-updater_*.flatpak "$REPO_DIR/"
cp -v assets/logo_256.png "$REPO_DIR/logo.png"

echo "=== 3. Generating Packages and Packages.gz ==="
cd "$REPO_DIR"
dpkg-scanpackages --multiversion pool/main /dev/null > dists/stable/main/binary-all/Packages
gzip -9c dists/stable/main/binary-all/Packages > dists/stable/main/binary-all/Packages.gz

# Mirror to binary-amd64 so apt works regardless of requested arch
cp -av dists/stable/main/binary-all/Packages dists/stable/main/binary-amd64/Packages
cp -av dists/stable/main/binary-all/Packages.gz dists/stable/main/binary-amd64/Packages.gz

echo "=== 4. Generating Release file with apt-ftparchive ==="
cd "$REPO_DIR/dists/stable"
apt-ftparchive \
    -o APT::FTPArchive::Release::Origin="CachyOS Kernel Updater" \
    -o APT::FTPArchive::Release::Label="CachyOS Kernel Updater" \
    -o APT::FTPArchive::Release::Suite="stable" \
    -o APT::FTPArchive::Release::Codename="stable" \
    -o APT::FTPArchive::Release::Architectures="all amd64" \
    -o APT::FTPArchive::Release::Components="main" \
    -o APT::FTPArchive::Release::Description="Official Debian APT repository for CachyOS Kernel Installer & Updater" \
    release . > Release

echo "=== 5. Signing Release file with GPG ==="
# Detached signature
gpg --batch --yes --default-key "$KEY_ID" -abs -o Release.gpg Release
# Inline clearsigned signature
gpg --batch --yes --default-key "$KEY_ID" --clearsign -o InRelease Release

cd "$REPO_DIR"
echo "=== 6. Creating distribution mirrors (bookworm, trixie, sid) ==="
for dist in bookworm trixie sid; do
    cp -r dists/stable "dists/$dist"
done

echo "=== 7. Exporting GPG public keys ==="
gpg --armor --export "$KEY_ID" > KEY.asc
gpg --export "$KEY_ID" > KEY.gpg
gpg --export "$KEY_ID" > cachy-kernel-updater-keyring.gpg

echo "=== 8. Creating web landing page (index.html) ==="
cat << 'EOF' > index.html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CachyOS Kernel Updater - Debian APT Repository</title>
  <style>
    :root {
      --bg: #0b1214;
      --card-bg: #121c1f;
      --text: #e0f2f1;
      --accent: #00a896;
      --accent-grad: linear-gradient(135deg, #00a896, #028090);
      --crimson: #d82655;
      --border: #1f3337;
      --code-bg: #090e10;
    }
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      margin: 0;
      padding: 40px 20px;
    }
    .container {
      max-width: 840px;
      margin: 0 auto;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 28px;
      margin-bottom: 24px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }
    h1 {
      color: var(--accent);
      margin-top: 0;
      display: flex;
      align-items: center;
      gap: 14px;
    }
    h2 {
      color: #80ded9;
    }
    pre {
      background: var(--code-bg);
      padding: 16px;
      border-radius: 8px;
      overflow-x: auto;
      border: 1px solid var(--border);
      font-family: "JetBrains Mono", "Fira Code", monospace;
      font-size: 0.95rem;
      color: #80ded9;
    }
    a {
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }
    a:hover {
      text-decoration: underline;
      color: #38b2ac;
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
      background: rgba(0, 168, 150, 0.2);
      color: var(--accent);
      border: 1px solid rgba(0, 168, 150, 0.4);
    }
    .btn-download {
      display: inline-block;
      padding: 10px 18px;
      margin: 6px 8px 6px 0;
      background: var(--accent-grad);
      color: #ffffff !important;
      border-radius: 8px;
      font-weight: 700;
      text-decoration: none !important;
      box-shadow: 0 2px 6px rgba(0, 168, 150, 0.3);
    }
    .btn-download:hover {
      filter: brightness(1.15);
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="card" style="border-left: 4px solid var(--accent);">
      <h1><img src="logo.png" alt="Logo" width="48" height="48" style="border-radius: 8px;"> Debian CachyOS Kernel Updater <span class="badge">APT &amp; Flatpak Repo</span></h1>
      <p>Official Debian APT repository and Flatpak distribution for <strong>CachyOS Kernel Installer &amp; Updater</strong>. Optimized for Debian 12 (Bookworm), Debian 13 (Trixie), Sid, and derivatives.</p>
    </div>

    <div class="card" style="border-left: 4px solid var(--crimson);">
      <h3 style="margin-top: 0; color: var(--crimson);">⚠️ Experimental Tool &amp; Limitation of Liability</h3>
      <p style="margin: 0; font-size: 0.95rem;">This tool is an independent community project provided strictly as an <strong>experimental tool</strong> under the <strong>GNU General Public License v3.0 (GPLv3)</strong>. The authors and contributors assume <strong>no responsibility or liability whatsoever</strong> for any damage, boot failure, data loss, or mis-use. Please ensure you always keep a working stock Debian kernel installed on your system.</p>
    </div>

    <div class="card">
      <h2>🚀 Method 1: Official Debian APT Repository</h2>
      <p>Run the following commands in your terminal to add the repository and install the application with automatic update support:</p>

      <pre><code># 1. Download and install the GPG signing key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://antux912012.github.io/debian-cachy-kernel-updater/KEY.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/cachy-kernel-updater.gpg

# 2. Add the repository to your APT sources
echo "deb [signed-by=/etc/apt/keyrings/cachy-kernel-updater.gpg] https://antux912012.github.io/debian-cachy-kernel-updater stable main" | sudo tee /etc/apt/sources.list.d/cachy-kernel-updater.list

# 3. Update package index and install
sudo apt update
sudo apt install cachy-kernel-updater</code></pre>
    </div>

    <div class="card">
      <h2>📦 Direct Package Downloads (v${VERSION})</h2>
      <p>Direct download links for the latest stable build:</p>
      <p>
        <a class="btn-download" href="pool/main/c/cachy-kernel-updater/cachy-kernel-updater_${VERSION}_all.deb">📦 Download Debian Package (.deb)</a>
        <a class="btn-download" href="cachy-kernel-updater_${VERSION}.flatpak">📦 Download Flatpak Bundle (.flatpak)</a>
      </p>
      <ul>
        <li><a href="KEY.asc">Repository GPG Public Key (ASCII Armored)</a></li>
        <li><a href="KEY.gpg">Repository GPG Public Key (Binary Dearmored)</a></li>
      </ul>
      <p>Source code, issue tracker, and releases available on <a href="https://github.com/Antux912012/debian-cachy-kernel-updater">GitHub: Antux912012/debian-cachy-kernel-updater</a>.</p>
    </div>

    <div class="card">
      <h2>🙏 Acknowledgements &amp; Support CachyOS</h2>
      <p>This project is inspired by and relies on the incredible work of the <strong>CachyOS Team</strong>. We thank them for their continuous innovation in high-performance Linux kernels and schedulers.</p>
      <ul>
        <li>Official Website: <a href="https://cachyos.org" target="_blank" rel="noopener">https://cachyos.org</a></li>
        <li>GitHub: <a href="https://github.com/CachyOS" target="_blank" rel="noopener">https://github.com/CachyOS</a></li>
        <li>💖 Support CachyOS: <a href="https://cachyos.org/donate/" target="_blank" rel="noopener">Donate to CachyOS</a> | <a href="https://www.patreon.com/CachyOS" target="_blank" rel="noopener">Patreon</a></li>
      </ul>
    </div>
  </div>
</body>
</html>
EOF

echo "=== 9. Repository generated successfully at $REPO_DIR ==="
ls -la "$REPO_DIR"

if [ "$1" = "--deploy" ] || [ "$1" = "-d" ]; then
    echo "=== 10. Deploying APT repository to gh-pages branch ==="
    REMOTE_URL="$(git -C "$DIR" config --get remote.origin.url 2>/dev/null || echo "https://github.com/Antux912012/debian-cachy-kernel-updater.git")"
    if [ -n "${GITHUB_TOKEN:-}" ]; then
        REMOTE_URL="https://${GITHUB_TOKEN}@github.com/Antux912012/debian-cachy-kernel-updater.git"
    fi
    DEPLOY_TMP="/tmp/gh-pages-deploy-$$"
    rm -rf "$DEPLOY_TMP"
    git clone --branch gh-pages --single-branch "$REMOTE_URL" "$DEPLOY_TMP" || git clone "$REMOTE_URL" "$DEPLOY_TMP"
    cd "$DEPLOY_TMP"
    git checkout gh-pages 2>/dev/null || git checkout --orphan gh-pages
    git rm -rf . >/dev/null 2>&1 || true
    cp -r "$REPO_DIR"/* .
    git config user.name "Antonio"
    git config user.email "antux912012@users.noreply.github.com"
    git add -A
    git commit -m "Update APT & Flatpak repository to v${VERSION}" || echo "No changes to commit"
    git push "$REMOTE_URL" gh-pages
    rm -rf "$DEPLOY_TMP"
    echo "=== Successfully published to GitHub Pages! ==="
fi

