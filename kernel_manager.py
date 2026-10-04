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
        cache_base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        self.download_dir = os.path.join(cache_base, "cachy-kernel-build")
        self.latest_version = None
        self.latest_tag = None
        self.download_url = None

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

    def _run_cmd(self, cmd, cwd, progress_callback):
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

    def download_kernel(self, progress_callback=None):
        """Downloads the official pre-patched CachyOS kernel source and configuration."""
        if not self.latest_version or not self.download_url:
            self.get_latest_cachy_version()

        if not self.download_url:
            raise Exception("Unable to find download URL for latest CachyOS kernel.")

        os.makedirs(self.download_dir, exist_ok=True)
        archive_name = f"{self.latest_tag}.tar.gz"
        archive_path = os.path.join(self.download_dir, archive_name)

        if progress_callback:
            progress_callback(f"Target: CachyOS Kernel {self.latest_version}")
            progress_callback(f"Downloading from {self.download_url}...")

        # Download tarball with progress indication
        if not os.path.exists(archive_path) or os.path.getsize(archive_path) < 1000000:
            def report_hook(block_num, block_size, total_size):
                if total_size > 0 and block_num % 1000 == 0:
                    downloaded = block_num * block_size
                    percent = min(100, int(downloaded * 100 / total_size))
                    mb_down = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    if progress_callback:
                        progress_callback(f"Downloading: {percent}% ({mb_down:.1f} MB / {mb_total:.1f} MB)")

            urllib.request.urlretrieve(self.download_url, archive_path, reporthook=report_hook)

        if progress_callback:
            progress_callback(f"Extracting {archive_name}...")

        # Extract kernel source
        self._run_cmd(['tar', '-xf', archive_path], cwd=self.download_dir, progress_callback=progress_callback)

        # Download official CachyOS config
        if progress_callback:
            progress_callback("Fetching official CachyOS kernel config...")
        config_path = os.path.join(self.download_dir, "config")
        urllib.request.urlretrieve(self.cachy_config_raw, config_path)

        extracted_dir = os.path.join(self.download_dir, self.latest_tag)
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
            progress_callback(f"Kernel source ready in {extracted_dir}")

        return extracted_dir

    def compile_kernel(self, kernel_dir, progress_callback=None):
        """Prepares configuration and compiles the kernel into Debian packages."""
        if progress_callback:
            progress_callback("Setting up kernel configuration for Debian...")

        # Copy official CachyOS config to .config
        config_src = os.path.join(self.download_dir, "config")
        config_dst = os.path.join(kernel_dir, ".config")
        shutil.copy(config_src, config_dst)

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

        # 3. Update configuration
        self._run_cmd(['make', 'olddefconfig'], cwd=kernel_dir, progress_callback=progress_callback)

        cores = str(os.cpu_count() or 4)
        if progress_callback:
            progress_callback(f"Starting kernel compilation using {cores} CPU threads...")
            progress_callback("Running 'make bindeb-pkg' (Debian package build)...")

        # Compile and generate .deb packages
        self._run_cmd(['make', f'-j{cores}', 'bindeb-pkg'], cwd=kernel_dir, progress_callback=progress_callback)

        if progress_callback:
            progress_callback("Compilation completed successfully! Debian packages (.deb) are ready.")

    def install_kernel(self, progress_callback=None):
        """Installs the compiled .deb packages using pkexec."""
        import glob
        
        deb_files = glob.glob(os.path.join(self.download_dir, "linux-image-*.deb"))
        deb_files += glob.glob(os.path.join(self.download_dir, "linux-headers-*.deb"))
        
        # Exclude debug symbols debs if any were generated
        deb_files = [f for f in deb_files if '-dbg' not in f]

        if not deb_files:
            if progress_callback:
                progress_callback("Error: No linux-image or linux-headers .deb files found in build directory.")
            return False

        if progress_callback:
            progress_callback(f"Found packages: {[os.path.basename(f) for f in deb_files]}")
            progress_callback("Requesting root permissions via pkexec to install packages...")

        cmd = ['pkexec', 'dpkg', '-i'] + deb_files
        try:
            self._run_cmd(cmd, cwd=self.download_dir, progress_callback=progress_callback)
            if progress_callback:
                progress_callback("Installation successful! Updating GRUB...")
            # Ensure grub is updated
            try:
                self._run_cmd(['pkexec', 'update-grub'], cwd=self.download_dir, progress_callback=progress_callback)
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
