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
        self.saved_native_config_path = os.path.join(self.config_dir, "kernel-native.config")
        os.makedirs(self.config_dir, exist_ok=True)

        self.REQUIRED_BUILD_DEPS = [
            'build-essential',
            'bc',
            'bison',
            'flex',
            'libssl-dev',
            'libelf-dev',
            'libncurses-dev',
            'libdw-dev',
            'libudev-dev',
            'libpci-dev',
            'libiberty-dev',
            'autoconf',
            'dwarves',
            'pahole',
            'zstd',
            'xz-utils',
            'lz4',
            'cpio',
            'rsync',
            'kmod',
            'fakeroot',
            'dpkg-dev',
            'debhelper',
            'devscripts',
            'clang',
            'llvm',
            'lld',
            'sbsigntool',
            'mokutil',
            'openssl'
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

    def detect_hardware(self):
        """
        Detects system hardware: CPU model, vendor, thread count, laptop/chassis status,
        root filesystem, manufacturer, and loaded kernel modules.
        Returns a dict of detected hardware details.
        """
        import glob
        info = {
            'cpu_model': 'Generic x86-64',
            'vendor': 'Unknown',
            'threads': os.cpu_count() or 4,
            'is_laptop': False,
            'manufacturer': 'Generic',
            'product_name': 'PC',
            'root_fs': 'ext4',
            'loaded_modules': []
        }

        # 1. CPU Info from /proc/cpuinfo
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if ':' in line:
                        k, v = [x.strip() for x in line.split(':', 1)]
                        if k == 'model name' and info['cpu_model'] == 'Generic x86-64':
                            info['cpu_model'] = v
                        elif k == 'vendor_id' and info['vendor'] == 'Unknown':
                            info['vendor'] = v
        except Exception:
            pass

        # 2. Laptop detection via /sys/class/power_supply
        try:
            batteries = glob.glob('/sys/class/power_supply/BAT*')
            if batteries:
                info['is_laptop'] = True
        except Exception:
            pass

        # 3. DMI info (Manufacturer and Product)
        try:
            if os.path.exists('/sys/class/dmi/id/sys_vendor'):
                with open('/sys/class/dmi/id/sys_vendor', 'r') as f:
                    info['manufacturer'] = f.read().strip()
            if os.path.exists('/sys/class/dmi/id/product_name'):
                with open('/sys/class/dmi/id/product_name', 'r') as f:
                    info['product_name'] = f.read().strip()
        except Exception:
            pass

        # 4. Root Filesystem
        try:
            df_out = subprocess.check_output(['df', '-T', '/'], text=True).splitlines()
            if len(df_out) > 1:
                info['root_fs'] = df_out[1].split()[1]
        except Exception:
            pass

        # 5. Loaded kernel modules from lsmod
        try:
            lsmod_out = subprocess.check_output(['lsmod'], text=True)
            modules = []
            for line in lsmod_out.splitlines()[1:]:
                parts = line.split()
                if parts:
                    modules.append(parts[0])
            info['loaded_modules'] = modules
        except Exception:
            pass

        return info

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

    def _run_cmd(self, cmd, cwd=None, progress_callback=None, env=None, tee_log=True):
        """Runs a command, logs output live, captures errors, and tees to ~/.cache/cachy-kernel-build/build.log."""
        if progress_callback:
            progress_callback(f"> {' '.join(cmd)}")

        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        os.makedirs(self.download_dir, exist_ok=True)
        build_log_path = os.path.join(self.download_dir, "build.log")

        log_file = None
        if tee_log:
            try:
                log_file = open(build_log_path, "a", encoding="utf-8", errors="replace")
                log_file.write(f"\n--- [Command: {' '.join(cmd)}] ---\n")
                log_file.flush()
            except Exception:
                log_file = None

        error_regex = re.compile(r'(error:|fatal error:|undefined reference|No space left on device|Killed)', re.IGNORECASE)
        captured_errors = []

        process = subprocess.Popen(
            cmd, cwd=cwd, env=run_env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )

        try:
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    stripped = line.rstrip()
                    if log_file:
                        try:
                            log_file.write(line)
                            log_file.flush()
                        except Exception:
                            pass

                    if error_regex.search(stripped):
                        if not re.search(r'0\s+errors', stripped, re.IGNORECASE):
                            captured_errors.append(stripped)

                    if progress_callback and line:
                        progress_callback(stripped)
        finally:
            if process.stdout:
                process.stdout.close()
            if log_file:
                try:
                    log_file.close()
                except Exception:
                    pass

        rc = process.wait()
        if rc != 0:
            err_msg_lines = [
                f"\n=======================================================",
                f"[!] BUILD FAILURE (Return code {rc})",
                f"    Command: {' '.join(cmd)}",
                f"======================================================="
            ]
            if captured_errors:
                err_msg_lines.append("[!] Root-cause compilation error(s) detected:")
                for err_line in captured_errors[-30:]:
                    err_msg_lines.append(f"    >>> {err_line}")
                err_msg_lines.append("-------------------------------------------------------")
            err_msg_lines.append(f"[!] Full build log available at:\n    {build_log_path}")
            err_msg_lines.append("=======================================================\n")

            full_error_text = "\n".join(err_msg_lines)
            if progress_callback:
                progress_callback(full_error_text)
            raise Exception(full_error_text)

    def check_build_dependencies(self, use_container=False):
        """Returns a list of missing build dependencies. Checks container engine and image only if use_container is True."""
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

        # Include container engine and container image dependencies ONLY if build in container is selected
        if use_container:
            engine = self.get_container_engine()
            if not engine:
                missing.append('podman')
            elif not self.has_container_image():
                missing.append(f"container-image:{self.container_image_tag}")

        return missing

    def install_build_dependencies(self, progress_callback=None, use_container=False, force_rebuild=False):
        """
        Installs kernel build dependencies using pkexec apt-get.
        Installs container engine and prepares container image ONLY if use_container is True.
        """
        pkgs = list(self.REQUIRED_BUILD_DEPS)
        if use_container:
            engine = self.get_container_engine()
            if not engine and 'podman' not in pkgs:
                pkgs.append('podman')

        if progress_callback:
            progress_callback("\n=======================================================")
            mode_desc = "container & host" if use_container else "host compiler"
            progress_callback(f"[*] Requesting root authorization via pkexec to install {mode_desc} dependencies...")
            progress_callback("=======================================================\n")
            progress_callback(f"Packages to install: {' '.join(pkgs)}\n")

        cmd = ['pkexec', 'apt-get', 'install', '-y'] + pkgs
        try:
            self._run_cmd(cmd, progress_callback=progress_callback)
            if progress_callback:
                progress_callback("\n[✓] APT dependencies installed successfully!\n")
        except Exception as e:
            if progress_callback:
                progress_callback(f"\n[!] APT dependency installation failed: {e}\n")
            return False

        # Build and verify container image ONLY if container build is selected
        if use_container:
            if progress_callback:
                progress_callback("=======================================================")
                progress_callback(f"[*] Setting up builder container image ({self.container_image_tag})...")
                progress_callback("=======================================================\n")
            try:
                self.ensure_container_image(progress_callback=progress_callback, force=force_rebuild)
                if progress_callback:
                    progress_callback(f"\n[✓] Container image verified and ready: {self.container_image_tag}\n")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"\n[!] Container image setup failed: {e}\n")
                return False

        if progress_callback:
            mode_str = "Container-isolated" if use_container else "Host"
            progress_callback(f"\n[✓] All {mode_str} dependencies ready!\n")
        return True

    def get_output_kernel_dir(self, is_native=False):
        """Returns the full path to the output kernel deb folder: ~/kernel-build-deb/Linux-kernel-CachyOS-(version)-[native-]debian."""
        ver = self.latest_version or "latest"
        tag = "native-debian" if is_native else "debian"
        folder_name = f"Linux-kernel-CachyOS-{ver}-{tag}"
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

    def ensure_container_image(self, progress_callback=None, force=False):
        """Ensures the Debian Bookworm builder image is built and ready."""
        engine = self.get_container_engine()
        if not engine:
            raise Exception("Neither podman nor docker was found. Please install podman or docker.")

        if not force and self.has_container_image():
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

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\
    build-essential \\
    bc \\
    bison \\
    flex \\
    libssl-dev \\
    libelf-dev \\
    libncurses-dev \\
    libdw-dev \\
    libudev-dev \\
    libpci-dev \\
    libiberty-dev \\
    autoconf \\
    dwarves \\
    pahole \\
    zstd \\
    xz-utils \\
    lz4 \\
    cpio \\
    rsync \\
    kmod \\
    fakeroot \\
    dpkg-dev \\
    debhelper \\
    devscripts \\
    git \\
    curl \\
    wget \\
    ca-certificates \\
    python3 \\
    python3-gi \\
    python3-requests \\
    clang \\
    llvm \\
    lld \\
    sbsigntool \\
    mokutil \\
    openssl \\
    && rm -rf /var/lib/apt/lists/*

ENV DEBFULLNAME="CachyOS Debian Builder"
ENV DEBEMAIL="builder@localhost"

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

    def compile_kernel(self, kernel_dir, progress_callback=None, use_container=False, optimize_for_system=False):
        """Prepares configuration and compiles the kernel into Debian packages."""
        if progress_callback:
            progress_callback("Setting up kernel configuration for Debian...")

        config_dst = os.path.join(kernel_dir, ".config")

        # Recover saved config if available, otherwise use running CachyOS kernel or downloaded official config
        active_saved_cfg = self.saved_native_config_path if optimize_for_system else self.saved_config_path
        if os.path.exists(active_saved_cfg) and os.path.getsize(active_saved_cfg) > 1000:
            if progress_callback:
                progress_callback(f"[✓] Recovering previously saved kernel configuration from {active_saved_cfg}...")
            shutil.copy(active_saved_cfg, config_dst)
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

        if not use_container:
            missing_deps = self.check_build_dependencies(use_container=False)
            if missing_deps:
                raise Exception(
                    f"Missing required host compiler packages: {', '.join(missing_deps)}.\n"
                    f"Please install them by clicking 'Install Dependencies' or run:\n"
                    f"sudo apt-get install -y {' '.join(missing_deps)}"
                )

        # Apply necessary tweaks for Debian environment & sanitize .config
        # 1. Remove Debian/Canonical hardcoded certificate paths (Prevents Makefile:2207 crash)
        # 2. Bypass build-time module signing (avoids ephemeral key/cert failures in containers)
        # 3. Keep signature verification support compiled into the kernel for post-build user signing
        # 4. Disable heavy DWARF/BTF debug symbols by default (prevents 30GB+ disk exhaustion & pahole crashes)
        # 5. Disable strict -Werror and Rust (prevents compiler version mismatch failures on Debian)
        config_sanitize_cmd = [
            'scripts/config',
            '--set-str', 'SYSTEM_TRUSTED_KEYS', '',
            '--set-str', 'SYSTEM_REVOCATION_KEYS', '',
            '--set-str', 'MODULE_SIG_KEY', '',
            '--disable', 'MODULE_SIG_ALL',
            '--disable', 'MODULE_SIG_FORCE',
            '--enable', 'MODULE_SIG',
            '--enable', 'MODULE_SIG_SHA512',
            '--enable', 'KEXEC_SIG',
            '--disable', 'DEBUG_INFO_BTF',
            '--disable', 'DEBUG_INFO_DWARF4',
            '--disable', 'DEBUG_INFO_DWARF5',
            '--disable', 'DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT',
            '--enable', 'DEBUG_INFO_NONE',
            '--disable', 'WERROR',
            '--disable', 'DRM_WERROR',
            '--disable', 'RUST',
            '--disable', 'INTEL_TDX_HOST',
            '--disable', 'KVM_INTEL_TDX',
        ]
        self._run_cmd(config_sanitize_cmd, cwd=kernel_dir, progress_callback=None)

        # Check whether building with Clang/LLVM or GCC
        use_llvm = False
        if os.path.exists(config_dst):
            try:
                with open(config_dst, 'r') as cf:
                    cfg_text = cf.read()
                    if 'CONFIG_LTO_CLANG_THIN=y' in cfg_text or 'CONFIG_LTO_CLANG_FULL=y' in cfg_text:
                        use_llvm = True
            except Exception:
                pass

        if not use_llvm:
            # If building with GCC, ensure Clang LTO is disabled first
            self._run_cmd(['scripts/config', '--disable', 'LTO_CLANG_THIN', '--enable', 'LTO_NONE'], cwd=kernel_dir, progress_callback=None)

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
                "-e", "DEBFULLNAME=CachyOS Debian Builder",
                "-e", "DEBEMAIL=builder@localhost",
                "-e", "KBUILD_BUILD_USER=cachyos",
                "-e", "KBUILD_BUILD_HOST=debian",
                "-e", "DPKG_FLAGS=-d -uc -us",
                self.container_image_tag
            ]

        # 4. Hardware Optimization (Compile for my system) or Generic Debian branding
        if optimize_for_system:
            hw = self.detect_hardware()
            if progress_callback:
                progress_callback("\n=======================================================")
                progress_callback("[*] 'Compile for My System' Hardware Auto-Detection:")
                progress_callback(f"    • CPU: {hw['cpu_model']} ({hw['threads']} threads)")
                progress_callback(f"    • Vendor: {hw['vendor']} | Chassis: {'Laptop (Battery)' if hw['is_laptop'] else 'Desktop/Workstation'}")
                if hw['manufacturer'] != 'Generic':
                    progress_callback(f"    • Machine: {hw['manufacturer']} {hw['product_name']}")
                progress_callback(f"    • Root Filesystem: {hw['root_fs']}")
                progress_callback(f"    • Active Modules: {len(hw['loaded_modules'])} loaded hardware drivers detected")
                progress_callback("=======================================================\n")

            # Snapshot host lsmod into download_dir for streamline_config / localmodconfig
            lsmod_host_file = os.path.join(self.download_dir, "host_lsmod.txt")
            try:
                lsmod_raw = subprocess.check_output(['lsmod'], text=True)
                with open(lsmod_host_file, "w") as f:
                    f.write(lsmod_raw)
            except Exception as e:
                if progress_callback:
                    progress_callback(f"[!] Warning: failed to export host lsmod: {e}")

            if progress_callback:
                progress_callback("[*] Applying 'make localmodconfig' (stripping unneeded hardware drivers)...")

            try:
                if use_container:
                    self._run_cmd(
                        container_prefix + ['sh', '-c', 'make localmodconfig LSMOD=/workspace/host_lsmod.txt < /dev/null'],
                        cwd=kernel_dir,
                        progress_callback=progress_callback
                    )
                else:
                    self._run_cmd(
                        ['sh', '-c', f'make localmodconfig LSMOD={lsmod_host_file} < /dev/null'],
                        cwd=kernel_dir,
                        progress_callback=progress_callback
                    )
                if progress_callback:
                    progress_callback("[✓] Unused hardware drivers successfully trimmed!")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"[!] Warning: localmodconfig encountered non-fatal note: {e}")

            if progress_callback:
                progress_callback("[*] Enforcing hardware safety baselines & CPU native instructions...")

            safeties = [
                # Essential filesystems
                ('enable', 'CONFIG_EXT4_FS'),
                ('module', 'CONFIG_BTRFS_FS'),
                ('enable', 'CONFIG_VFAT_FS'),
                ('enable', 'CONFIG_FAT_FS'),
                ('module', 'CONFIG_EXFAT_FS'),
                ('module', 'CONFIG_NTFS3_FS'),
                # Essential storage
                ('enable', 'CONFIG_BLK_DEV_SD'),
                ('enable', 'CONFIG_BLK_DEV_NVME'),
                ('enable', 'CONFIG_NVME_CORE'),
                ('enable', 'CONFIG_ATA'),
                ('enable', 'CONFIG_SATA_AHCI'),
                ('enable', 'CONFIG_USB_STORAGE'),
                ('module', 'CONFIG_USB_UAS'),
                # Essential input
                ('enable', 'CONFIG_HID'),
                ('enable', 'CONFIG_HID_GENERIC'),
                ('enable', 'CONFIG_USB_HID'),
                # Native CPU instruction set (-march=native)
                ('enable', 'CONFIG_X86_NATIVE_CPU'),
                ('disable', 'CONFIG_MGENERIC_CPU'),
            ]

            # CPU Vendor tuning
            if 'intel' in hw['vendor'].lower():
                safeties.extend([
                    ('enable', 'CONFIG_X86_INTEL_PSTATE'),
                    ('enable', 'CONFIG_INTEL_IDLE'),
                    ('enable', 'CONFIG_MNATIVE_INTEL'),
                ])
            elif 'amd' in hw['vendor'].lower():
                safeties.extend([
                    ('enable', 'CONFIG_X86_AMD_PSTATE'),
                    ('enable', 'CONFIG_MNATIVE_AMD'),
                ])

            # Laptop / Chassis tuning
            if hw['is_laptop']:
                safeties.extend([
                    ('enable', 'CONFIG_CPU_FREQ_GOV_POWERSAVE'),
                    ('enable', 'CONFIG_NO_HZ_IDLE'),
                ])

            # Manufacturer-specific ACPI modules
            mfg = hw['manufacturer'].lower()
            if 'lenovo' in mfg or 'thinkpad' in hw['product_name'].lower():
                safeties.append(('module', 'CONFIG_THINKPAD_ACPI'))
            elif 'dell' in mfg:
                safeties.append(('module', 'CONFIG_DELL_WMI'))
            elif 'asus' in mfg:
                safeties.append(('module', 'CONFIG_ASUS_WMI'))

            for action, opt in safeties:
                flag = f'--{action}'
                self._run_cmd(['scripts/config', flag, opt], cwd=kernel_dir, progress_callback=None)

            # Cap NR_CPUS reasonably instead of 8192
            nr_cpus = max(16, min(128, hw['threads'] * 2))
            self._run_cmd(['scripts/config', '--set-val', 'CONFIG_NR_CPUS', str(nr_cpus)], cwd=kernel_dir, progress_callback=None)

            # Localversion with native branding
            self._run_cmd(['scripts/config', '--set-str', 'CONFIG_LOCALVERSION', '-cachyos-native-debian'], cwd=kernel_dir, progress_callback=None)

            if progress_callback:
                progress_callback(f"[✓] System profile tuned: NR_CPUS={nr_cpus}, -march=native enabled, localversion=-cachyos-native-debian")
        else:
            # Standard generic Debian branding
            self._run_cmd(['scripts/config', '--set-str', 'CONFIG_LOCALVERSION', '-cachyos-debian'], cwd=kernel_dir, progress_callback=None)

        # 5. Update configuration for the new kernel version non-interactively
        toolchain_flags = ['LLVM=1', 'LLVM_IAS=1'] if use_llvm else []
        olddef_cmd = ['make'] + toolchain_flags + ['olddefconfig']
        if use_container:
            self._run_cmd(container_prefix + olddef_cmd, cwd=kernel_dir, progress_callback=progress_callback)
        else:
            self._run_cmd(olddef_cmd, cwd=kernel_dir, progress_callback=progress_callback)

        # 6. Save the generated configuration to persistent storage for future updates
        try:
            target_saved_cfg = self.saved_native_config_path if optimize_for_system else self.saved_config_path
            os.makedirs(os.path.dirname(target_saved_cfg), exist_ok=True)
            shutil.copy(config_dst, target_saved_cfg)
            if progress_callback:
                progress_callback(f"[✓] Preserved updated kernel configuration in {target_saved_cfg}")
        except Exception as e:
            if progress_callback:
                progress_callback(f"[!] Warning: could not save configuration: {e}")

        # 7. Clean stale packaging state (Step 4.1: removes leftover debian/ directory)
        debian_pkg_dir = os.path.join(kernel_dir, "debian")
        if os.path.exists(debian_pkg_dir):
            if progress_callback:
                progress_callback("[*] Cleaning stale debian/ packaging directory before build...")
            try:
                shutil.rmtree(debian_pkg_dir, ignore_errors=True)
            except Exception as e:
                if progress_callback:
                    progress_callback(f"[!] Warning: could not remove debian directory: {e}")

        # 8. Packaging environment variables (Step 4.2)
        packaging_env = {
            'DEBFULLNAME': 'CachyOS Debian Builder',
            'DEBEMAIL': 'builder@localhost',
            'KBUILD_BUILD_USER': 'cachyos',
            'KBUILD_BUILD_HOST': 'debian',
            'DPKG_FLAGS': '-d -uc -us',
        }

        cores = str(os.cpu_count() or 4)
        if progress_callback:
            mode_desc = f"inside Debian container ({self.get_container_engine()})" if use_container else "on host system"
            tc_desc = " (Clang/LLVM)" if use_llvm else " (GCC)"
            progress_callback(f"Starting kernel compilation {mode_desc}{tc_desc} using {cores} CPU threads...")
            progress_callback("Running 'make bindeb-pkg' (Debian package build)...")

        bindeb_cmd = ['make', f'-j{cores}'] + toolchain_flags + ['bindeb-pkg', 'DPKG_FLAGS=-d -uc -us']

        try:
            # Compile and generate .deb packages
            if use_container:
                self._run_cmd(container_prefix + bindeb_cmd, cwd=kernel_dir, progress_callback=progress_callback)
            else:
                self._run_cmd(bindeb_cmd, cwd=kernel_dir, progress_callback=progress_callback, env=packaging_env)
        finally:
            # Clean up active build lockfile
            lock_file = os.path.join(self.download_dir, ".building")
            if os.path.exists(lock_file):
                try:
                    os.unlink(lock_file)
                except Exception:
                    pass

        # 7. Collect all generated deb packages and save to ~/kernel-build-deb/Linux-kernel-CachyOS-(version)-[native-]debian
        output_dir = self.get_output_kernel_dir(is_native=optimize_for_system)
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
            kernel_brand = f"Linux-kernel-CachyOS-{ver}-{'native-' if optimize_for_system else ''}debian"
            with open(install_script_path, "w") as sf:
                sf.write(f"""#!/usr/bin/env bash
# CachyOS Kernel Debian Package Installer
# Kernel: {kernel_brand}
set -e

DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" >/dev/null 2>&1 && pwd)"
echo "=== Installing {kernel_brand} ==="
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
        output_dir_native = self.get_output_kernel_dir(is_native=True)
        if os.path.isdir(output_dir_native) and output_dir_native not in search_dirs:
            search_dirs.append(output_dir_native)
        output_dir_generic = self.get_output_kernel_dir(is_native=False)
        if os.path.isdir(output_dir_generic) and output_dir_generic not in search_dirs:
            search_dirs.append(output_dir_generic)
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

    def get_secure_boot_status(self) -> bool:
        """
        Checks if UEFI Secure Boot is active on the system.
        Returns True if 'SecureBoot enabled' is reported by mokutil, False otherwise.
        """
        try:
            res = subprocess.run(
                ['mokutil', '--sb-state'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            out = (res.stdout + res.stderr).lower()
            return 'secureboot enabled' in out
        except Exception:
            return False

    def ensure_mok_keys(self, key_dir="~/.config/cachy-kernel-updater/mok") -> dict:
        """
        Ensures persistent MOK keypair exists. Checks key_dir, /var/lib/shim-signed/mok/,
        or creates a new RSA-2048 X.509 keypair valid for 10 years (3650 days).
        Returns a dict: {'priv': path, 'pem': path, 'der': path}.
        """
        expanded_dir = os.path.expanduser(key_dir)
        priv_path = os.path.join(expanded_dir, "MOK.priv")
        pem_path = os.path.join(expanded_dir, "MOK.pem")
        der_path = os.path.join(expanded_dir, "MOK.der")

        # 1. Check specified key_dir
        if os.path.isfile(priv_path) and (os.path.isfile(pem_path) or os.path.isfile(der_path)):
            if not os.path.isfile(pem_path) and os.path.isfile(der_path):
                subprocess.run(['openssl', 'x509', '-inform', 'DER', '-in', der_path, '-out', pem_path], check=True)
            elif not os.path.isfile(der_path) and os.path.isfile(pem_path):
                subprocess.run(['openssl', 'x509', '-in', pem_path, '-outform', 'DER', '-out', der_path], check=True)
            return {"priv": priv_path, "pem": pem_path, "der": der_path}

        # 2. Check /var/lib/shim-signed/mok/
        shim_dir = "/var/lib/shim-signed/mok"
        s_priv = os.path.join(shim_dir, "MOK.priv")
        s_pem = os.path.join(shim_dir, "MOK.pem")
        s_der = os.path.join(shim_dir, "MOK.der")
        if os.path.isfile(s_priv) and os.path.isfile(s_pem) and os.access(s_priv, os.R_OK):
            if not os.path.isfile(s_der):
                try:
                    subprocess.run(['openssl', 'x509', '-in', s_pem, '-outform', 'DER', '-out', s_der], check=True)
                except Exception:
                    pass
            if os.path.isfile(s_der):
                return {"priv": s_priv, "pem": s_pem, "der": s_der}

        # 3. Create key_dir and generate new RSA-2048 X.509 keypair
        os.makedirs(expanded_dir, exist_ok=True)
        os.chmod(expanded_dir, 0o700)

        cmd_req = [
            'openssl', 'req', '-new', '-x509', '-newkey', 'rsa:2048', '-nodes',
            '-days', '3650', '-outform', 'DER',
            '-keyout', priv_path, '-out', der_path,
            '-subj', '/CN=CachyOS Debian User Signing Key/'
        ]
        subprocess.run(cmd_req, check=True)

        cmd_pem = ['openssl', 'x509', '-inform', 'DER', '-in', der_path, '-out', pem_path]
        subprocess.run(cmd_pem, check=True)

        os.chmod(priv_path, 0o600)
        os.chmod(pem_path, 0o644)
        os.chmod(der_path, 0o644)

        return {"priv": priv_path, "pem": pem_path, "der": der_path}

    def is_mok_enrolled(self, der_path: str) -> bool:
        """
        Runs 'mokutil --test-key <der_path>' to check if this MOK certificate
        is already enrolled in the UEFI database.
        Returns True if enrolled, False otherwise.
        """
        if not os.path.exists(der_path):
            return False
        try:
            res = subprocess.run(
                ['mokutil', '--test-key', der_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            output = (res.stdout + res.stderr).lower()
            return 'is enrolled' in output and 'not enrolled' not in output
        except Exception:
            return False

    def enroll_mok_key_gui(self, der_path: str, password: str) -> tuple:
        """
        Imports the MOK certificate into mokutil using pkexec and pipes the one-time enrollment password.
        Returns (True, message) on success, or (False, error_message).
        """
        if not os.path.exists(der_path):
            return False, f"Certificate file not found: {der_path}"

        if len(password) < 8 or len(password) > 16:
            return False, "Enrollment password must be between 8 and 16 characters."

        cmd = ['pkexec', 'mokutil', '--import', der_path]
        try:
            proc = subprocess.run(
                cmd,
                input=f"{password}\n{password}\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30
            )
            if proc.returncode == 0:
                return True, (
                    "MOK key import request successfully submitted to UEFI!\n\n"
                    "Next Reboot Action Required:\n"
                    "1. When your computer restarts, the blue 'MOKManagement' screen will appear.\n"
                    "2. Select 'Enroll MOK' -> 'Continue' -> 'Yes'.\n"
                    "3. Enter the one-time password you just created.\n"
                    "Your custom CachyOS kernel will then boot securely."
                )
            else:
                err = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
                return False, f"Failed to register MOK key: {err}"
        except Exception as e:
            return False, f"Failed to execute mokutil via pkexec: {e}"

    def sign_built_deb_packages(self, deb_dir: str, log_callback=None) -> bool:
        """
        Extracts each linux-image-*.deb in deb_dir using fakeroot, signs /boot/vmlinuz-* with MOK,
        verifies the signature with sbverify, and repacks the .deb in-place.
        """
        import glob
        if not os.path.isdir(deb_dir):
            if log_callback:
                log_callback(f"[!] Directory not found: {deb_dir}")
            return False

        for tool in ['sbsign', 'sbverify', 'fakeroot', 'dpkg-deb']:
            if not shutil.which(tool):
                msg = f"[!] Required signing tool '{tool}' is missing. Please install sbsigntool and fakeroot."
                if log_callback:
                    log_callback(msg)
                return False

        keys = self.ensure_mok_keys()
        priv = keys["priv"]
        pem = keys["pem"]

        deb_patterns = [os.path.join(deb_dir, "linux-image-*.deb")]
        deb_files = [f for pat in deb_patterns for f in glob.glob(pat) if '-dbg' not in f]

        if not deb_files:
            if log_callback:
                log_callback(f"[!] No linux-image-*.deb packages found to sign in {deb_dir}")
            return False

        if log_callback:
            log_callback(f"\n=======================================================")
            log_callback(f"[*] Starting UEFI Secure Boot signing of .deb packages...")
            log_callback(f"    MOK Key:  {priv}")
            log_callback(f"    MOK Cert: {pem}")
            log_callback(f"=======================================================\n")

        signed_count = 0
        tmp_extract_dir = os.path.join(deb_dir, ".tmp_sign_extract")

        for deb in deb_files:
            fname = os.path.basename(deb)
            if log_callback:
                log_callback(f"[*] Processing package: {fname}...")

            if os.path.exists(tmp_extract_dir):
                shutil.rmtree(tmp_extract_dir, ignore_errors=True)
            os.makedirs(tmp_extract_dir, exist_ok=True)

            try:
                # 1. Extract package preserving permissions
                if log_callback:
                    log_callback(f"    • Unpacking payload with fakeroot dpkg-deb -R...")
                res = subprocess.run(
                    ['fakeroot', 'dpkg-deb', '-R', deb, tmp_extract_dir],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if res.returncode != 0:
                    raise Exception(f"Unpacking failed: {res.stderr.strip() or res.stdout.strip()}")

                # 2. Locate kernel binary inside boot/
                boot_dir = os.path.join(tmp_extract_dir, "boot")
                vmlinuz_candidates = glob.glob(os.path.join(boot_dir, "vmlinuz-*"))
                if not vmlinuz_candidates:
                    if log_callback:
                        log_callback(f"    [!] Notice: No /boot/vmlinuz-* found in {fname}; skipping.")
                    continue

                for vmlinuz in vmlinuz_candidates:
                    if vmlinuz.endswith(".signed"):
                        continue
                    v_base = os.path.basename(vmlinuz)
                    if log_callback:
                        log_callback(f"    • Signing kernel binary {v_base} with sbsign...")

                    signed_file = f"{vmlinuz}.signed"
                    s_res = subprocess.run(
                        ['sbsign', '--key', priv, '--cert', pem, '--output', signed_file, vmlinuz],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    if s_res.returncode != 0:
                        raise Exception(f"sbsign failed for {v_base}: {s_res.stderr.strip() or s_res.stdout.strip()}")

                    os.replace(signed_file, vmlinuz)

                    # 3. Verify signature with sbverify
                    v_res = subprocess.run(
                        ['sbverify', '--list', vmlinuz],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    if log_callback:
                        log_callback(f"    • Signature verified: {v_base} is cryptographically signed.")

                # 4. Repack package
                if log_callback:
                    log_callback(f"    • Repacking signed package with fakeroot dpkg-deb -b...")
                repack_res = subprocess.run(
                    ['fakeroot', 'dpkg-deb', '-b', tmp_extract_dir, deb],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if repack_res.returncode != 0:
                    raise Exception(f"Repacking failed: {repack_res.stderr.strip() or repack_res.stdout.strip()}")

                signed_count += 1
                if log_callback:
                    log_callback(f"    [✓] Successfully signed and repacked {fname}!\n")

            except Exception as e:
                if log_callback:
                    log_callback(f"    [!] Error signing package {fname}: {e}")
                return False
            finally:
                if os.path.exists(tmp_extract_dir):
                    shutil.rmtree(tmp_extract_dir, ignore_errors=True)

        if log_callback:
            log_callback(f"[✓] Secure Boot MOK signing completed for {signed_count} .deb package(s)!\n")
        return True

    def sign_installed_boot_kernel(self, kernel_version: str = None, log_callback=None) -> bool:
        """
        Signs /boot/vmlinuz-<kernel_version> directly on the host using pkexec sbsign and updates initramfs.
        """
        keys = self.ensure_mok_keys()
        priv = keys["priv"]
        pem = keys["pem"]

        if not kernel_version:
            import glob
            cachy_kernels = glob.glob("/boot/vmlinuz-*cachyos*")
            if cachy_kernels:
                cachy_kernels.sort(key=os.path.getmtime, reverse=True)
                target_vmlinuz = cachy_kernels[0]
            else:
                current = self.get_current_kernel_version()
                target_vmlinuz = f"/boot/vmlinuz-{current}"
        else:
            if kernel_version.startswith("/boot/"):
                target_vmlinuz = kernel_version
            elif kernel_version.startswith("vmlinuz-"):
                target_vmlinuz = f"/boot/{kernel_version}"
            else:
                target_vmlinuz = f"/boot/vmlinuz-{kernel_version}"

        if not os.path.isfile(target_vmlinuz):
            if log_callback:
                log_callback(f"[-] Target kernel binary not found: {target_vmlinuz}")
            return False

        kver = os.path.basename(target_vmlinuz).replace("vmlinuz-", "")

        if log_callback:
            log_callback(f"[*] Signing {target_vmlinuz} via pkexec sbsign...")

        cmd_sign = ['pkexec', 'sbsign', '--key', priv, '--cert', pem, '--output', target_vmlinuz, target_vmlinuz]
        res = subprocess.run(cmd_sign, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            if log_callback:
                log_callback(f"[!] pkexec sbsign failed: {res.stderr.strip() or res.stdout.strip()}")
            return False

        if log_callback:
            log_callback(f"[✓] Kernel {target_vmlinuz} signed. Updating initramfs via pkexec update-initramfs...")

        cmd_initrd = ['pkexec', 'update-initramfs', '-u', '-k', kver]
        subprocess.run(cmd_initrd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if log_callback:
            log_callback(f"[✓] Initramfs updated for {kver}. Kernel is ready for Secure Boot!")
        return True

    def sign_kernel_secureboot(self, kernel_version=None, progress_callback=None):
        """Signs the installed kernel in /boot using MOK for UEFI Secure Boot."""
        return self.sign_installed_boot_kernel(kernel_version=kernel_version, log_callback=progress_callback)

    def sign_deb_packages(self, deb_dir=None, gpg_key_id=None, progress_callback=None):
        """Signs the compiled .deb packages using GPG."""
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "sign-kernel.sh"),
            "/usr/share/cachy-kernel-updater/sign-kernel.sh",
            os.path.expanduser("~/Projects/debian-cachy-kernel-updater/sign-kernel.sh")
        ]
        script_path = None
        for p in candidates:
            if os.path.isfile(p):
                script_path = p
                break
        if not script_path:
            raise Exception("sign-kernel.sh script not found. Please ensure sign-kernel.sh exists in application directory.")

        target_dir = deb_dir or self.last_output_dir
        if not target_dir or not os.path.isdir(target_dir):
            for candidate in [self.get_output_kernel_dir(is_native=True), self.get_output_kernel_dir(is_native=False)]:
                if os.path.isdir(candidate):
                    target_dir = candidate
                    break

        if not target_dir or not os.path.isdir(target_dir):
            raise Exception("Debian packages directory not found. Please compile the kernel first.")

        cmd = [script_path, "--debs", target_dir]
        if gpg_key_id:
            cmd.append(gpg_key_id)

        if progress_callback:
            progress_callback("\n=======================================================")
            progress_callback(f"[*] Initiating .deb GPG package signing for: {target_dir}")
            progress_callback("=======================================================\n")
        self._run_cmd(cmd, progress_callback=progress_callback)
        return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Debian CachyOS Kernel Manager CLI")
    parser.add_argument('--check', action='store_true', help="Check for latest CachyOS kernel version")
    parser.add_argument('--status-sb', action='store_true', help="Check UEFI Secure Boot status")
    parser.add_argument('--install-deps', action='store_true', help="Install required build dependencies")
    parser.add_argument('--container', action='store_true', help="Use container environment (Podman/Docker)")
    parser.add_argument('--optimize', action='store_true', help="Optimize kernel compilation for local system (-march=native)")
    parser.add_argument('--build', action='store_true', help="Download and compile the latest CachyOS kernel")
    parser.add_argument('--install', action='store_true', help="Install compiled Debian packages")
    parser.add_argument('--rollback', nargs='?', const='', help="Purge/rollback an installed kernel package")
    parser.add_argument('--sign-mok', nargs='?', const='', help="Sign kernel for UEFI Secure Boot (MOK)")
    parser.add_argument('--sign-deb-mok', metavar='DIR', nargs='?', const='', help="Sign kernel inside built .deb packages with MOK")
    parser.add_argument('--enroll-mok', action='store_true', help="Enroll MOK key into UEFI")
    parser.add_argument('--sign-debs', nargs='?', const='', help="Sign .deb packages with GPG (specify folder or default)")
    parser.add_argument('--gpg-key', help="GPG Key ID for signing .deb packages")

    args = parser.parse_args()
    km = KernelManager()

    def cli_log(msg):
        print(msg)

    if args.check:
        print(f"Current kernel: {km.get_current_kernel_version()}")
        print(f"Latest CachyOS: {km.get_latest_cachy_version()}")
        print(f"Running latest: {km.is_matching_running_kernel()}")
    elif args.status_sb:
        sb = km.get_secure_boot_status()
        print(f"UEFI Secure Boot: {'ENABLED' if sb else 'DISABLED'}")
    elif args.install_deps:
        km.install_build_dependencies(progress_callback=cli_log, use_container=args.container)
    elif args.build:
        src = km.download_kernel(progress_callback=cli_log)
        km.compile_kernel(src, progress_callback=cli_log, use_container=args.container, optimize_for_system=args.optimize)
    elif args.install:
        km.install_kernel(progress_callback=cli_log)
    elif args.rollback is not None:
        if args.rollback:
            km.remove_kernel(args.rollback, progress_callback=cli_log)
        else:
            print("Installed kernels:", km.get_installed_kernels())
    elif args.sign_deb_mok is not None:
        target_dir = args.sign_deb_mok or km.last_output_dir or km.get_output_kernel_dir()
        km.sign_built_deb_packages(target_dir, log_callback=cli_log)
    elif args.enroll_mok:
        keys = km.ensure_mok_keys()
        der_path = keys["der"]
        import getpass
        pwd = getpass.getpass("Enter one-time MOK enrollment password (8-16 chars): ")
        success, msg = km.enroll_mok_key_gui(der_path, pwd)
        print(msg)
    elif args.sign_mok is not None:
        km.sign_kernel_secureboot(kernel_version=args.sign_mok or None, progress_callback=cli_log)
    elif args.sign_debs is not None:
        km.sign_deb_packages(deb_dir=args.sign_debs or None, gpg_key_id=args.gpg_key, progress_callback=cli_log)
    else:
        parser.print_help()
