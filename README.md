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

1. **Official CachyOS Version Checking:** Queries the official [CachyOS GitHub repository](https://github.com/CachyOS/linux/releases) and [PKGBUILD](https://github.com/CachyOS/linux-cachyos) to detect the latest stable CachyOS kernel release.
2. **System Comparison:** Automatically verifies whether your currently running kernel matches the latest CachyOS release.
3. **Automated Source & Config Download:** Downloads the pre-patched official CachyOS kernel tree and the official CachyOS `.config`.
4. **Optimized Compilation (`make bindeb-pkg`):**
   * Configures the kernel with CachyOS scheduler and performance optimizations.
   * Disables Debian trusted keys hurdles and excessive debug symbols to ensure fast, failure-free builds.
   * Compiles the kernel into native `.deb` packages using all available CPU threads.
5. **Polkit Privilege Escalation:** Safely invokes `pkexec` for native password prompts when installing or purging packages and updating GRUB.
6. **Kernel Rollback:** Lists installed `linux-image-*` packages in a safety-first UI dialog, allowing you to purge previous kernels and automatically restore older kernel entries in GRUB.
7. **Modern Native UI:** Built with **GTK4** and **Libadwaita**, providing dark mode support, titlebar controls, and live terminal logging.

---

## Downloads (v1.0.1)

Pre-compiled packages are available on the [Latest Release Page](https://github.com/Antux912012/debian-cachy-kernel-updater/releases/tag/v1.0.1):

* 📦 **[Download Debian Package (.deb)](https://github.com/Antux912012/debian-cachy-kernel-updater/releases/download/v1.0.1/cachy-kernel-updater_1.0.1_all.deb)** — Recommended for Debian systems (auto-resolves dependencies via `apt`)
* 🚀 **[Download Standalone AppImage](https://github.com/Antux912012/debian-cachy-kernel-updater/releases/download/v1.0.1/Cachy-Kernel-Updater-1.0.1-x86_64.AppImage)** — Pre-bundled standalone executable (all GTK4/Adwaita libraries and logo icons included)
* 🔧 **[Download libfuse2t64 (.deb)](https://github.com/Antux912012/debian-cachy-kernel-updater/releases/download/v1.0.1/libfuse2t64_2.9.9-9_amd64.deb)** — Crucial compatibility package for running AppImages on **Debian Testing (Trixie)** & **Debian Sid**

---

### Package Formats & System Libraries

Depending on how you run the application, the required libraries vary:

#### 1. Running the AppImage (All Libraries Included)
> [!NOTE]
> **No external GUI or Python libraries are required.** All runtime dependencies—including **Python 3**, **GTK4**, **Libadwaita**, **PyGObject**, **Requests**, and the **CachyOS/Debian Icon Theme**—are fully bundled inside the `.AppImage` executable.

##### FUSE Requirement on Debian:
To run any AppImage on Debian, FUSE2 runtime support is required:
* **On Debian Stable (Bookworm):**
  ```bash
  sudo apt install -y libfuse2
  ```
* **On Debian Testing (Trixie) & Sid (Unstable):**
  Due to the 64-bit `time_t` transition in Debian Testing/Sid, `libfuse2` has transitioned to `libfuse2t64`. You can install it via:
  ```bash
  sudo apt install -y libfuse2t64
  ```
  Or install the provided compatibility package:
  ```bash
  sudo dpkg -i libfuse2t64_2.9.9-9_amd64.deb
  ```

Then execute the AppImage:
```bash
chmod +x Cachy-Kernel-Updater-1.0.1-x86_64.AppImage
./Cachy-Kernel-Updater-1.0.1-x86_64.AppImage
```

---

#### 2. Running the Native Debian Package (`.deb`)
The `.deb` package defines all runtime dependencies in its control file. When installed via `apt`, all required libraries are resolved and installed automatically:

```bash
sudo apt install -y ./deb_dist/cachy-kernel-updater_1.0.1_all.deb
```

---

#### 3. Flatpak Support (Work in Progress 🚧)
> [!IMPORTANT]
> **We are currently working on an official Flatpak version as well.** The Flatpak package is in active development to provide an easy one-click install for users on Flatpak-centric setups and Flathub.

---

#### 4. Running Directly from Source (Python)
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

## Building from Source

### Build the Native Debian Package (`.deb`)
```bash
./build_deb.sh
```
This generates the ready-to-install package at `deb_dist/cachy-kernel-updater_1.0.0_all.deb`.

### Build the AppImage
```bash
./build_appimage.sh
```
This generates `Cachy-Kernel-Updater-1.0.0-x86_64.AppImage`.

---

## Project Structure

```
├── assets/              # Screenshots and visual media
│   └── Debian-Cachy-OS.jpeg
├── main.py              # GTK4 / Libadwaita User Interface
├── kernel_manager.py    # Backend engine: version checking, compilation, install & rollback
├── build_deb.sh         # Debian package (.deb) generator script
├── build_appimage.sh    # AppImage packaging script
├── AppImageBuilder.yml  # AppImage recipe configuration
├── requirements.txt     # Python requirements
├── LICENSE              # GNU General Public License v3.0
└── README.md            # Documentation & requirements
```

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
