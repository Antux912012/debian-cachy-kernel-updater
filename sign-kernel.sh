#!/usr/bin/env bash
# ==============================================================================
# Debian CachyOS Kernel Secure Boot Signing Script
# Signs custom compiled CachyOS kernels using Machine Owner Keys (MOK)
# ==============================================================================
set -e

if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this script with sudo: sudo ./sign-kernel.sh [kernel-version]"
  exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check possible locations for MOK private key and certificate
KEY=""
CERT=""

for dir in "$SCRIPT_DIR" "/home/antonio/kernel-build" "/var/lib/shim-signed/mok" "$HOME/.mok" "/root/.mok"; do
    if [ -f "$dir/MOK.priv" ] && [ -f "$dir/MOK.pem" ]; then
        KEY="$dir/MOK.priv"
        CERT="$dir/MOK.pem"
        break
    elif [ -f "$dir/MOK.key" ] && [ -f "$dir/MOK.crt" ]; then
        KEY="$dir/MOK.key"
        CERT="$dir/MOK.crt"
        break
    fi
done

# If no MOK keys exist, guide the user to generate them
if [ -z "$KEY" ] || [ -z "$CERT" ]; then
    echo "[!] Machine Owner Key (MOK) pair not found."
    echo "[*] Generating a new MOK key pair in $SCRIPT_DIR..."
    openssl req -new -x509 -newkey rsa:2048 -keyout "$SCRIPT_DIR/MOK.priv" \
        -out "$SCRIPT_DIR/MOK.pem" -nodes -days 3650 -subj "/CN=CachyOS Custom Kernel/"
    openssl x509 -in "$SCRIPT_DIR/MOK.pem" -outform DER -out "$SCRIPT_DIR/MOK.der"
    chmod 600 "$SCRIPT_DIR/MOK.priv"
    KEY="$SCRIPT_DIR/MOK.priv"
    CERT="$SCRIPT_DIR/MOK.pem"
    
    echo "[+] Generated MOK.priv and MOK.der in $SCRIPT_DIR"
    echo "[!] To enroll this key into your UEFI Secure Boot, run:"
    echo "      sudo mokutil --import $SCRIPT_DIR/MOK.der"
    echo "    Set a temporary enrollment password, reboot, and choose 'Enroll MOK' on screen."
fi

# Ensure sbsigntool is installed
if ! command -v sbsign &> /dev/null; then
    echo "[*] Installing sbsigntool..."
    apt-get update && apt-get install -y sbsigntool
fi

# Locate the target kernel image in /boot
if [ -n "${1:-}" ]; then
    KERNEL="/boot/vmlinuz-${1}"
else
    # Automatically find the newest CachyOS kernel or newest kernel in /boot
    KERNEL=$(ls -v /boot/vmlinuz-*cachyos* 2>/dev/null | tail -n1)
    if [ -z "$KERNEL" ]; then
        KERNEL=$(ls -v /boot/vmlinuz-* 2>/dev/null | tail -n1)
    fi
    echo "[*] No kernel version specified. Auto-detected target kernel: $KERNEL"
fi

if [ ! -f "$KERNEL" ]; then
    echo "[-] Error: Kernel image '$KERNEL' not found!"
    exit 1
fi

echo "[*] Signing kernel image for Secure Boot: $KERNEL"
sbsign --key "$KEY" --cert "$CERT" "$KERNEL" --output "$KERNEL"

echo "[✓] Kernel $KERNEL successfully signed for Secure Boot!"
