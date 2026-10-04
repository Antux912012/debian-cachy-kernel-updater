#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
cd "$DIR"

KEY_ID="620D1EA9AC45150575E70825BEE28F80428556CF"
REPO_URL="https://antux912012.github.io/debian-cachy-kernel-updater"
REPO_DIR="/tmp/cachyos-apt-repo-staging"

echo "=== 1. Preparing staging directory for APT repository ==="
rm -rf "$REPO_DIR"
mkdir -p "$REPO_DIR/pool/main/c/cachy-kernel-updater"
mkdir -p "$REPO_DIR/dists/stable/main/binary-all"
mkdir -p "$REPO_DIR/dists/stable/main/binary-amd64"

echo "=== 2. Copying .deb packages ==="
if [ ! -f "deb_dist/cachy-kernel-updater_1.0.5_all.deb" ]; then
    echo "deb_dist package not found, building..."
    ./build_deb.sh
fi

cp -v deb_dist/cachy-kernel-updater_*.deb "$REPO_DIR/pool/main/c/cachy-kernel-updater/"

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
      --bg: #0f111a;
      --card-bg: #1a1c29;
      --text: #e6e6e6;
      --accent: #00d2ff;
      --border: #2d3148;
      --code-bg: #12131c;
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
      max-width: 820px;
      margin: 0 auto;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 28px;
      margin-bottom: 24px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    h1 {
      color: var(--accent);
      margin-top: 0;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    pre {
      background: var(--code-bg);
      padding: 16px;
      border-radius: 8px;
      overflow-x: auto;
      border: 1px solid var(--border);
      font-family: "JetBrains Mono", "Fira Code", monospace;
      font-size: 0.95rem;
      color: #79ffe1;
    }
    a {
      color: var(--accent);
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
      background: #00d2ff22;
      color: var(--accent);
      border: 1px solid #00d2ff44;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h1>🐧 Debian CachyOS Kernel Updater <span class="badge">APT Repository</span></h1>
      <p>Official Debian APT repository for <strong>CachyOS Kernel Installer & Updater</strong>. Supports Debian 12 (Bookworm), Debian 13 (Trixie), Sid, and Debian-based distributions.</p>
    </div>

    <div class="card" style="border-left: 4px solid #f39c12;">
      <h3 style="margin-top: 0; color: #f39c12;">⚠️ Experimental Software Notice</h3>
      <p style="margin: 0; font-size: 0.95rem;">This tool is an independent community project and is currently <strong>experimental</strong>. Please ensure you always have a fallback stock Debian kernel installed on your system before updating.</p>
    </div>

    <div class="card">
      <h2>🚀 Quick Installation</h2>
      <p>Run the following commands in your terminal to add the repository and install the application:</p>

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
      <h2>📦 Direct Package Downloads</h2>
      <ul>
        <li><a href="pool/main/c/cachy-kernel-updater/cachy-kernel-updater_1.0.5_all.deb">cachy-kernel-updater_1.0.5_all.deb</a> (Latest)</li>
        <li><a href="KEY.asc">Repository GPG Public Key (ASCII Armored)</a></li>
        <li><a href="KEY.gpg">Repository GPG Public Key (Binary Dearmored)</a></li>
      </ul>
      <p>Source code and issue tracker available at <a href="https://github.com/Antux912012/debian-cachy-kernel-updater">GitHub: Antux912012/debian-cachy-kernel-updater</a>.</p>
    </div>

    <div class="card">
      <h2>🙏 Acknowledgements & Support CachyOS</h2>
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
    REMOTE_URL="$(git config --get remote.origin.url)"
    DEPLOY_TMP="/tmp/gh-pages-deploy-$$"
    rm -rf "$DEPLOY_TMP"
    git clone "$REMOTE_URL" "$DEPLOY_TMP"
    cd "$DEPLOY_TMP"
    git checkout gh-pages 2>/dev/null || git checkout --orphan gh-pages
    git rm -rf . >/dev/null 2>&1 || true
    cp -r "$REPO_DIR"/* .
    git config user.name "Antonio"
    git config user.email "antux912012@users.noreply.github.com"
    git add -A
    git commit -m "Update APT repository" || echo "No changes to commit"
    git push origin gh-pages
    rm -rf "$DEPLOY_TMP"
    echo "=== Successfully published to GitHub Pages! ==="
fi

