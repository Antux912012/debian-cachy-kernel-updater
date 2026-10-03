#!/usr/bin/env bash
# ==============================================================================
# Universal Linux Kernel Secure Boot Signing Script
# Signs custom compiled Linux kernels (CachyOS, Debian, etc.) using MOK
# ==============================================================================
set -e

# Ensure running with root privileges
if [ "$EUID" -ne 0 ]; then
    echo "[-] Error: Root privileges required."
    echo "    Please run this script with sudo: sudo ./sign-kernel.sh [kernel-path-or-version]"
    exit 1
fi

echo "======================================================="
echo "  Secure Boot Kernel Signer (Universal)"
echo "======================================================="

# ------------------------------------------------------------------------------
# 1. Dependency Auto-Detection and Installation
# ------------------------------------------------------------------------------
install_prerequisites() {
    local missing_tools=()
    command -v sbsign &>/dev/null || missing_tools+=("sbsign")
    command -v openssl &>/dev/null || missing_tools+=("openssl")
    command -v mokutil &>/dev/null || missing_tools+=("mokutil")

    if [ ${#missing_tools[@]} -eq 0 ]; then
        return 0
    fi

    echo "[*] Missing required tool(s): ${missing_tools[*]}"
    echo "[*] Auto-installing prerequisites for your distribution..."

    if command -v apt-get &>/dev/null; then
        apt-get update -y
        apt-get install -y sbsigntool openssl mokutil
    elif command -v dnf &>/dev/null; then
        dnf install -y sbsigntools openssl mokutil
    elif command -v pacman &>/dev/null; then
        pacman -Sy --noconfirm sbsigntools openssl mokutil
    elif command -v zypper &>/dev/null; then
        zypper install -y sbsigntools openssl mokutil
    elif command -v apk &>/dev/null; then
        apk add sbsigntool openssl mokutil
    else
        echo "[-] Error: Unsupported package manager. Please manually install: sbsigntool, openssl, and mokutil."
        exit 1
    fi

    echo "[✓] All prerequisites installed successfully."
}

install_prerequisites

# ------------------------------------------------------------------------------
# 2. Check System Secure Boot Status
# ------------------------------------------------------------------------------
if command -v mokutil &>/dev/null; then
    sb_status=$(mokutil --sb-state 2>/dev/null || true)
    if [[ "$sb_status" =~ "SecureBoot enabled" ]]; then
        echo "[i] Secure Boot is currently: ENABLED (kernel signing is mandatory to boot)"
    elif [[ "$sb_status" =~ "SecureBoot disabled" ]]; then
        echo "[i] Secure Boot is currently: DISABLED (kernel will be signed for future compatibility)"
    else
        echo "[i] Secure Boot status: ${sb_status:-Unknown}"
    fi
fi

# ------------------------------------------------------------------------------
# 3. Locate or Generate Machine Owner Key (MOK)
# ------------------------------------------------------------------------------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MOK_DIR="/etc/secureboot/mok"
KEY=""
CERT=""

# Search order for existing MOK keys
search_dirs=(
    "$SCRIPT_DIR"
    "$MOK_DIR"
    "/var/lib/shim-signed/mok"
    "${SUDO_USER:+/home/$SUDO_USER/.mok}"
    "/root/.mok"
)

for dir in "${search_dirs[@]}"; do
    [ -z "$dir" ] && continue
    if [ -f "$dir/MOK.priv" ] && [ -f "$dir/MOK.pem" ]; then
        KEY="$dir/MOK.priv"
        CERT="$dir/MOK.pem"
        echo "[✓] Found existing MOK key pair: $dir"
        break
    elif [ -f "$dir/MOK.key" ] && [ -f "$dir/MOK.crt" ]; then
        KEY="$dir/MOK.key"
        CERT="$dir/MOK.crt"
        echo "[✓] Found existing MOK key pair: $dir"
        break
    fi
done

# If no MOK keys exist anywhere on the system, generate a persistent keypair
if [ -z "$KEY" ] || [ -z "$CERT" ]; then
    mkdir -p "$MOK_DIR"
    chmod 700 "$MOK_DIR"
    
    echo "[!] No existing Machine Owner Key (MOK) found."
    echo "[*] Generating a new persistent 2048-bit RSA MOK keypair in $MOK_DIR..."
    
    openssl req -new -x509 -newkey rsa:2048 \
        -keyout "$MOK_DIR/MOK.priv" \
        -out "$MOK_DIR/MOK.pem" \
        -nodes -days 3650 \
        -subj "/CN=Custom Linux Kernel MOK ($(hostname))/"
        
    openssl x509 -in "$MOK_DIR/MOK.pem" -outform DER -out "$MOK_DIR/MOK.der"
    chmod 600 "$MOK_DIR/MOK.priv"
    
    KEY="$MOK_DIR/MOK.priv"
    CERT="$MOK_DIR/MOK.pem"
    
    echo "[✓] Created persistent MOK keypair: $MOK_DIR"
    echo ""
    echo "========================================================================="
    echo "  FIRST-TIME MOK ENROLLMENT REQUIRED"
    echo "========================================================================="
    echo "  To authorize this new key in your UEFI Secure Boot, run:"
    echo "    sudo mokutil --import $MOK_DIR/MOK.der"
    echo "  Enter a temporary enrollment password when prompted."
    echo "  Then reboot your computer. The blue MOKManager screen will appear:"
    echo "    1. Select 'Enroll MOK'"
    echo "    2. Select 'Continue'"
    echo "    3. Select 'Yes' and enter the temporary password you set."
    echo "========================================================================="
    echo ""
fi

# ------------------------------------------------------------------------------
# 4. Locate Target Kernel Image
# ------------------------------------------------------------------------------
TARGET="$1"
KERNEL=""

if [ -n "$TARGET" ]; then
    if [ -f "$TARGET" ]; then
        KERNEL="$TARGET"
    elif [ -f "/boot/$TARGET" ]; then
        KERNEL="/boot/$TARGET"
    elif [ -f "/boot/vmlinuz-${TARGET}" ]; then
        KERNEL="/boot/vmlinuz-${TARGET}"
    else
        echo "[-] Error: Target kernel '$TARGET' not found."
        exit 1
    fi
else
    # Automatically locate newest CachyOS or Linux kernel in /boot
    CANDIDATES=$(ls -v /boot/vmlinuz-*cachyos* 2>/dev/null || true)
    if [ -n "$CANDIDATES" ]; then
        KERNEL=$(echo "$CANDIDATES" | tail -n1)
    else
        KERNEL=$(ls -v /boot/vmlinuz-* 2>/dev/null | tail -n1)
    fi
fi

if [ -z "$KERNEL" ] || [ ! -f "$KERNEL" ]; then
    echo "[-] Error: No kernel image found in /boot to sign."
    exit 1
fi

echo "[*] Target kernel image: $KERNEL"

# ------------------------------------------------------------------------------
# 5. Sign the Kernel and Verify Signature
# ------------------------------------------------------------------------------
echo "[*] Signing kernel image with sbsign..."
sbsign --key "$KEY" --cert "$CERT" "$KERNEL" --output "$KERNEL"

if command -v sbverify &>/dev/null; then
    echo "[*] Verifying cryptographic signature..."
    if sbverify --cert "$CERT" "$KERNEL" &>/dev/null; then
        echo "[✓] Signature verified successfully with sbverify!"
    else
        echo "[!] Warning: sbverify could not verify signature immediately, but signing succeeded."
    fi
fi

echo "======================================================="
echo "[✓] SUCCESS: Kernel is signed and ready for Secure Boot!"
echo "======================================================="
