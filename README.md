# Debian CachyOS Kernel Installer & Updater

A modern **GTK4 / Libadwaita** application designed for Debian systems to check, download, compile, install, and rollback performance-optimized **CachyOS Linux Kernels**.

![Debian](https://img.shields.io/badge/Debian-Bookworm%20%2B-A81D33?logo=debian&logoColor=white)
![GTK4](https://img.shields.io/badge/GUI-GTK4%20%2F%20Libadwaita-3584e4?logo=gnome&logoColor=white)
![Python](https://img.shields.io/badge/Language-Python%203-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-GPLv3-blue.svg)

---

## Features

1. **Official CachyOS Version Checking:** Queries the official [CachyOS GitHub repository](https://github.com/CachyOS/linux/releases) and [PKGBUILD](https://github.com/CachyOS/linux-cachyos) to detect the latest stable CachyOS kernel release.
2. **System Comparison:** Automatically verifies whether your currently running kernel matches the latest CachyOS release.
3. **Automated Source & Config Download:** Downloads the pre-patched official CachyOS kernel tree and the official CachyOS `.config`.
4. **Optimized Compilation (`make bindeb-pkg`):**
   * Configures the kernel with CachyOS scheduler and performance optimizations.
   * Disables Debian trusted keys hurdles and excessive debug symbols to ensure fast, failure-free builds.
   * Compiles the kernel into native `.deb` packages using all available CPU threads.
5. **Polkit Privilege Escalation:** Safely invokes `pkexec` for password prompts when installing or purging packages and updating GRUB.
6. **Kernel Rollback:** Lists installed `linux-image-*` packages in a safety-first UI dialog, allowing you to purge previous kernels and automatically restore older kernel entries in GRUB.
7. **Modern Native UI:** Built with **GTK4** and **Libadwaita**, providing dark mode support, titlebar controls, and live terminal logging.

---

## Installation

### Option 1: Native Debian Package (`.deb`) [Recommended]

Build the `.deb` package using the included build script:
```bash
./build_deb.sh
sudo apt install ./deb_dist/cachy-kernel-updater_1.0.0_all.deb
```
Once installed, you can launch the app from your application menu or by running:
```bash
cachy-kernel-updater
```

### Option 2: AppImage

To build an AppImage bundle:
```bash
./build_appimage.sh
./Cachy-Kernel-Updater-1.0.0-x86_64.AppImage
```

### Option 3: Run directly from source

Make sure the required runtime dependencies are installed:
```bash
sudo apt install -y python3 python3-gi python3-gi-cairo python3-requests \
    gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0
```
Run the application:
```bash
python3 main.py
```

---

## Kernel Build Dependencies

When compiling a custom Linux kernel on Debian, make sure the following build dependencies are installed on your machine:
```bash
sudo apt install -y build-essential libncurses-dev bison flex libssl-dev \
    libelf-dev bc rsync debhelper pahole
```

---

## Project Structure

```
├── main.py              # GTK4 / Libadwaita User Interface
├── kernel_manager.py    # Backend engine: version checking, compilation, install & rollback
├── build_deb.sh         # Debian package (.deb) generator script
├── build_appimage.sh    # AppImage packaging script
├── AppImageBuilder.yml  # AppImage recipe configuration
├── requirements.txt     # Python requirements
└── README.md
```

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
