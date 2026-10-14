#!/usr/bin/env bash
# ==============================================================================
# Universal Linux Kernel & Package Signer (CachyOS / Debian)
#
# Standalone Modes:
#   Mode A (UEFI Secure Boot Signing):
#     ./sign-kernel.sh --secureboot [kernel-version-or-path]
#
#   Mode B (.deb Package GPG Signing):
#     ./sign-kernel.sh --debs <deb_directory> [gpg_key_id]
# ==============================================================================
set -e

show_usage() {
    cat << 'EOF'
Usage:
  ./sign-kernel.sh --secureboot [kernel-version-or-path]
      Signs /boot/vmlinuz-<kernel_version> using MOK keys for UEFI Secure Boot
      and regenerates the initramfs.

  ./sign-kernel.sh --debs <deb_directory> [gpg_key_id]
      Cryptographically signs all compiled .deb packages in <deb_directory>
      using a local GPG key (via dpkg-sig / debsigs and detached signatures).

  ./sign-kernel.sh --sign-deb-mok <deb_directory>
      Unpacks linux-image-*.deb packages in <deb_directory>, signs the kernel
      binary (vmlinuz) using local MOK key with sbsign, verifies with sbverify,
      and repacks the packages for UEFI Secure Boot.

  ./sign-kernel.sh --help | -h
      Displays this help information.

Examples:
  ./sign-kernel.sh --secureboot 7.2.10-cachyos-debian
  ./sign-kernel.sh --sign-deb-mok ~/kernel-build-deb/Linux-kernel-CachyOS-7.2.10-1-debian
  ./sign-kernel.sh --debs ~/kernel-build-deb/Linux-kernel-CachyOS-7.2.10-1-debian
EOF
}

# Resolve real invoking user and home directory
get_real_user_home() {
    local real_user="${SUDO_USER:-${PKEXEC_UID:+$(id -nu "$PKEXEC_UID" 2>/dev/null)}}"
    real_user="${real_user:-$USER}"
    local real_home=""
    if command -v getent &>/dev/null; then
        real_home=$(getent passwd "$real_user" 2>/dev/null | cut -d: -f6)
    fi
    echo "${real_home:-$HOME}"
}

get_real_user() {
    local real_user="${SUDO_USER:-${PKEXEC_UID:+$(id -nu "$PKEXEC_UID" 2>/dev/null)}}"
    echo "${real_user:-$USER}"
}

# Privilege escalation helper
run_as_root() {
    if [ "$EUID" -eq 0 ]; then
        "$@"
    elif command -v pkexec &>/dev/null; then
        pkexec "$@"
    elif command -v sudo &>/dev/null; then
        sudo "$@"
    else
        echo "[-] Error: Root privileges required for: $*"
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# Mode A: UEFI Secure Boot Signing (MOK)
# ------------------------------------------------------------------------------
sign_secureboot() {
    local TARGET="$1"
    echo "======================================================="
    echo "  UEFI Secure Boot Kernel Signer (MOK)"
    echo "======================================================="

    # 1. Check prerequisites
    local missing_tools=()
    command -v sbsign &>/dev/null || missing_tools+=("sbsign")
    command -v openssl &>/dev/null || missing_tools+=("openssl")
    command -v mokutil &>/dev/null || missing_tools+=("mokutil")

    if [ ${#missing_tools[@]} -gt 0 ]; then
        echo "[*] Missing required tool(s): ${missing_tools[*]}"
        echo "[*] Auto-installing prerequisites (sbsigntool, openssl, mokutil)..."
        run_as_root apt-get update
        run_as_root apt-get install -y --no-install-recommends sbsigntool openssl mokutil
        echo "[✓] All prerequisites installed successfully."
    fi

    # 2. Check Secure Boot Status
    if command -v mokutil &>/dev/null; then
        local sb_status
        sb_status=$(mokutil --sb-state 2>/dev/null || true)
        if [[ "$sb_status" =~ "SecureBoot enabled" ]]; then
            echo "[i] Secure Boot is currently: ENABLED (signing is mandatory to boot)"
        elif [[ "$sb_status" =~ "SecureBoot disabled" ]]; then
            echo "[i] Secure Boot is currently: DISABLED (signing for compatibility)"
        else
            echo "[i] Secure Boot status: ${sb_status:-Unknown}"
        fi
    fi

    # 3. Locate or Generate MOK keypair
    local real_home
    real_home="$(get_real_user_home)"
    local real_user
    real_user="$(get_real_user)"
    local user_mok_dir="${real_home}/.config/cachy-kernel-updater/mok"

    local KEY=""
    local CERT=""
    local search_dirs=(
        "$user_mok_dir"
        "/var/lib/shim-signed/mok"
        "/etc/secureboot/mok"
        "${real_home}/.mok"
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

    if [ -z "$KEY" ] || [ -z "$CERT" ]; then
        echo "[!] No existing Machine Owner Key (MOK) found."
        echo "[*] Generating a new persistent 2048-bit RSA MOK keypair in $user_mok_dir..."
        mkdir -p "$user_mok_dir"
        chmod 700 "$user_mok_dir"

        openssl req -new -x509 -newkey rsa:2048 \
            -keyout "$user_mok_dir/MOK.priv" \
            -out "$user_mok_dir/MOK.pem" \
            -nodes -days 3650 \
            -subj "/CN=CachyOS Custom Kernel MOK ($(hostname))/"

        openssl x509 -in "$user_mok_dir/MOK.pem" -outform DER -out "$user_mok_dir/MOK.der"
        chmod 600 "$user_mok_dir/MOK.priv"
        chmod 644 "$user_mok_dir/MOK.pem" "$user_mok_dir/MOK.der"

        if [ "$EUID" -eq 0 ] && [ "$real_user" != "root" ]; then
            chown -R "$real_user":"$(id -ng "$real_user")" "$user_mok_dir" 2>/dev/null || true
        fi

        KEY="$user_mok_dir/MOK.priv"
        CERT="$user_mok_dir/MOK.pem"
        echo "[✓] Created persistent MOK keypair: $user_mok_dir"

        echo ""
        echo "========================================================================="
        echo "  FIRST-TIME MOK ENROLLMENT REQUIRED"
        echo "========================================================================="
        echo "  Enrolling MOK certificate with mokutil..."
        echo "  You will be prompted to set a temporary enrollment password."
        echo "========================================================================="
        run_as_root mokutil --import "$user_mok_dir/MOK.der" || true
        echo ""
        echo "  Next reboot instructions:"
        echo "    1. On reboot, select 'Enroll MOK' in the blue MOKManager screen."
        echo "    2. Select 'Continue' -> 'Yes'."
        echo "    3. Enter the temporary password you just set."
        echo "========================================================================="
        echo ""
    fi

    # 4. Locate Target Kernel Image
    local KERNEL=""
    if [ -n "$TARGET" ]; then
        if [ -f "$TARGET" ]; then
            KERNEL="$TARGET"
        elif [ -f "/boot/$TARGET" ]; then
            KERNEL="/boot/$TARGET"
        elif [ -f "/boot/vmlinuz-${TARGET}" ]; then
            KERNEL="/boot/vmlinuz-${TARGET}"
        else
            echo "[-] Error: Target kernel '$TARGET' not found in /boot."
            exit 1
        fi
    else
        local candidates
        candidates=$(ls -v /boot/vmlinuz-*cachyos* 2>/dev/null || true)
        if [ -n "$candidates" ]; then
            KERNEL=$(echo "$candidates" | tail -n1)
        else
            KERNEL=$(ls -v /boot/vmlinuz-* 2>/dev/null | tail -n1)
        fi
    fi

    if [ -z "$KERNEL" ] || [ ! -f "$KERNEL" ]; then
        echo "[-] Error: No kernel image found in /boot to sign."
        exit 1
    fi

    local kernel_base
    kernel_base="$(basename "$KERNEL")"
    local kernel_ver="${kernel_base#vmlinuz-}"
    echo "[*] Target kernel image: $KERNEL ($kernel_ver)"

    # 5. Sign the Kernel and Regenerate Initramfs
    echo "[*] Signing kernel image with sbsign..."
    run_as_root sbsign --key "$KEY" --cert "$CERT" "$KERNEL" --output "$KERNEL"

    if command -v sbverify &>/dev/null; then
        echo "[*] Verifying cryptographic signature..."
        if sbverify --cert "$CERT" "$KERNEL" &>/dev/null; then
            echo "[✓] Signature verified successfully with sbverify!"
        else
            echo "[!] Warning: sbverify could not verify signature immediately, but signing succeeded."
        fi
    fi

    echo "[*] Updating initramfs for kernel $kernel_ver..."
    run_as_root update-initramfs -u -k "$kernel_ver"

    echo "======================================================="
    echo "[✓] SUCCESS: Kernel $kernel_ver is signed & ready for Secure Boot!"
    echo "======================================================="
}

# ------------------------------------------------------------------------------
# Mode B: .deb Package GPG Signing
# ------------------------------------------------------------------------------
sign_debs() {
    local DEB_DIR="$1"
    local GPG_KEY_ID="$2"

    echo "======================================================="
    echo "  Debian Package GPG Signer (.deb)"
    echo "======================================================="

    if [ -z "$DEB_DIR" ] || [ ! -d "$DEB_DIR" ]; then
        echo "[-] Error: Debian package directory '$DEB_DIR' not found."
        echo "    Usage: ./sign-kernel.sh --debs <deb_directory> [gpg_key_id]"
        exit 1
    fi

    # 1. Check prerequisites: gpg and debsigs/dpkg-sig
    if ! command -v gpg &>/dev/null; then
        echo "[*] Installing gnupg..."
        run_as_root apt-get update
        run_as_root apt-get install -y --no-install-recommends gnupg
    fi

    if ! command -v debsigs &>/dev/null && ! command -v dpkg-sig &>/dev/null; then
        echo "[*] Neither 'debsigs' nor 'dpkg-sig' found. Installing 'debsigs'..."
        run_as_root apt-get update
        run_as_root apt-get install -y --no-install-recommends debsigs || true
    fi

    # 2. Check GPG Key availability
    if [ -z "$GPG_KEY_ID" ]; then
        # Auto-detect default secret key from local keyring
        local detected_key
        detected_key=$(gpg --list-secret-keys --with-colons 2>/dev/null | awk -F: '/^sec:/ {print $5}' | head -n1 || true)
        if [ -n "$detected_key" ]; then
            GPG_KEY_ID="$detected_key"
            echo "[✓] Auto-detected local GPG secret key: $GPG_KEY_ID"
        else
            echo "[!] Warning: No GPG secret key specified and none detected in keyring."
            echo "    Will attempt signing with default GPG key configuration."
        fi
    else
        echo "[✓] Using specified GPG Key: $GPG_KEY_ID"
    fi

    # 3. Locate .deb files
    local deb_files=()
    shopt -s nullglob
    for f in "$DEB_DIR"/linux-image-*.deb "$DEB_DIR"/linux-headers-*.deb; do
        if [[ "$f" != *"-dbg"* ]]; then
            deb_files+=("$f")
        fi
    done

    if [ ${#deb_files[@]} -eq 0 ]; then
        deb_files=("$DEB_DIR"/*.deb)
    fi
    shopt -u nullglob

    if [ ${#deb_files[@]} -eq 0 ]; then
        echo "[-] Error: No .deb packages found in $DEB_DIR to sign."
        exit 1
    fi

    echo "[*] Found ${#deb_files[@]} package(s) to sign in $DEB_DIR:"
    for deb in "${deb_files[@]}"; do
        echo "    • $(basename "$deb")"
    done
    echo ""

    # 4. Sign each deb package
    local signed_count=0
    for deb in "${deb_files[@]}"; do
        local deb_name
        deb_name="$(basename "$deb")"
        echo "[*] Signing $deb_name..."

        local signed_embedded=false
        if command -v dpkg-sig &>/dev/null; then
            if [ -n "$GPG_KEY_ID" ]; then
                dpkg-sig -k "$GPG_KEY_ID" --sign builder "$deb" && signed_embedded=true
            else
                dpkg-sig --sign builder "$deb" && signed_embedded=true
            fi
        elif command -v debsigs &>/dev/null; then
            if [ -n "$GPG_KEY_ID" ]; then
                debsigs --sign=origin --default-key="$GPG_KEY_ID" "$deb" && signed_embedded=true
            else
                debsigs --sign=origin "$deb" && signed_embedded=true
            fi
        fi

        # Always generate detached ASCII-armored GPG signature file (.sig)
        if [ -n "$GPG_KEY_ID" ]; then
            gpg --batch --yes --default-key "$GPG_KEY_ID" -abs -o "${deb}.sig" "$deb"
        else
            gpg --batch --yes -abs -o "${deb}.sig" "$deb"
        fi

        if [ "$signed_embedded" = true ]; then
            echo "[✓] Successfully signed $deb_name (embedded signature + detached .sig)"
        else
            echo "[✓] Created detached signature ${deb_name}.sig"
        fi
        signed_count=$((signed_count + 1))
    done

    echo "======================================================="
    echo "[✓] SUCCESS: Signed $signed_count .deb package(s) with GPG!"
    echo "======================================================="
}

# ------------------------------------------------------------------------------
# Mode C: .deb Package UEFI Secure Boot Signing (MOK)
# ------------------------------------------------------------------------------
sign_debs_mok() {
    local DEB_DIR="$1"
    echo "======================================================="
    echo "  Debian Package UEFI Secure Boot Signer (MOK)"
    echo "======================================================="

    if [ -z "$DEB_DIR" ] || [ ! -d "$DEB_DIR" ]; then
        echo "[-] Error: Debian package directory '$DEB_DIR' not found."
        echo "    Usage: ./sign-kernel.sh --sign-deb-mok <deb_directory>"
        exit 1
    fi

    # 1. Prerequisites check
    local missing_tools=()
    command -v sbsign &>/dev/null || missing_tools+=("sbsign")
    command -v sbverify &>/dev/null || missing_tools+=("sbverify")
    command -v openssl &>/dev/null || missing_tools+=("openssl")
    command -v fakeroot &>/dev/null || missing_tools+=("fakeroot")
    command -v dpkg-deb &>/dev/null || missing_tools+=("dpkg-deb")
    if [ ${#missing_tools[@]} -gt 0 ]; then
        echo "[*] Missing required tool(s): ${missing_tools[*]}"
        echo "[*] Installing prerequisites..."
        run_as_root apt-get update
        run_as_root apt-get install -y --no-install-recommends sbsigntool openssl fakeroot dpkg-dev
    fi

    # 2. Locate or Generate MOK keypair
    local real_home
    real_home="$(get_real_user_home)"
    local real_user
    real_user="$(get_real_user)"
    local user_mok_dir="${real_home}/.config/cachy-kernel-updater/mok"

    local KEY=""
    local CERT=""
    local search_dirs=(
        "$user_mok_dir"
        "/var/lib/shim-signed/mok"
        "/etc/secureboot/mok"
        "${real_home}/.mok"
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

    if [ -z "$KEY" ] || [ -z "$CERT" ]; then
        echo "[!] No existing Machine Owner Key (MOK) found."
        echo "[*] Generating a new persistent 2048-bit RSA MOK keypair in $user_mok_dir..."
        mkdir -p "$user_mok_dir"
        chmod 700 "$user_mok_dir"

        openssl req -new -x509 -newkey rsa:2048 \
            -keyout "$user_mok_dir/MOK.priv" \
            -out "$user_mok_dir/MOK.pem" \
            -nodes -days 3650 \
            -subj "/CN=CachyOS Custom Kernel MOK ($(hostname))/"

        openssl x509 -in "$user_mok_dir/MOK.pem" -outform DER -out "$user_mok_dir/MOK.der"
        chmod 600 "$user_mok_dir/MOK.priv"
        chmod 644 "$user_mok_dir/MOK.pem" "$user_mok_dir/MOK.der"

        KEY="$user_mok_dir/MOK.priv"
        CERT="$user_mok_dir/MOK.pem"
        echo "[✓] Created persistent MOK keypair: $user_mok_dir"
    fi

    # 3. Find linux-image-*.deb packages
    local deb_files=()
    shopt -s nullglob
    for f in "$DEB_DIR"/linux-image-*.deb; do
        [[ "$f" == *"-dbg"* ]] && continue
        deb_files+=("$f")
    done
    shopt -u nullglob

    if [ ${#deb_files[@]} -eq 0 ]; then
        echo "[-] No linux-image-*.deb packages found in '$DEB_DIR'."
        exit 1
    fi

    echo "[*] Found ${#deb_files[@]} kernel image package(s) to sign with MOK."
    local signed_count=0
    for deb in "${deb_files[@]}"; do
        local deb_name
        deb_name="$(basename "$deb")"
        echo "[*] Processing $deb_name..."
        local tmp_dir
        tmp_dir="$(mktemp -d -p "$DEB_DIR" .tmp_sign_XXXXXX)"

        fakeroot dpkg-deb -R "$deb" "$tmp_dir"

        local vmlinuz_list=()
        for v in "$tmp_dir"/boot/vmlinuz-*; do
            [[ "$v" == *".signed"* ]] && continue
            [ -f "$v" ] && vmlinuz_list+=("$v")
        done

        if [ ${#vmlinuz_list[@]} -eq 0 ]; then
            echo "    [!] Notice: No boot/vmlinuz-* found in $deb_name; skipping."
            rm -rf "$tmp_dir"
            continue
        fi

        for v in "${vmlinuz_list[@]}"; do
            local v_base
            v_base="$(basename "$v")"
            echo "    • Signing $v_base with sbsign..."
            sbsign --key "$KEY" --cert "$CERT" --output "${v}.signed" "$v"
            mv "${v}.signed" "$v"
            if command -v sbverify &>/dev/null; then
                sbverify --list "$v" &>/dev/null || true
                echo "    • Signature verified: $v_base is cryptographically signed."
            fi
        done

        echo "    • Repacking $deb_name with fakeroot dpkg-deb -b..."
        fakeroot dpkg-deb -b "$tmp_dir" "$deb"
        rm -rf "$tmp_dir"

        signed_count=$((signed_count + 1))
        echo "    [✓] Successfully signed and repacked $deb_name!"
    done

    echo "======================================================="
    echo "[✓] SUCCESS: Signed $signed_count .deb package(s) with MOK!"
    echo "======================================================="

    # Check enrollment status
    if command -v mokutil &>/dev/null && [ -f "$user_mok_dir/MOK.der" ]; then
        if ! mokutil --test-key "$user_mok_dir/MOK.der" &>/dev/null; then
            echo ""
            echo "[!] Notice: MOK key is not yet enrolled in UEFI NVRAM."
            echo "    Run 'mokutil --import $user_mok_dir/MOK.der' to stage enrollment for next reboot."
            echo ""
        fi
    fi
}

# ------------------------------------------------------------------------------
# Entrypoint Dispatcher
# ------------------------------------------------------------------------------
case "$1" in
    --secureboot|-s)
        shift
        sign_secureboot "$1"
        ;;
    --sign-deb-mok|-m)
        shift
        sign_debs_mok "$1"
        ;;
    --debs|-d)
        shift
        sign_debs "$1" "$2"
        ;;
    --help|-h)
        show_usage
        exit 0
        ;;
    *)
        if [ "$#" -eq 0 ]; then
            # Default to secureboot mode with auto-detection
            sign_secureboot ""
        else
            # Backward-compatibility: if an argument like a kernel path or version is given
            sign_secureboot "$1"
        fi
        ;;
esac
