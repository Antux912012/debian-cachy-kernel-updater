# Debian CachyOS Kernel Installer & Updater

A modern **GTK4 / Libadwaita** application designed for Debian systems to check, download, compile, install, and rollback performance-optimized **CachyOS Linux Kernels**.

![Debian](https://img.shields.io/badge/Debian-Bookworm%20%2B-A81D33?logo=debian&logoColor=white)
![GTK4](https://img.shields.io/badge/GUI-GTK4%20%2F%20Libadwaita-3584e4?logo=gnome&logoColor=white)
![Python](https://img.shields.io/badge/Language-Python%203-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-GPLv3-blue.svg)

<p align="center">
  <img src="assets/Debian-Cachy-OS.jpeg" alt="Debian CachyOS Kernel Updater" width="750">
</p>

---

## Features

1. **Official CachyOS Version Checking:** Queries the official [CachyOS GitHub repository](https://github.com/CachyOS/linux/releases) and [PKGBUILD](https://github.com/CachyOS/linux-cachyos) to detect the latest stable CachyOS kernel release (e.g. 7.2.9).
2. **System Comparison:** Automatically verifies whether your currently running kernel matches the latest CachyOS release.
3. **Automated Source & Config Download:** Downloads the pre-patched official CachyOS kernel tree and the official CachyOS `.config`.
4. **Containerized Compilation (Podman / Docker):**
   * Optionally compile inside an isolated `debian:bookworm-slim` container environment using **Podman** or **Docker**.
   * Provides 100% reproducible builds and generic compatibility across Debian Bookworm, Trixie, Sid, and derivatives without polluting your host system.
5. **Organized Output in `~/kernel-build-deb/`:**
   * Prompts the user to grant permission to create the output folder in their home directory.
   * Collects all generated `.deb` packages (`linux-image`, `linux-headers`), `kernel.config`, and a self-contained `install.sh` helper into `/home/$USER/kernel-build-deb/Linux-kernel-CachyOS-(version)-debian/`.
6. **Optimized Compilation (`make bindeb-pkg`):**
   * Configures the kernel with CachyOS scheduler and performance optimizations.
   * Disables Debian trusted keys hurdles and excessive debug symbols to ensure fast, failure-free builds.
   * Compiles the kernel into native `.deb` packages using all available CPU threads.
7. **Polkit Privilege Escalation:** Safely invokes `pkexec` for native password prompts when installing or purging packages and updating GRUB.
8. **Kernel Rollback:** Lists installed `linux-image-*` packages in a safety-first UI dialog, allowing you to purge previous kernels and automatically restore older kernel entries in GRUB.
9. **Cache Cleanup & Persistent Config Recovery:** Checks and cleans `~/.cache/cachy-kernel-build` every time the app opens, preventing disk bloat while automatically saving and recovering your generated kernel `.config` across kernel updates.
10. **One-Click Build Dependencies Installer:** Built-in "Install Dependencies" button to verify and install all required kernel compiler tools directly from the GUI.
11. **Modern Native UI:** Built with **GTK4** and **Libadwaita**, providing dark mode support, titlebar controls, and live terminal logging.

---

## Installation

### Method 1: Official Debian APT Repository (Recommended)

Installing via our official APT repository enables automatic updates alongside your system packages (`sudo apt upgrade`):

```bash
# 1. Download and install the repository GPG signing key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://antux912012.github.io/debian-cachy-kernel-updater/KEY.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/cachy-kernel-updater.gpg

# 2. Add the repository to your APT sources
echo "deb [signed-by=/etc/apt/keyrings/cachy-kernel-updater.gpg] https://antux912012.github.io/debian-cachy-kernel-updater stable main" | sudo tee /etc/apt/sources.list.d/cachy-kernel-updater.list

# 3. Update package index and install
sudo apt update
sudo apt install cachy-kernel-updater
```

> [!TIP]
> Compatible with **Debian 12 (Bookworm)**, **Debian 13 (Trixie)**, **Debian Sid (Unstable)**, and Debian-based distributions. You can also visit the [APT Repository Web Page](https://antux912012.github.io/debian-cachy-kernel-updater/).

---

### Method 2: Direct `.deb` Package Download

Download the pre-compiled `.deb` package from the [v1.0.5 Release Page](https://github.com/Antux912012/debian-cachy-kernel-updater/releases/tag/v1.0.5):

* 📦 **[cachy-kernel-updater_1.0.5_all.deb](https://github.com/Antux912012/debian-cachy-kernel-updater/releases/download/v1.0.5/cachy-kernel-updater_1.0.5_all.deb)**

Install it using `apt` (which automatically installs any missing dependencies):
```bash
sudo apt install -y ./cachy-kernel-updater_1.0.5_all.deb
```

---

### Method 3: Running Directly from Source (Python)
If running from source code (`python3 main.py`), you must ensure the following Debian packages and GTK4 libraries are installed:

| Library Package | Purpose |
| :--- | :--- |
| `python3` | Python runtime |
| `python3-gi` | Python GObject introspection bindings |
| `python3-gi-cairo` | Cairo vector graphics bindings for Python |
| `python3-requests` | HTTP library for querying the official CachyOS GitHub API |
| `gir1.2-gtk-4.0` | GTK 4.0 graphical toolkit |
| `gir1.2-adw-1` | Libadwaita 1.0 widget library (GNOME modern styling) |
| `libadwaita-1-0` | Libadwaita shared C libraries |
| `policykit-1` or `polkitd` | Provides `pkexec` for secure root privilege prompts |

Install all of them with a single command:
```bash
sudo apt update
sudo apt install -y python3 python3-gi python3-gi-cairo python3-requests \
    gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0 policykit-1
```

---

### 4. Kernel Compilation Dependencies
To compile the CachyOS kernel (`make bindeb-pkg`), your system requires standard Linux kernel compilation build tools:

```bash
sudo apt install -y build-essential libncurses-dev bison flex libssl-dev \
    libelf-dev bc rsync debhelper pahole
```

---

## 🔐 Secure Boot & Kernel Signing

> [!WARNING]
> **Crucial for Systems with Secure Boot Enabled:**
> Custom compiled Linux kernels are not signed by Debian's official Microsoft-trusted EFI key. If your computer has **UEFI Secure Boot enabled**, your motherboard firmware will refuse to boot the newly compiled CachyOS kernel unless it is signed with a **Machine Owner Key (MOK)**.

### Signing the Kernel with `sign-kernel.sh`

We provide an automated helper script [`sign-kernel.sh`](sign-kernel.sh) to sign the installed kernel image in `/boot`:

```bash
chmod +x sign-kernel.sh
sudo ./sign-kernel.sh
```

#### What `sign-kernel.sh` does:
1. **Finds or Generates MOK Keys:** Automatically checks for existing `MOK.priv` and `MOK.pem` keys. If you don't have them yet, it generates a new 2048-bit RSA MOK keypair (`MOK.priv`, `MOK.pem`, and `MOK.der`) in the script directory.
2. **First-time MOK Enrollment:** If keys were just generated, enroll the public key into your UEFI firmware by running:
   ```bash
   sudo mokutil --import MOK.der
   ```
   Set a simple temporary password. Upon reboot, the blue **MOKManager** screen will appear: select **Enroll MOK** -> **Continue** -> enter the password to enroll the key permanently.
3. **Installs `sbsigntool`:** Automatically installs `sbsigntool` via `apt` if not already installed.
4. **Signs the Kernel:** Automatically identifies your newly installed CachyOS kernel in `/boot/` and signs it using `sbsign`.

> [!TIP]
> **Upcoming In-App Signing:** We are actively working on integrating this Secure Boot signing process directly into the GTK4 application itself, so that signing is automatically offered upon completing kernel installation!

---

## Building from Source

### Build the Native Debian Package (`.deb`)
```bash
./build_deb.sh
```
This generates the ready-to-install package at `deb_dist/cachy-kernel-updater_1.0.5_all.deb`.

### Build the AppImage
```bash
./build_appimage.sh
```
This generates `Cachy-Kernel-Updater-1.0.3-x86_64.AppImage`.

---

## Project Structure

```
├── assets/              # Screenshots and visual media
│   └── Debian-Cachy-OS.jpeg
├── main.py              # GTK4 / Libadwaita User Interface
├── kernel_manager.py    # Backend engine: version checking, compilation, install & rollback
├── build_deb.sh         # Debian package (.deb) generator script
├── build_appimage.sh    # AppImage packaging script
├── sign-kernel.sh       # Secure Boot MOK signing script
├── AppImageBuilder.yml  # AppImage recipe configuration
├── requirements.txt     # Python requirements
├── LICENSE              # GNU General Public License v3.0
└── README.md            # Documentation & requirements
```

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
