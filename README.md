# Debian CachyOS Kernel Installer & Updater

A modern **GTK4 / Libadwaita** application designed for Debian systems to check, download, compile, install, and rollback performance-optimized **CachyOS Linux Kernels**.

![Debian](https://img.shields.io/badge/Debian-Bookworm%20%2B-A81D33?logo=debian&logoColor=white)
![GTK4](https://img.shields.io/badge/GUI-GTK4%20%2F%20Libadwaita-3584e4?logo=gnome&logoColor=white)
![Python](https://img.shields.io/badge/Language-Python%203-3776AB?logo=python&logoColor=white)
![Version](https://img.shields.io/badge/version-1.0.7-blue.svg)
![License](https://img.shields.io/badge/License-GPLv3-blue.svg)

<p align="center">
  <img src="assets/Debian-Cachy-OS.jpeg" alt="Debian CachyOS Kernel Updater" width="750">
</p>

> [!WARNING]
> **Disclaimer — Experimental Software:**
> This tool is an independent community project and is currently **experimental**. Compiling, installing, or modifying system kernels carries inherent risks. While safety checks and rollback options are built in, you should **always maintain a fallback stock Debian kernel** on your system. Use at your own risk.

---

## Features

1. **Official CachyOS Version Checking:** Queries the official [CachyOS GitHub repository](https://github.com/CachyOS/linux/releases) and [PKGBUILD](https://github.com/CachyOS/linux-cachyos) to detect the latest stable CachyOS kernel release (e.g. 7.2.10).
2. **System Comparison:** Automatically verifies whether your currently running kernel matches the latest CachyOS release.
3. **Automated Source & Config Download:** Downloads the pre-patched official CachyOS kernel tree and the official CachyOS `.config`.
4. **Containerized Compilation (Podman / Docker):**
   * Optionally compile inside an isolated `debian:bookworm-slim` container environment using **Podman** or **Docker**.
   * Provides 100% reproducible builds and generic compatibility across Debian Bookworm, Trixie, Sid, and derivatives without polluting your host system.
5. **⚡ Compile for My System (Experimental):**
   * **Hardware Auto-Detection:** Automatically scans your machine's CPU vendor (Intel/AMD), CPU model, thread count, form-factor (laptop battery vs desktop), root filesystem, and active hardware modules.
   * **Native CPU Optimization (`-march=native`):** Directs the compiler to utilize your exact CPU microarchitecture instructions (AVX2, AVX-512, BMI2, modern cache line sizes) for maximum responsiveness.
   * **Hardware-Tailored Drivers (`make localmodconfig`):** Scans active hardware modules and trims thousands of unused drivers for hardware not present on your system, reducing compile times from 45–90 minutes down to ~10–20 minutes!
   * **Baseline Safeguards:** Enforces essential storage controllers (NVMe, SATA), filesystems (ext4, btrfs, vfat, ntfs3), and USB input/storage classes so your system always boots reliably.
6. **🔐 In-App UEFI Secure Boot (MOK) Signing & Enrollment Wizard:**
   * **Automatic Post-Build Signing:** Automatically unpacks built `.deb` packages, signs `/boot/vmlinuz-*` with `sbsign`, verifies signature integrity with `sbverify`, and repacks `.deb` packages in-place.
   * **In-App MOK Enrollment:** Prompts for a one-time enrollment password directly inside the GUI and stages the key into NVRAM via `pkexec mokutil --import` for approval on next reboot.
   * **Standalone Signing Tools:** Sign existing packages on demand, enroll MOK keys, or sign `/boot/vmlinuz-*` directly.
7. **Organized Output in `~/kernel-build-deb/`:**
   * Prompts the user to grant permission to create the output folder in their home directory.
   * Collects all generated `.deb` packages (`linux-image`, `linux-headers`), `kernel.config`, and a self-contained `install.sh` helper into `/home/$USER/kernel-build-deb/Linux-kernel-CachyOS-(version)-debian/` (or `-native-debian/`).
8. **Optimized Compilation (`make bindeb-pkg`):**
   * Configures the kernel with CachyOS scheduler and performance optimizations.
   * Sanitizes Debian certificate traps (`SYSTEM_TRUSTED_KEYS=""`, `SYSTEM_REVOCATION_KEYS=""`) and module keys to ensure failure-free builds on both host and containers.
   * Compiles the kernel into native `.deb` packages using all available CPU threads.
9. **Polkit Privilege Escalation:** Safely invokes `pkexec` for native password prompts when installing or purging packages, importing MOK keys, and updating GRUB.
10. **Kernel Rollback:** Lists installed `linux-image-*` packages in a safety-first UI dialog, allowing you to purge previous kernels and automatically restore older kernel entries in GRUB.
11. **Cache Cleanup & Persistent Config Recovery:** Checks and cleans `~/.cache/cachy-kernel-build` every time the app opens, preventing disk bloat while automatically saving and recovering your generated kernel `.config` across kernel updates.
12. **One-Click Build Dependencies Installer:** Built-in "Install Dependencies" button to verify and install all required kernel compiler tools directly from the GUI.
13. **Modern Native UI:** Built with **GTK4** and **Libadwaita**, providing dark mode support, titlebar controls, and live terminal logging.

---

## ⚡ Experimental Feature: "Compile for My System"

The **"Compile for my system"** switch enables automated hardware auto-detection to build an optimized, machine-tailored CachyOS kernel rather than a generic one-size-fits-all build:

### What It Does:
* **Silicon-Level Optimization (`-march=native`):** Configures the kernel with `CONFIG_X86_NATIVE_CPU=y` (and CachyOS native compiler flags), instructing GCC to utilize all instruction sets supported by your exact processor (e.g. AVX2, AVX-512, BMI2, AES-NI, FMA, and modern cache-line tuning).
* **Hardware-Tailored Driver Stripping (`make localmodconfig`):** Generic distribution kernels compile over 5,000 drivers for thousands of ancient or obscure controllers. The app snapshots your running hardware via `lsmod` and trims away drivers for hardware not physically present on your machine.
* **Dramatically Faster Builds:** Cuts compilation time from **45–90 minutes down to ~10–20 minutes** on typical multi-core CPUs, while also reducing kernel image and initramfs size.
* **Form-Factor & Power Management:** Detects whether you are running on a laptop (battery detected) or desktop, configuring optimal CPU frequency governors (`AMD P-State EPP` / `Intel P-State`), timer tick behavior, and vendor-specific ACPI modules (e.g., ThinkPad, Dell, ASUS).
* **Baseline Safeguards:** Enforces core storage drivers (NVMe, AHCI/SATA), vital filesystems (`ext4`, `btrfs`, `vfat`, `ntfs3`), and USB HID input devices so your system boots reliably and external drives continue to work.
* **Isolated Output:** System-tailored builds are labeled with the `-cachyos-native-debian` localversion and organized into `~/kernel-build-deb/Linux-kernel-CachyOS-(version)-native-debian/`.

> [!IMPORTANT]
> **Portability Notice:**
> A kernel compiled with "Compile for my system" is tailored specifically for the machine on which it was built. The resulting `.deb` packages should not be installed on another PC with different hardware or a different CPU generation.

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

Download the pre-compiled `.deb` package from the [v1.0.7 Release Page](https://github.com/Antux912012/debian-cachy-kernel-updater/releases/tag/v1.0.7):

* 📦 **[cachy-kernel-updater_1.0.7_all.deb](https://github.com/Antux912012/debian-cachy-kernel-updater/releases/download/v1.0.7/cachy-kernel-updater_1.0.7_all.deb)**

Install it using `apt` (which automatically installs any missing dependencies):
```bash
sudo apt install -y ./cachy-kernel-updater_1.0.7_all.deb
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
    libelf-dev bc rsync debhelper pahole dwarves sbsigntool mokutil openssl
```

> [!NOTE]
> **Compilation Duration Notice:**
> Compiling a full Linux kernel is an intensive task that utilizes all available CPU threads. The compilation process can take a while (typically anywhere from 15 to 45+ minutes) depending on the processing power, CPU core count, and cooling capabilities of your system.

---

## 🔐 Secure Boot & Kernel Signing

> [!WARNING]
> **Crucial for Systems with Secure Boot Enabled:**
> Custom compiled Linux kernels are not signed by Debian's official Microsoft-trusted EFI key. If your computer has **UEFI Secure Boot enabled**, your motherboard firmware will refuse to boot the newly compiled CachyOS kernel unless it is signed with a **Machine Owner Key (MOK)**.

### Option A: In-App MOK Signing & Enrollment (Automatic)
The application now features built-in **Post-Build Secure Boot (MOK) Signing**:
1. When **Auto-sign built kernel packages (UEFI MOK)** is toggled on (enabled by default when Secure Boot is detected), the application automatically unpacks your newly compiled `linux-image-*.deb` packages, signs `/boot/vmlinuz-*` using your local MOK key via `sbsign`, verifies the signature with `sbverify`, and repacks the `.deb` archive in-place.
2. If your MOK key has not yet been enrolled into your system's NVRAM, the app opens a dialog prompting for a one-time temporary enrollment password and stages the key via `pkexec mokutil --import`.
3. Upon reboot, the blue **MokManager** screen appears:
   - Select **Enroll MOK** -> **Continue** -> **Yes**.
   - Enter your chosen temporary password.
   - Select **Reboot** to boot into your newly signed kernel!

### Option B: CLI Signing with `sign-kernel.sh`
For headless systems or command-line workflows, use [`sign-kernel.sh`](sign-kernel.sh):
```bash
# Sign built .deb packages with MOK:
./sign-kernel.sh --sign-deb-mok ~/kernel-build-deb/Linux-kernel-CachyOS-.../

# Or sign installed kernel in /boot and update initramfs:
sudo ./sign-kernel.sh --secureboot
```

---

## Building from Source

### Build the Native Debian Package (`.deb`)
```bash
./build_deb.sh
```
This generates the ready-to-install package at `deb_dist/cachy-kernel-updater_1.0.7_all.deb`.

### Build the AppImage
```bash
./build_appimage.sh
```
This generates `CachyOS_Kernel_Updater-1.0.7-x86_64.AppImage`.

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

## 🙏 Acknowledgements & Support CachyOS

This project would not be possible without the remarkable, groundbreaking work of the **[CachyOS Team](https://cachyos.org/)**. 

We express our sincerest gratitude to the CachyOS developers for their continuous innovation in the Linux ecosystem, including their performance-optimized kernel patches, advanced CPU schedulers (BORE, EEVDF, etc.), and fine-tuned configurations that make high-performance desktop responsiveness and gaming accessible to everyone.

* 🌐 **Official Website:** [https://cachyos.org](https://cachyos.org)
* 🐙 **Official GitHub:** [https://github.com/CachyOS](https://github.com/CachyOS)
* 🐧 **CachyOS Kernel Source:** [https://github.com/CachyOS/linux](https://github.com/CachyOS/linux)
* 💖 **Support & Donate to CachyOS:** If you enjoy the performance benefits of CachyOS kernels, please consider supporting their project directly through the **[CachyOS Donation Page](https://cachyos.org/donate/)** or their **[Patreon](https://www.patreon.com/CachyOS)**.

*(Note: This updater is an independent, community-driven tool for Debian and is not officially affiliated with or maintained by the CachyOS core team).*

---

## 📜 Changelog

### v1.0.7
- **Resolved `bindeb-pkg` Error 2**: Sanitized Debian/Canonical `.pem` certificate traps (`SYSTEM_TRUSTED_KEYS=""`, `SYSTEM_REVOCATION_KEYS=""`, `MODULE_SIG_KEY=""`) and decoupled module signing from the compilation phase, enabling robust failure-free kernel builds natively and inside Podman/Docker containers.
- **Added Full Kernel 7.x & Packaging Dependencies**: Added `pahole`, `dwarves`, `sbsigntool`, `mokutil`, `openssl`, `fakeroot`, and `dpkg-dev` to `Containerfile`, `build_deb.sh`, and `kernel_manager.py`.
- **In-App Post-Build UEFI Secure Boot (MOK) Signing**: Automatically unpacks `linux-image-*.deb` packages post-compilation, signs internal `/boot/vmlinuz-*` binaries with `sbsign`, verifies cryptographic signatures via `sbverify`, and repacks `.deb` packages in-place.
- **In-App MOK Key Enrollment Wizard**: Integrated interactive dialog to stage MOK certificate enrollment into UEFI NVRAM (`pkexec mokutil --import`) with password validation and step-by-step reboot guidance for MokManager.
- **Standalone Security Signing Tools**: Added UI rows and CLI arguments (`--sign-deb-mok`, `--status-sb`, `--enroll-mok`) for on-demand package signing and MOK management.

### v1.0.6
- Added experimental "Compile for my system" hardware-tailored kernel build with CPU detection and `make localmodconfig`.

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

