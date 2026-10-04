import subprocess
import requests
import os
import shutil
import urllib.request
import re

class KernelManager:
    def __init__(self):
        self.releases_api = "https://api.github.com/repos/CachyOS/linux/releases?per_page=30"
        self.pkgbuild_raw = "https://raw.githubusercontent.com/CachyOS/linux-cachyos/master/linux-cachyos/PKGBUILD"
        self.cachy_config_raw = "https://raw.githubusercontent.com/CachyOS/linux-cachyos/master/linux-cachyos/config"
        cache_base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        self.download_dir = os.path.join(cache_base, "cachy-kernel-build")
        
        config_base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        self.config_dir = os.path.join(config_base, "cachy-kernel-updater")
        self.saved_config_path = os.path.join(self.config_dir, "kernel.config")
        os.makedirs(self.config_dir, exist_ok=True)

        self.REQUIRED_BUILD_DEPS = [
            'build-essential',
            'libncurses-dev',
            'bison',
            'flex',
            'libssl-dev',
            'libelf-dev',
            'libdw-dev',
            'bc',
            'rsync',
            'debhelper',
            'pahole',
            'kmod',
            'cpio'
        ]

        self.latest_version = None
        self.latest_tag = None
        self.download_url = None

        self.output_base_dir = os.path.expanduser("~/kernel-build-deb")
        self.last_output_dir = None
        self.container_image_tag = "cachyos-kernel-builder:debian"

    def get_current_kernel_version(self):
        """Returns the currently running kernel version."""
        try:
            return subprocess.check_output(['uname', '-r'], text=True).strip()
        except Exception as e:
            return f"Error: {e}"

    def get_latest_cachy_version(self):
        """Fetches the latest official CachyOS kernel version from CachyOS GitHub repositories."""
        latest_version = None
        latest_tag = None
        download_url = None

        # Method 1: Check official releases from CachyOS/linux (contains official pre-patched kernel tarballs)
        try:
            headers = {'User-Agent': 'Debian-CachyOS-Kernel-Updater'}
            response = requests.get(self.releases_api, headers=headers, timeout=12)
            if response.status_code == 200:
                releases = response.json()
                for rel in releases:
                    tag = rel.get('tag_name', '')
                    # Pick the latest stable release (exclude -rc release candidates)
                    if tag.startswith('cachyos-') and '-rc' not in tag:
                        latest_tag = tag
                        latest_version = tag.replace('cachyos-', '')
                        for asset in rel.get('assets', []):
                            asset_name = asset.get('name', '')
                            if asset_name.endswith('.tar.gz') and not asset_name.endswith('.asc'):
                                download_url = asset.get('browser_download_url')
                                break
                        if latest_version and download_url:
                            break
        except Exception as e:
            print(f"Error fetching releases API: {e}")

        # Method 2: Check official CachyOS PKGBUILD from CachyOS/linux-cachyos master
        try:
            headers = {'User-Agent': 'Debian-CachyOS-Kernel-Updater'}
            r_pb = requests.get(self.pkgbuild_raw, headers=headers, timeout=10)
            if r_pb.status_code == 200:
                text = r_pb.text
                major = re.search(r'^\s*_major=([^\s#]+)', text, re.M)
                minor = re.search(r'^\s*_minor=([^\s#]+)', text, re.M)
                tagrel = re.search(r'^\s*_tagrel=([^\s#]+)', text, re.M)
                if major and minor:
                    rel_num = tagrel.group(1) if tagrel else '1'
                    pkg_ver = f"{major.group(1)}.{minor.group(1)}-{rel_num}"
                    pkg_tag = f"cachyos-{pkg_ver}"
                    
                    # If releases API failed or is older, use PKGBUILD version
                    if not latest_version:
                        latest_version = pkg_ver
                        latest_tag = pkg_tag
                        download_url = f"https://github.com/CachyOS/linux/releases/download/{pkg_tag}/{pkg_tag}.tar.gz"
        except Exception as e:
            print(f"Error checking PKGBUILD: {e}")

        self.latest_version = latest_version or "Unknown"
        self.latest_tag = latest_tag or f"cachyos-{self.latest_version}"
        self.download_url = download_url or (
            f"https://github.com/CachyOS/linux/releases/download/{self.latest_tag}/{self.latest_tag}.tar.gz"
            if latest_tag else None
        )

        return self.latest_version

    def is_matching_running_kernel(self):
        """Checks if the currently running kernel matches the latest CachyOS kernel."""
        current = self.get_current_kernel_version().lower()
        if not self.latest_version or self.latest_version == "Unknown":
            return False
        
        # Extract base version digits like 7.2.8 from 7.2.8-1
        base_ver = self.latest_version.split('-')[0]
        # Check if running kernel contains this version and cachyos
        if base_ver in current and 'cachy' in current:
            return True
        return False

    def _run_cmd(self, cmd, cwd=None, progress_callback=None):
        """Runs a command and yields output live to the callback."""
        if progress_callback:
            progress_callback(f"> {' '.join(cmd)}")
            
        process = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        
        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                if progress_callback and line:
                    progress_callback(line.rstrip())
                    
        process.stdout.close()
        rc = process.wait()
        if rc != 0:
            raise Exception(f"Command failed with return code {rc}: {' '.join(cmd)}")

    def check_build_dependencies(self):
        """Returns a list of missing kernel compiler build dependencies."""
        missing = []
        for pkg in self.REQUIRED_BUILD_DEPS:
            try:
                res = subprocess.run(
                    ['dpkg-query', '-W', '-f=${Status}', pkg],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if 'install ok installed' not in res.stdout:
                    missing.append(pkg)
            except Exception:
                missing.append(pkg)
        return missing

    def install_build_dependencies(self, progress_callback=None):
        """Installs kernel build dependencies using pkexec apt-get."""
        if progress_callback:
            progress_callback("\n=======================================================")
            progress_callback("[*] Requesting root authorization via pkexec to install build dependencies...")
            progress_callback("=======================================================\n")
            progress_callback(f"Packages to install: {' '.join(self.REQUIRED_BUILD_DEPS)}\n")

        cmd = ['pkexec', 'apt-get', 'install', '-y'] + self.REQUIRED_BUILD_DEPS
        try:
            self._run_cmd(cmd, progress_callback=progress_callback)
            if progress_callback:
                progress_callback("\n[✓] Kernel compiler build dependencies installed successfully!\n")
            return True
        except Exception as e:
            if progress_callback:
                progress_callback(f"\n[!] Dependency installation failed: {e}\n")
            return False

    def get_output_kernel_dir(self):
        """Returns the full path to the output kernel deb folder: ~/kernel-build-deb/Linux-kernel-CachyOS-(version)-debian."""
        ver = self.latest_version or "latest"
        folder_name = f"Linux-kernel-CachyOS-{ver}-debian"
        return os.path.join(self.output_base_dir, folder_name)

    def get_container_engine(self):
        """Returns 'podman' or 'docker' if available, otherwise None."""
        if shutil.which("podman"):
            return "podman"
        if shutil.which("docker"):
            return "docker"
        return None

    def has_container_image(self):
        """Checks if the Debian-based builder container image is already available and has required tools."""
        engine = self.get_container_engine()
        if not engine:
            return False
        try:
            if engine == "podman":
                res = subprocess.run([engine, "image", "exists", self.container_image_tag],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode != 0:
                    return False
            else:
                res = subprocess.run([engine, "inspect", "--type=image", self.container_image_tag],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode != 0:
                    return False

            # Verify that essential build tools (such as libdw-dev) exist in the container image
            check_pkg = subprocess.run(
                [engine, "run", "--rm", self.container_image_tag, "dpkg-query", "-W", "-f=${Status}", "libdw-dev"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
            return "install ok installed" in check_pkg.stdout
        except Exception:
            return False

    def ensure_container_image(self, progress_callback=None):
        """Ensures the Debian Bookworm builder image is built and ready."""
        engine = self.get_container_engine()
        if not engine:
            raise Exception("Neither podman nor docker was found. Please install podman or docker.")

        if self.has_container_image():
            if progress_callback:
                progress_callback(f"[✓] Container image verified: {self.container_image_tag} ({engine})")
            return True

        if progress_callback:
            progress_callback(f"\n[*] Preparing {self.container_image_tag} using {engine}...")
            progress_callback("Base: Debian Bookworm (ensures maximum generic compatibility and zero host dependencies)")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        containerfile_path = os.path.join(base_dir, "Containerfile")
        if not os.path.exists(containerfile_path):
            containerfile_path = os.path.join(self.download_dir, "Containerfile")
            os.makedirs(self.download_dir, exist_ok=True)
            with open(containerfile_path, "w") as cf:
                cf.write("""FROM docker.io/library/debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    bc \\
    bison \\
    flex \\
    libelf-dev \\
    libssl-dev \\
    libncurses-dev \\
    libdw-dev \\
    rsync \\
    kmod \\
    cpio \\
    pahole \\
    zstd \\
    tar \\
    xz-utils \\
    dpkg-dev \\
    debhelper \\
    python3 \\
    gcc \\
    make \\
    git \\
    ca-certificates \\
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
""")

        build_cmd = [engine, "build", "-t", self.container_image_tag, "-f", containerfile_path, os.path.dirname(containerfile_path)]
        self._run_cmd(build_cmd, progress_callback=progress_callback)
        if progress_callback:
            progress_callback(f"[✓] Successfully built container image: {self.container_image_tag}\n")
        return True

    def cleanup_cache_on_startup(self, progress_callback=None):
        """
        Checks ~/.cache for the kernel build directory on application launch.
        Preserves any generated .config to persistent storage before cleaning.
        """
        # First ensure persistent storage has an initial config from running CachyOS kernel if missing
        if not os.path.exists(self.saved_config_path):
            current_kernel = self.get_current_kernel_version()
            boot_cfg = f"/boot/config-{current_kernel}"
            if os.path.isfile(boot_cfg) and 'cachy' in current_kernel:
                try:
                    os.makedirs(os.path.dirname(self.saved_config_path), exist_ok=True)
                    shutil.copy(boot_cfg, self.saved_config_path)
                    if progress_callback:
                        progress_callback(f"[✓] Initialized configuration from running CachyOS kernel ({boot_cfg})")
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"[!] Warning: could not seed initial config from {boot_cfg}: {e}")

        if not os.path.exists(self.download_dir):
            if progress_callback:
                progress_callback(f"[i] Cache check: {self.download_dir} is clean.")
            return

        # Do not clean if a build is actively running (lockfile check)
        lock_file = os.path.join(self.download_dir, ".building")
        if os.path.exists(lock_file):
            try:
                with open(lock_file, "r") as lf:
                    pid = int(lf.read().strip())
                # Check if process is still running
                os.kill(pid, 0)
                if progress_callback:
                    progress_callback(f"[i] Build process (PID {pid}) is currently running in cache; skipping cleanup.")
                return
            except (ProcessLookupError, ValueError, OSError):
                # Stale lockfile, proceed with cleanup
                pass

        if progress_callback:
            progress_callback(f"[*] Checking cache folder: {self.download_dir}...")

        # Search for any generated .config inside the download_dir tree to preserve it
        found_config = None
        for root, dirs, files in os.walk(self.download_dir):
            if ".config" in files:
                candidate = os.path.join(root, ".config")
                if os.path.isfile(candidate) and os.path.getsize(candidate) > 1000:
                    found_config = candidate
                    break

        # Save config if found and not yet saved or if found is newer
        if found_config:
            should_save = False
            if not os.path.exists(self.saved_config_path):
                should_save = True
            elif os.path.getmtime(found_config) > os.path.getmtime(self.saved_config_path):
                should_save = True

            if should_save:
                try:
                    os.makedirs(os.path.dirname(self.saved_config_path), exist_ok=True)
                    shutil.copy(found_config, self.saved_config_path)
                    if progress_callback:
                        progress_callback(f"[✓] Preserved generated kernel configuration to {self.saved_config_path}")
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"[!] Warning: could not backup config: {e}")

        # Clean the cachy-kernel-build folder with robust permission handling
        try:
            import stat
            for root, dirs, files in os.walk(self.download_dir, topdown=False):
                for name in files:
                    p = os.path.join(root, name)
                    try:
                        os.chmod(p, stat.S_IWUSR | stat.S_IRUSR)
                        os.unlink(p)
                    except Exception:
                        pass
                for name in dirs:
                    p = os.path.join(root, name)
                    try:
                        os.chmod(p, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
                        os.rmdir(p)
                    except Exception:
                        pass
            try:
                os.rmdir(self.download_dir)
            except Exception:
                shutil.rmtree(self.download_dir, ignore_errors=True)

            if progress_callback:
                progress_callback(f"[✓] Cleaned previous build artifacts from {self.download_dir}\n")
        except Exception as e:
            if progress_callback:
                progress_callback(f"[!] Warning: could not clean {self.download_dir}: {e}\n")

    def download_kernel(self, progress_callback=None):
        """Downloads the official pre-patched CachyOS kernel source and configuration."""
        if not self.latest_version or not self.download_url:
            self.get_latest_cachy_version()

        if not self.download_url:
            raise Exception("Unable to find download URL for latest CachyOS kernel.")

        os.makedirs(self.download_dir, exist_ok=True)

        # Write active build lockfile
        lock_file = os.path.join(self.download_dir, ".building")
        try:
            with open(lock_file, "w") as lf:
                lf.write(str(os.getpid()))
        except Exception:
            pass

        archive_name = f"{self.latest_tag}.tar.gz"
        archive_path = os.path.join(self.download_dir, archive_name)
        part_path = os.path.join(self.download_dir, f"{archive_name}.part")

        if progress_callback:
            progress_callback(f"Target: CachyOS Kernel {self.latest_version}")

        # Tarball integrity validator
        def is_tarball_valid(path):
            if not os.path.isfile(path) or os.path.getsize(path) < 10000000:
                return False
            try:
                res = subprocess.run(['tar', '-tzf', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return res.returncode == 0
            except Exception:
                return False

        # Download tarball with progress indication and integrity check
        if not is_tarball_valid(archive_path):
            if os.path.exists(archive_path):
                try:
                    os.unlink(archive_path)
                except Exception:
                    pass

            if progress_callback:
                progress_callback(f"Downloading from {self.download_url}...")

            def report_hook(block_num, block_size, total_size):
                if total_size > 0 and block_num % 1000 == 0:
                    downloaded = block_num * block_size
                    percent = min(100, int(downloaded * 100 / total_size))
                    mb_down = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    if progress_callback:
                        progress_callback(f"Downloading: {percent}% ({mb_down:.1f} MB / {mb_total:.1f} MB)")

            urllib.request.urlretrieve(self.download_url, part_path, reporthook=report_hook)

            if not is_tarball_valid(part_path):
                raise Exception("Downloaded kernel archive is incomplete or corrupted. Please check network connection.")

            os.replace(part_path, archive_path)
        else:
            if progress_callback:
                progress_callback(f"[✓] Verified existing archive: {archive_name}")

        extracted_dir = os.path.join(self.download_dir, self.latest_tag)

        # Validate extracted directory integrity
        def is_extracted_valid(path):
            if not os.path.isdir(path):
                return False
            makefile = os.path.join(path, "Makefile")
            compiler_h = os.path.join(path, "include/linux/compiler-version.h")
            return os.path.isfile(makefile) and os.path.isfile(compiler_h)

        if not is_extracted_valid(extracted_dir):
            if os.path.exists(extracted_dir):
                shutil.rmtree(extracted_dir, ignore_errors=True)

            if progress_callback:
                progress_callback(f"Extracting {archive_name}...")

            self._run_cmd(['tar', '-xf', archive_path], cwd=self.download_dir, progress_callback=progress_callback)

        # Download official CachyOS config if needed
        config_path = os.path.join(self.download_dir, "config")
        if not os.path.exists(config_path) or os.path.getsize(config_path) < 1000:
            if progress_callback:
                progress_callback("Fetching official CachyOS kernel config...")
            try:
                urllib.request.urlretrieve(self.cachy_config_raw, config_path)
            except Exception:
                pass

        if not os.path.exists(extracted_dir):
            # Fallback search if folder name differs
            candidates = [
                d for d in os.listdir(self.download_dir) 
                if os.path.isdir(os.path.join(self.download_dir, d)) and 'cachy' in d
            ]
            if candidates:
                extracted_dir = os.path.join(self.download_dir, candidates[0])
            else:
                raise Exception(f"Extracted directory not found in {self.download_dir}")

        if progress_callback:
            progress_callback(f"[✓] Kernel source verified and ready in {extracted_dir}")

        return extracted_dir

    def compile_kernel(self, kernel_dir, progress_callback=None, use_container=False):
        """Prepares configuration and compiles the kernel into Debian packages."""
        if progress_callback:
            progress_callback("Setting up kernel configuration for Debian...")

        config_dst = os.path.join(kernel_dir, ".config")

        # Recover saved config if available, otherwise use running CachyOS kernel or downloaded official config
        if os.path.exists(self.saved_config_path) and os.path.getsize(self.saved_config_path) > 1000:
            if progress_callback:
                progress_callback(f"[✓] Recovering previously saved kernel configuration from {self.saved_config_path}...")
            shutil.copy(self.saved_config_path, config_dst)
        else:
            current_kernel = self.get_current_kernel_version()
            boot_cfg = f"/boot/config-{current_kernel}"
            if os.path.isfile(boot_cfg) and 'cachy' in current_kernel:
                if progress_callback:
                    progress_callback(f"[✓] Recovering configuration from running kernel ({boot_cfg})...")
                shutil.copy(boot_cfg, config_dst)
            else:
                if progress_callback:
                    progress_callback("Applying official CachyOS base kernel configuration...")
                config_src = os.path.join(self.download_dir, "config")
                if os.path.exists(config_src):
                    shutil.copy(config_src, config_dst)
                else:
                    urllib.request.urlretrieve(self.cachy_config_raw, config_dst)

        # Apply necessary tweaks for Debian environment
        # 1. Disable trusted and revocation keys which cause Debian builds to fail without local certificates
        self._run_cmd(['scripts/config', '--disable', 'SYSTEM_TRUSTED_KEYS'], cwd=kernel_dir, progress_callback=None)
        self._run_cmd(['scripts/config', '--disable', 'SYSTEM_REVOCATION_KEYS'], cwd=kernel_dir, progress_callback=None)
        
        # 2. Disable heavy debug info to prevent huge 40GB+ deb packages and out-of-space errors
        self._run_cmd(['scripts/config', '--disable', 'CONFIG_DEBUG_INFO'], cwd=kernel_dir, progress_callback=None)
        self._run_cmd(['scripts/config', '--disable', 'CONFIG_DEBUG_INFO_DWARF5'], cwd=kernel_dir, progress_callback=None)
        self._run_cmd(['scripts/config', '--disable', 'CONFIG_DEBUG_INFO_DWARF4'], cwd=kernel_dir, progress_callback=None)
        self._run_cmd(['scripts/config', '--disable', 'CONFIG_DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT'], cwd=kernel_dir, progress_callback=None)
        self._run_cmd(['scripts/config', '--enable', 'CONFIG_DEBUG_INFO_NONE'], cwd=kernel_dir, progress_callback=None)

        # 3. Disable enterprise server-only features that can fail on desktop/laptop toolchains
        self._run_cmd(['scripts/config', '--disable', 'CONFIG_INTEL_TDX_HOST'], cwd=kernel_dir, progress_callback=None)
        self._run_cmd(['scripts/config', '--disable', 'CONFIG_KVM_INTEL_TDX'], cwd=kernel_dir, progress_callback=None)

        # 4. Set Debian localversion so generated kernel has clean branding
        self._run_cmd(['scripts/config', '--set-str', 'CONFIG_LOCALVERSION', '-cachyos-debian'], cwd=kernel_dir, progress_callback=None)

        # Prepare container runner prefix if container build is selected
        container_prefix = []
        if use_container:
            engine = self.get_container_engine()
            if not engine:
                raise Exception("Container build requested but neither podman nor docker is installed.")
            self.ensure_container_image(progress_callback=progress_callback)
            
            rel_kernel = os.path.relpath(kernel_dir, self.download_dir)
            container_prefix = [engine, "run", "--rm"]
            if engine == "podman":
                container_prefix += ["--userns=keep-id"]
            else:
                container_prefix += ["-u", f"{os.getuid()}:{os.getgid()}"]
            
            container_prefix += [
                "-v", f"{self.download_dir}:/workspace:z",
                "-w", f"/workspace/{rel_kernel}",
                "-e", "KBUILD_BUILD_USER=cachyos",
                "-e", "KBUILD_BUILD_HOST=debian",
                self.container_image_tag
            ]

        # 5. Update configuration for the new kernel version
        if use_container:
            self._run_cmd(container_prefix + ['make', 'olddefconfig'], cwd=kernel_dir, progress_callback=progress_callback)
        else:
            self._run_cmd(['make', 'olddefconfig'], cwd=kernel_dir, progress_callback=progress_callback)

        # 6. Save the generated configuration to persistent storage for future updates
        try:
            os.makedirs(os.path.dirname(self.saved_config_path), exist_ok=True)
            shutil.copy(config_dst, self.saved_config_path)
            if progress_callback:
                progress_callback(f"[✓] Preserved updated kernel configuration in {self.saved_config_path}")
        except Exception as e:
            if progress_callback:
                progress_callback(f"[!] Warning: could not save configuration: {e}")

        cores = str(os.cpu_count() or 4)
        if progress_callback:
            mode_desc = f"inside Debian container ({self.get_container_engine()})" if use_container else "on host system"
            progress_callback(f"Starting kernel compilation {mode_desc} using {cores} CPU threads...")
            progress_callback("Running 'make bindeb-pkg' (Debian package build)...")

        try:
            # Compile and generate .deb packages
            if use_container:
                self._run_cmd(container_prefix + ['make', f'-j{cores}', 'bindeb-pkg'], cwd=kernel_dir, progress_callback=progress_callback)
            else:
                self._run_cmd(['make', f'-j{cores}', 'bindeb-pkg'], cwd=kernel_dir, progress_callback=progress_callback)
        finally:
            # Clean up active build lockfile
            lock_file = os.path.join(self.download_dir, ".building")
            if os.path.exists(lock_file):
                try:
                    os.unlink(lock_file)
                except Exception:
                    pass

        # 7. Collect all generated deb packages and save to ~/kernel-build-deb/Linux-kernel-CachyOS-(version)-debian
        output_dir = self.get_output_kernel_dir()
        os.makedirs(output_dir, exist_ok=True)
        self.last_output_dir = output_dir

        if progress_callback:
            progress_callback(f"\n[*] Collecting generated Debian packages into:\n    {output_dir}")

        import glob
        patterns = ["linux-image-*.deb", "linux-headers-*.deb", "linux-libc-dev-*.deb", "*.changes", "*.buildinfo"]
        found_files = []
        for pat in patterns:
            found_files.extend(glob.glob(os.path.join(self.download_dir, pat)))
        for pat in patterns:
            found_files.extend(glob.glob(os.path.join(kernel_dir, pat)))

        copied_count = 0
        for fpath in set(found_files):
            fname = os.path.basename(fpath)
            dst_path = os.path.join(output_dir, fname)
            try:
                shutil.copy2(fpath, dst_path)
                copied_count += 1
                if progress_callback:
                    progress_callback(f"    • Copied {fname}")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"    [!] Warning: could not copy {fname}: {e}")

        # Also preserve .config in the output directory
        if os.path.exists(config_dst):
            try:
                shutil.copy2(config_dst, os.path.join(output_dir, "kernel.config"))
                if progress_callback:
                    progress_callback("    • Copied kernel.config")
            except Exception:
                pass

        # Generate standalone install.sh script in the output directory
        install_script_path = os.path.join(output_dir, "install.sh")
        try:
            ver = self.latest_version or "latest"
            with open(install_script_path, "w") as sf:
                sf.write(f"""#!/usr/bin/env bash
# CachyOS Kernel Debian Package Installer
# Kernel: Linux-kernel-CachyOS-{ver}-debian
set -e

DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" >/dev/null 2>&1 && pwd)"
echo "=== Installing Linux-kernel-CachyOS-{ver}-debian ==="
echo "Package directory: $DIR"

DEBS=()
for f in "$DIR"/linux-image-*.deb "$DIR"/linux-headers-*.deb; do
    if [ -f "$f" ] && [[ "$f" != *"-dbg"* ]]; then
        DEBS+=("$f")
    fi
done

if [ ${{#DEBS[@]}} -eq 0 ]; then
    echo "Error: No suitable kernel .deb packages found in $DIR"
    exit 1
fi

echo "Installing packages: ${{DEBS[@]}}"
if command -v pkexec >/dev/null 2>&1; then
    pkexec dpkg -i "${{DEBS[@]}}"
    pkexec update-grub
elif [ "$(id -u)" -eq 0 ]; then
    dpkg -i "${{DEBS[@]}}"
    update-grub
else
    sudo dpkg -i "${{DEBS[@]}}"
    sudo update-grub
fi

echo "=========================================================="
echo "Installation complete! Please reboot to boot the new kernel."
echo "=========================================================="
""")
            os.chmod(install_script_path, 0o755)
            if progress_callback:
                progress_callback("    • Generated install.sh helper script")
        except Exception as e:
            if progress_callback:
                progress_callback(f"    [!] Warning: could not create install.sh: {e}")

        if progress_callback:
            progress_callback(f"\n[✓] Compilation completed successfully! Saved {copied_count} artifact(s) to:\n    {output_dir}")

    def install_kernel(self, progress_callback=None):
        """Installs the compiled .deb packages using pkexec."""
        import glob
        
        search_dirs = []
        if self.last_output_dir and os.path.isdir(self.last_output_dir):
            search_dirs.append(self.last_output_dir)
        output_dir = self.get_output_kernel_dir()
        if os.path.isdir(output_dir) and output_dir not in search_dirs:
            search_dirs.append(output_dir)
        if self.download_dir not in search_dirs:
            search_dirs.append(self.download_dir)

        deb_files = []
        source_dir = None
        for sdir in search_dirs:
            candidates = glob.glob(os.path.join(sdir, "linux-image-*.deb"))
            candidates += glob.glob(os.path.join(sdir, "linux-headers-*.deb"))
            candidates = [f for f in candidates if '-dbg' not in f]
            if candidates:
                deb_files = candidates
                source_dir = sdir
                break

        if not deb_files:
            if progress_callback:
                progress_callback("Error: No linux-image or linux-headers .deb files found in output or build directories.")
            return False

        if progress_callback:
            progress_callback(f"Installing packages from: {source_dir}")
            progress_callback(f"Found packages: {[os.path.basename(f) for f in deb_files]}")
            progress_callback("Requesting root permissions via pkexec to install packages...")

        cmd = ['pkexec', 'dpkg', '-i'] + deb_files
        try:
            self._run_cmd(cmd, cwd=source_dir, progress_callback=progress_callback)
            if progress_callback:
                progress_callback("Installation successful! Updating GRUB...")
            # Ensure grub is updated
            try:
                self._run_cmd(['pkexec', 'update-grub'], cwd=source_dir, progress_callback=progress_callback)
            except Exception:
                pass
            return True
        except Exception as e:
            if progress_callback:
                progress_callback(f"Installation failed: {e}")
            return False

    def get_installed_kernels(self):
        """Returns a list of installed linux-image packages."""
        try:
            output = subprocess.check_output(
                ['dpkg-query', '-W', '-f=${binary:Package}\\n', 'linux-image-*'], 
                text=True
            )
            packages = [line.strip() for line in output.split('\n') if line.strip() and 'dbg' not in line]
            return packages
        except subprocess.CalledProcessError:
            return []

    def remove_kernel(self, package_name, progress_callback=None):
        """Removes a specific kernel package using pkexec."""
        if progress_callback:
            progress_callback(f"Removing {package_name} via pkexec...")
        cmd = ['pkexec', 'apt-get', 'purge', '-y', package_name]
        try:
            self._run_cmd(cmd, cwd='/tmp', progress_callback=progress_callback)
            if progress_callback:
                progress_callback(f"Successfully removed {package_name}. Updating GRUB...")
            try:
                self._run_cmd(['pkexec', 'update-grub'], cwd='/tmp', progress_callback=progress_callback)
            except Exception:
                pass
            return True
        except Exception as e:
            if progress_callback:
                progress_callback(f"Failed to remove {package_name}: {e}")
            return False
