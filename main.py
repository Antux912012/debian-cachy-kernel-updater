import sys
import os
import subprocess
import threading
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk, Gio

from kernel_manager import KernelManager

class KernelUpdaterWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Debian CachyOS Kernel Updater")
        self.set_default_size(800, 640)
        self.set_decorated(True)
        self.set_resizable(True)
        
        # Ensure window decoration layout displays minimize, maximize, and close buttons
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-decoration-layout", ":minimize,maximize,close")

        # Configure icon theme search paths to guarantee symbolic window controls are found
        display = Gdk.Display.get_default()
        if display:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            appdir = os.environ.get("APPDIR")
            if appdir:
                icon_theme.add_search_path(os.path.join(appdir, "usr/share/icons"))
                icon_theme.add_search_path(os.path.join(appdir, "usr/share/pixmaps"))
            icon_theme.add_search_path("/usr/share/icons")
            icon_theme.add_search_path("/usr/local/share/icons")
            icon_theme.add_search_path(os.path.expanduser("~/.local/share/icons"))

        self.kernel_manager = KernelManager()

        # Header Bar with explicit title buttons
        self.header = Adw.HeaderBar()
        self.header.set_show_start_title_buttons(True)
        self.header.set_show_end_title_buttons(True)
        
        self.set_icon_name("org.cachyos.debian.kernelupdater")
        self.window_title = Adw.WindowTitle(
            title="Debian CachyOS Kernel Updater",
            subtitle="Installer, Updater & Rollback (v1.0.7)"
        )
        self.header.set_title_widget(self.window_title)

        # Content Box
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.content_box.set_margin_top(16)
        self.content_box.set_margin_bottom(16)
        self.content_box.set_margin_start(20)
        self.content_box.set_margin_end(20)

        # Main Layout using Adw.ToolbarView if available, fallback to Gtk.Box for older Libadwaita
        if hasattr(Adw, "ToolbarView"):
            self.toolbar_view = Adw.ToolbarView()
            self.set_content(self.toolbar_view)
            self.toolbar_view.add_top_bar(self.header)
            self.toolbar_view.set_content(self.content_box)
        else:
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            main_box.append(self.header)
            main_box.append(self.content_box)
            self.set_content(main_box)

        # Status Cards / Banner Box
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.status_box.add_css_class("card")
        self.status_box.set_margin_bottom(6)
        self.status_box.set_margin_top(4)

        inner_status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner_status_box.set_margin_top(12)
        inner_status_box.set_margin_bottom(12)
        inner_status_box.set_margin_start(16)
        inner_status_box.set_margin_end(16)

        current_kernel = self.kernel_manager.get_current_kernel_version()
        self.status_label = Gtk.Label(label=f"Current Kernel: {current_kernel}", halign=Gtk.Align.START)
        self.status_label.add_css_class("title-3")
        inner_status_box.append(self.status_label)

        self.latest_label = Gtk.Label(label="Latest CachyOS Kernel: Checking official GitHub...", halign=Gtk.Align.START)
        self.latest_label.add_css_class("body")
        inner_status_box.append(self.latest_label)

        self.match_status_label = Gtk.Label(label="", halign=Gtk.Align.START)
        self.match_status_label.add_css_class("caption")
        inner_status_box.append(self.match_status_label)

        self.status_box.append(inner_status_box)
        self.content_box.append(self.status_box)

        # Build Options Group (Container, Hardware Optimization & Output Location)
        self.options_group = Adw.PreferencesGroup()
        self.options_group.set_title("Build & Output Settings")

        self.container_row = Adw.SwitchRow()
        self.container_row.set_title("Build inside Container (Podman/Docker)")

        engine = self.kernel_manager.get_container_engine()
        if engine:
            self.container_row.set_subtitle(f"Detected engine: {engine.capitalize()} (Debian Bookworm isolated environment)")
            self.container_row.set_active(True)
        else:
            self.container_row.set_subtitle("Podman will be installed as a dependency (Debian Bookworm isolated environment)")
            self.container_row.set_active(True)

        self.container_row.connect("notify::active", self.on_container_toggled)
        self.options_group.add(self.container_row)

        self.system_opt_row = Adw.SwitchRow()
        self.system_opt_row.set_title("Compile for my system (Experimental)")
        self.system_opt_row.set_subtitle("Auto-detect CPU & hardware: native instructions (-march=native) & tailored drivers")
        self.system_opt_row.set_active(False)
        self.system_opt_row.connect("notify::active", self.on_system_opt_toggled)
        self.options_group.add(self.system_opt_row)

        self.is_secure_boot = self.kernel_manager.get_secure_boot_status()
        self.auto_sign_row = Adw.SwitchRow()
        self.auto_sign_row.set_title("Auto-sign built kernel packages (UEFI MOK)")
        if self.is_secure_boot:
            self.auto_sign_row.set_subtitle("UEFI Secure Boot: Active (Recommended) • Signs vmlinuz inside .deb with MOK key")
            self.auto_sign_row.set_active(True)
        else:
            self.auto_sign_row.set_subtitle("UEFI Secure Boot: Inactive/Disabled • Signs vmlinuz inside .deb with MOK key")
            self.auto_sign_row.set_active(False)
        self.options_group.add(self.auto_sign_row)

        self.output_row = Adw.ActionRow()
        self.output_row.set_title("Output Package Folder")
        self.output_row.set_subtitle(self.kernel_manager.get_output_kernel_dir(is_native=False))

        self.open_output_button = Gtk.Button(label="Open Folder")
        self.open_output_button.set_valign(Gtk.Align.CENTER)
        self.open_output_button.connect("clicked", self.on_open_output_clicked)
        self.output_row.add_suffix(self.open_output_button)

        self.options_group.add(self.output_row)
        self.content_box.append(self.options_group)

        # Kernel & Package Signing Group (Decoupled Post-Build / Post-Install Actions)
        self.signing_group = Adw.PreferencesGroup()
        self.signing_group.set_title("Kernel & Package Security Signing")
        self.signing_group.set_description("Decoupled signing tools: sign .deb packages, enroll Secure Boot MOK keys, or GPG-sign packages.")

        # Row 1: Sign Built .deb Packages for Secure Boot (MOK)
        self.sign_deb_mok_row = Adw.ActionRow()
        self.sign_deb_mok_row.set_title("Sign .deb Packages for Secure Boot (MOK)")
        self.sign_deb_mok_row.set_subtitle("Unpack linux-image-*.deb, sign /boot/vmlinuz-* with MOK, and repackage")
        self.sign_deb_mok_button = Gtk.Button(label="Sign .debs (MOK)")
        self.sign_deb_mok_button.set_valign(Gtk.Align.CENTER)
        self.sign_deb_mok_button.connect("clicked", self.on_sign_built_debs_clicked)
        self.sign_deb_mok_row.add_suffix(self.sign_deb_mok_button)
        self.signing_group.add(self.sign_deb_mok_row)

        # Row 2: Enroll MOK Key into UEFI NVRAM
        self.enroll_mok_row = Adw.ActionRow()
        self.enroll_mok_row.set_title("Enroll MOK Key into UEFI NVRAM")
        self.enroll_mok_row.set_subtitle("Stage MOK certificate into MokManager for UEFI authorization on reboot")
        self.enroll_mok_button = Gtk.Button(label="Enroll MOK")
        self.enroll_mok_button.set_valign(Gtk.Align.CENTER)
        self.enroll_mok_button.connect("clicked", self.on_enroll_mok_clicked)
        self.enroll_mok_row.add_suffix(self.enroll_mok_button)
        self.signing_group.add(self.enroll_mok_row)

        # Row 3: UEFI Secure Boot Signing (MOK) on installed /boot kernel
        self.sign_mok_row = Adw.ActionRow()
        self.sign_mok_row.set_title("Sign Installed Kernel in /boot (MOK)")
        self.sign_mok_row.set_subtitle("Authorize /boot/vmlinuz-* with Machine Owner Key (MOK) & update initramfs")
        self.sign_mok_button = Gtk.Button(label="Sign /boot")
        self.sign_mok_button.set_valign(Gtk.Align.CENTER)
        self.sign_mok_button.connect("clicked", self.on_sign_mok_clicked)
        self.sign_mok_row.add_suffix(self.sign_mok_button)
        self.signing_group.add(self.sign_mok_row)

        # Row 4: .deb Package GPG Signing
        self.sign_debs_row = Adw.ActionRow()
        self.sign_debs_row.set_title("Sign .deb Packages (GPG)")
        self.sign_debs_row.set_subtitle("Cryptographically sign compiled .deb packages with local GPG key")
        self.sign_debs_button = Gtk.Button(label="Sign (GPG)")
        self.sign_debs_button.set_valign(Gtk.Align.CENTER)
        self.sign_debs_button.connect("clicked", self.on_sign_debs_clicked)
        self.sign_debs_row.add_suffix(self.sign_debs_button)
        self.signing_group.add(self.sign_debs_row)

        self.content_box.append(self.signing_group)

        # Action Buttons Box
        self.button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.button_box.set_halign(Gtk.Align.CENTER)
        self.content_box.append(self.button_box)

        self.check_button = Gtk.Button(label="Check Updates")
        self.check_button.add_css_class("suggested-action")
        self.check_button.connect("clicked", self.on_check_updates_clicked)
        self.button_box.append(self.check_button)

        self.deps_button = Gtk.Button(label="Install Dependencies")
        self.deps_button.connect("clicked", self.on_install_deps_clicked)
        self.button_box.append(self.deps_button)

        self.install_button = Gtk.Button(label="Download & Compile")
        self.install_button.connect("clicked", self.on_install_clicked)
        self.install_button.set_sensitive(False)
        self.button_box.append(self.install_button)

        self.apply_button = Gtk.Button(label="Install (.deb)")
        self.apply_button.connect("clicked", self.on_apply_clicked)
        self.apply_button.set_sensitive(False)
        self.button_box.append(self.apply_button)

        self.sign_wizard_button = Gtk.Button(label="Sign Existing .deb")
        self.sign_wizard_button.connect("clicked", self.on_sign_built_debs_clicked)
        self.button_box.append(self.sign_wizard_button)

        self.rollback_button = Gtk.Button(label="Rollback Kernel")
        self.rollback_button.add_css_class("destructive-action")
        self.rollback_button.connect("clicked", self.on_rollback_clicked)
        self.button_box.append(self.rollback_button)

        # Terminal / Log Output Card
        log_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        log_title = Gtk.Label(label="Process & Compilation Log", halign=Gtk.Align.START)
        log_title.add_css_class("heading")
        log_header_box.append(log_title)
        self.content_box.append(log_header_box)

        self.terminal_view = Gtk.TextView()
        self.terminal_view.set_editable(False)
        self.terminal_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.terminal_view.set_monospace(True)
        self.terminal_view.set_left_margin(12)
        self.terminal_view.set_right_margin(12)
        self.terminal_view.set_top_margin(10)
        self.terminal_view.set_bottom_margin(10)

        # Terminal styling
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            textview text {
                font-family: monospace;
                font-size: 10pt;
                background-color: #1e1e1e;
                color: #dcdcdc;
            }
        """)
        self.terminal_view.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_child(self.terminal_view)
        scrolled_window.set_vexpand(True)
        scrolled_window.add_css_class("card")
        self.content_box.append(scrolled_window)

        # Clean build cache and verify saved config on startup
        self.kernel_manager.cleanup_cache_on_startup(progress_callback=self.log)

        sb_status = "ENABLED (MOK signing recommended)" if self.is_secure_boot else "DISABLED / INACTIVE"
        self.log(f"[i] Host UEFI Secure Boot: {sb_status}")

        # Check build dependencies status on startup (respecting container switch)
        use_container = self.container_row.get_active()
        missing_deps = self.kernel_manager.check_build_dependencies(use_container=use_container)
        if missing_deps:
            self.log(f"[!] Notice: Missing {len(missing_deps)} build dependency item(s): {', '.join(missing_deps)}. Click 'Install Dependencies' to install.")
        else:
            mode = "Container & build" if use_container else "Host compiler"
            self.log(f"[✓] {mode} dependencies are verified and installed.")

        # Automatically check for updates on startup
        self.on_check_updates_clicked(None)

    def log(self, message):
        """Thread-safe logging to the textview."""
        GLib.idle_add(self._log_idle, message)

    def _log_idle(self, message):
        buffer = self.terminal_view.get_buffer()
        end_iter = buffer.get_end_iter()
        buffer.insert(end_iter, message + "\n")
        
        # Auto-scroll to end
        mark = buffer.create_mark(None, buffer.get_end_iter(), False)
        self.terminal_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
        return False

    def on_check_updates_clicked(self, button):
        self.log("[*] Checking official CachyOS GitHub repositories for latest kernel...")
        self.check_button.set_sensitive(False)
        self.latest_label.set_label("Latest CachyOS Kernel: Querying GitHub...")

        def check_task():
            latest = self.kernel_manager.get_latest_cachy_version()
            is_matching = self.kernel_manager.is_matching_running_kernel()
            GLib.idle_add(self._update_version_ui, latest, is_matching)

        threading.Thread(target=check_task, daemon=True).start()

    def _update_version_ui(self, latest, is_matching):
        self.latest_label.set_label(f"Latest CachyOS Kernel: {latest}")
        self.log(f"[✓] Official latest CachyOS kernel version: {latest}")
        is_native = self.system_opt_row.get_active()
        self.output_row.set_subtitle(self.kernel_manager.get_output_kernel_dir(is_native=is_native))

        if is_matching:
            self.match_status_label.set_label("✅ You are currently running the latest CachyOS kernel.")
            self.log("[i] Your running kernel matches the latest CachyOS version.")
        else:
            self.match_status_label.set_label("⚡ A newer or different CachyOS kernel version is available for compilation.")
            self.log("[i] Running kernel does not match the latest CachyOS release.")

        self.check_button.set_sensitive(True)
        self.install_button.set_sensitive(True)
        self.deps_button.set_sensitive(True)
        return False

    def on_open_output_clicked(self, button):
        is_native = self.system_opt_row.get_active()
        out_dir = self.kernel_manager.last_output_dir or self.kernel_manager.get_output_kernel_dir(is_native=is_native)
        if not os.path.exists(out_dir):
            out_dir = self.kernel_manager.output_base_dir
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception:
                pass
        self.log(f"[*] Opening output folder: {out_dir}")
        try:
            subprocess.Popen(['xdg-open', out_dir])
        except Exception as e:
            self.log(f"[!] Could not open folder: {e}")

    def on_container_toggled(self, row, param):
        is_active = self.container_row.get_active()
        engine = self.kernel_manager.get_container_engine()
        if is_active:
            if engine:
                self.container_row.set_subtitle(f"Detected engine: {engine.capitalize()} (Debian Bookworm isolated environment)")
            else:
                self.container_row.set_subtitle("Podman will be installed as a dependency (Debian Bookworm isolated environment)")
            self.log("[i] Container build enabled. Container dependencies will be included.")
        else:
            self.container_row.set_subtitle("Disabled (building directly on host system)")
            self.log("[i] Container build disabled. Host compiler dependencies will be used.")

        # Re-check dependencies dynamically for the newly selected mode
        missing = self.kernel_manager.check_build_dependencies(use_container=is_active)
        if missing:
            self.log(f"[!] Notice: Missing {len(missing)} dependency item(s): {', '.join(missing)}. Click 'Install Dependencies' to install.")
        else:
            mode = "Container & build" if is_active else "Host compiler"
            self.log(f"[✓] {mode} dependencies are verified and installed.")

    def on_system_opt_toggled(self, row, param):
        is_active = self.system_opt_row.get_active()
        if is_active:
            hw = self.kernel_manager.detect_hardware()
            mfg_str = f" • {hw['manufacturer']}" if hw['manufacturer'] != 'Generic' else ""
            self.system_opt_row.set_subtitle(
                f"Active: {hw['cpu_model']} ({hw['threads']}T){mfg_str} • Native instructions & local drivers"
            )
            self.log("\n=======================================================")
            self.log("[*] 'Compile for my system' mode activated!")
            self.log(f"    • Detected CPU: {hw['cpu_model']} ({hw['threads']} threads)")
            self.log(f"    • CPU Vendor: {hw['vendor']} | Chassis: {'Laptop (Battery)' if hw['is_laptop'] else 'Desktop'}")
            if hw['manufacturer'] != 'Generic':
                self.log(f"    • Machine: {hw['manufacturer']} {hw['product_name']}")
            self.log(f"    • Root Filesystem: {hw['root_fs']}")
            self.log(f"    • Active Modules: {len(hw['loaded_modules'])} loaded hardware drivers")
            self.log("    • Profile: Hardware-optimized (-march=native, localmodconfig, localversion=-cachyos-native-debian)")
            self.log("=======================================================\n")
        else:
            self.system_opt_row.set_subtitle(
                "Auto-detect CPU & hardware: native instructions (-march=native) & tailored drivers"
            )
            self.log("[i] 'Compile for my system' disabled: standard generic x86-64 build.")
        self.output_row.set_subtitle(self.kernel_manager.get_output_kernel_dir(is_native=is_active))

    def on_install_deps_clicked(self, button):
        use_container = self.container_row.get_active()
        missing = self.kernel_manager.check_build_dependencies(use_container=use_container)
        if not missing:
            self.log("\n=======================================================")
            if use_container:
                self.log("[✓] All required kernel build dependencies and container environment are already installed:")
                engine = self.kernel_manager.get_container_engine() or "podman"
                self.log(f"    • Container Engine: {engine}")
                self.log(f"    • Container Image: {self.kernel_manager.container_image_tag} (verified)")
            else:
                self.log("[✓] All required host kernel compiler dependencies are already installed:")
            for dep in self.kernel_manager.REQUIRED_BUILD_DEPS:
                self.log(f"    • {dep} (installed)")
            self.log("=======================================================\n")

            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Dependencies Installed",
                body=(
                    "All required dependencies "
                    + ("and container builder image " if use_container else "")
                    + "are already installed on your system.\n\nWould you like to run verification/reinstallation anyway?"
                )
            )
            dialog.add_response("cancel", "Keep Current")
            dialog.add_response("reinstall", "Update / Reinstall")
            dialog.set_response_appearance("reinstall", Adw.ResponseAppearance.SUGGESTED)

            def on_dialog_response(dlg, response):
                if response == "reinstall":
                    self._start_deps_install(use_container=use_container, force_rebuild=True)

            dialog.connect("response", on_dialog_response)
            dialog.present()
        else:
            self.log("\n=======================================================")
            mode_desc = "Container & Build" if use_container else "Host Compiler"
            self.log(f"[*] Missing {len(missing)} {mode_desc} dependency item(s): {', '.join(missing)}")
            self.log("=======================================================\n")
            self._start_deps_install(use_container=use_container, force_rebuild=False)

    def _start_deps_install(self, use_container=False, force_rebuild=False):
        self.deps_button.set_sensitive(False)
        self.install_button.set_sensitive(False)
        self.check_button.set_sensitive(False)

        def deps_task():
            success = self.kernel_manager.install_build_dependencies(
                progress_callback=self.log,
                use_container=use_container,
                force_rebuild=force_rebuild
            )
            GLib.idle_add(self._on_deps_complete, success)

        threading.Thread(target=deps_task, daemon=True).start()

    def _on_deps_complete(self, success):
        self.deps_button.set_sensitive(True)
        self.check_button.set_sensitive(True)
        self.install_button.set_sensitive(True)
        if self.container_row.get_active():
            engine = self.kernel_manager.get_container_engine()
            if engine:
                self.container_row.set_subtitle(f"Detected engine: {engine.capitalize()} (Debian Bookworm isolated environment)")
        if success:
            self.log("[✓] Build dependencies setup complete.")
        else:
            self.log("[!] Dependency installation was cancelled or encountered an error.")
        return False

    def on_install_clicked(self, button):
        use_container = self.container_row.get_active()

        # Check host dependencies before starting a host build (Step 2)
        if not use_container:
            missing = self.kernel_manager.check_build_dependencies(use_container=False)
            if missing:
                self.log(f"[!] Cannot start host build: missing {len(missing)} package(s): {', '.join(missing)}")
                dialog = Adw.MessageDialog(
                    transient_for=self,
                    heading="Missing Host Dependencies",
                    body=(
                        f"The host system is missing required compilation packages:\n"
                        f"{', '.join(missing)}\n\n"
                        f"Would you like to install them now using pkexec apt-get?"
                    )
                )
                dialog.add_response("cancel", "Cancel")
                dialog.add_response("install", "Install Dependencies")
                dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)

                def on_missing_resp(dlg, resp):
                    if resp == "install":
                        self.on_install_deps_clicked(None)

                dialog.connect("response", on_missing_resp)
                dialog.present()
                return

        is_native = self.system_opt_row.get_active()
        output_dir = self.kernel_manager.get_output_kernel_dir(is_native=is_native)
        engine = self.kernel_manager.get_container_engine() if use_container else "Host"
        mode_str = f"Container ({engine})" if use_container else "Host System"
        opt_str = "Tailored for this machine (Native CPU -march=native & local drivers)" if is_native else "Generic x86-64 (Broad compatibility)"

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Grant Access & Start Build",
            body=(
                f"Kernel compilation mode: {mode_str}\n"
                f"Hardware optimization: {opt_str}\n\n"
                f"Please grant permission to generate and store the output kernel in:\n"
                f"📂 {output_dir}\n\n"
                f"All generated Debian (.deb) packages, kernel configuration, and installation helper scripts will be saved in this location."
            )
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("proceed", "Grant Access & Proceed")
        dialog.set_response_appearance("proceed", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dlg, response):
            if response == "proceed":
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    self.log(f"[✓] Permission granted. Output directory verified:\n    {output_dir}")
                except Exception as e:
                    self.log(f"[!] Warning creating output directory: {e}")
                self._start_kernel_build(use_container=use_container, optimize_for_system=is_native)
            else:
                self.log("[i] Build cancelled by user (access not granted).")

        dialog.connect("response", on_response)
        dialog.present()

    def _start_kernel_build(self, use_container, optimize_for_system=False):
        self.log("\n=======================================================")
        self.log("[*] Starting CachyOS kernel download and build task...")
        mode_desc = f"Container ({self.kernel_manager.get_container_engine()})" if use_container else "Host System"
        opt_desc = "Tailored for this machine (Native CPU & local drivers)" if optimize_for_system else "Generic x86-64"
        self.log(f"    Build Mode: {mode_desc}")
        self.log(f"    Optimization: {opt_desc}")
        self.log(f"    Output Folder: {self.kernel_manager.get_output_kernel_dir(is_native=optimize_for_system)}")
        if self.auto_sign_row.get_active():
            self.log(f"    Auto-Sign MOK: Enabled (will sign linux-image-*.deb packages post-build)")
        else:
            self.log(f"    Auto-Sign MOK: Disabled")
        self.log("=======================================================\n")
        self.install_button.set_sensitive(False)
        self.check_button.set_sensitive(False)
        self.deps_button.set_sensitive(False)

        def build_task():
            try:
                kernel_dir = self.kernel_manager.download_kernel(progress_callback=self.log)
                self.kernel_manager.compile_kernel(
                    kernel_dir,
                    progress_callback=self.log,
                    use_container=use_container,
                    optimize_for_system=optimize_for_system
                )

                # Post-build UEFI Secure Boot signing if enabled
                out_dir = self.kernel_manager.last_output_dir or self.kernel_manager.get_output_kernel_dir(is_native=optimize_for_system)
                if self.auto_sign_row.get_active():
                    self.log("\n=======================================================")
                    self.log("[*] Post-Build Auto-Signing: Signing kernel packages for UEFI Secure Boot (MOK)...")
                    self.log(f"    Target directory: {out_dir}")
                    self.log("=======================================================\n")
                    sign_ok = self.kernel_manager.sign_built_deb_packages(out_dir, log_callback=self.log)
                    if sign_ok:
                        keys = self.kernel_manager.ensure_mok_keys()
                        der = keys.get("der")
                        if der and not self.kernel_manager.is_mok_enrolled(der):
                            GLib.idle_add(self.show_mok_enrollment_dialog, der)

                GLib.idle_add(self._on_build_complete, True)
            except Exception as e:
                self.log(f"\n[!] Build task failed: {str(e)}")
                GLib.idle_add(self._on_build_complete, False)

        threading.Thread(target=build_task, daemon=True).start()

    def _on_build_complete(self, success):
        self.check_button.set_sensitive(True)
        self.install_button.set_sensitive(True)
        self.deps_button.set_sensitive(True)
        if success:
            self.apply_button.set_sensitive(True)
            out_dir = self.kernel_manager.last_output_dir or self.kernel_manager.get_output_kernel_dir()
            self.log(f"\n[✓] Build finished! Artifacts saved in:\n    {out_dir}")
            self.log("[✓] Available Actions:")
            self.log("    • Click 'Install (.deb)' to install the compiled kernel onto this machine.")
            if self.auto_sign_row.get_active():
                self.log("    • Kernel packages have been automatically signed with your UEFI MOK key.")
            else:
                self.log("    • Click 'Sign Existing .deb' to sign packages for UEFI Secure Boot.")
            self.log("    • Click 'Sign (GPG)' in Security Signing card to sign packages with GPG.")
            self.log("    • Click 'Sign /boot' after installation if needing host-level signing.")
        return False

    def on_apply_clicked(self, button):
        self.log("\n[*] Initiating package installation via pkexec...")
        self.apply_button.set_sensitive(False)

        def install_task():
            success = self.kernel_manager.install_kernel(progress_callback=self.log)
            GLib.idle_add(self._on_install_complete, success)

        threading.Thread(target=install_task, daemon=True).start()

    def _on_install_complete(self, success):
        self.apply_button.set_sensitive(True)
        if success:
            self.log("\n[✓] New CachyOS Kernel installed successfully! Please reboot to run the new kernel.")
            if self.is_secure_boot:
                keys = self.kernel_manager.ensure_mok_keys()
                der = keys.get("der")
                if der and not self.kernel_manager.is_mok_enrolled(der):
                    self.log("[!] Notice: UEFI Secure Boot is active. Prompting for MOK enrollment...")
                    self.show_mok_enrollment_dialog(der)
                else:
                    self.log("[✓] MOK key is enrolled and ready for Secure Boot.")
            else:
                self.log("[i] If your system uses UEFI Secure Boot, click 'Sign /boot' to authorize the kernel.")
        return False

    def on_sign_mok_clicked(self, button):
        current_kernel = self.kernel_manager.get_current_kernel_version()
        self.sign_mok_button.set_sensitive(False)
        self.log("\n=======================================================")
        self.log("[*] Starting UEFI Secure Boot signing (MOK)...")
        self.log(f"    Running Kernel: {current_kernel}")
        self.log("=======================================================\n")

        def sign_task():
            try:
                self.kernel_manager.sign_kernel_secureboot(progress_callback=self.log)
                GLib.idle_add(self._on_sign_mok_complete, True)
            except Exception as e:
                self.log(f"\n[!] Secure Boot signing failed: {e}\n")
                GLib.idle_add(self._on_sign_mok_complete, False)

        threading.Thread(target=sign_task, daemon=True).start()

    def _on_sign_mok_complete(self, success):
        self.sign_mok_button.set_sensitive(True)
        if success:
            self.log("[✓] UEFI Secure Boot signing completed successfully!")
            keys = self.kernel_manager.ensure_mok_keys()
            der = keys.get("der")
            if der and not self.kernel_manager.is_mok_enrolled(der):
                self.show_mok_enrollment_dialog(der)
        return False

    def on_enroll_mok_clicked(self, button):
        keys = self.kernel_manager.ensure_mok_keys()
        der = keys.get("der")
        if not der or not os.path.isfile(der):
            self.log("[!] MOK public certificate (MOK.der) could not be found or generated.")
            return

        if self.kernel_manager.is_mok_enrolled(der):
            self.log("[✓] MOK key is already enrolled in your system's UEFI NVRAM.")
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="MOK Already Enrolled",
                body="Your CachyOS Machine Owner Key (MOK) is already enrolled in UEFI Secure Boot NVRAM.\n\nNo further enrollment action is required."
            )
            dialog.add_response("ok", "OK")
            dialog.present()
        else:
            self.show_mok_enrollment_dialog(der)

    def show_mok_enrollment_dialog(self, der_path):
        """Displays an in-app dialog to stage MOK key enrollment via pkexec mokutil --import."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Enroll Machine Owner Key (MOK)",
            body=(
                "Your kernel is signed with your local Machine Owner Key (MOK).\n\n"
                "To allow UEFI Secure Boot to boot this kernel, the key certificate must be enrolled into UEFI NVRAM.\n\n"
                "Please choose a one-time temporary password (8 to 16 characters) to confirm enrollment in MokManager on next reboot:"
            )
        )
        dialog.add_response("cancel", "Enroll Later")
        dialog.add_response("enroll", "Enroll Key")
        dialog.set_response_appearance("enroll", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_enabled("enroll", False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        pwd_label = Gtk.Label(label="MOK Enrollment Password (8–16 characters):", halign=Gtk.Align.START)
        pwd_label.add_css_class("caption")
        pwd_entry = Gtk.PasswordEntry()
        pwd_entry.set_show_peek_icon(True)

        confirm_label = Gtk.Label(label="Confirm Password:", halign=Gtk.Align.START)
        confirm_label.add_css_class("caption")
        confirm_entry = Gtk.PasswordEntry()
        confirm_entry.set_show_peek_icon(True)

        hint_label = Gtk.Label(label="Password must be between 8 and 16 characters.", halign=Gtk.Align.START)
        hint_label.add_css_class("dim-label")
        hint_label.add_css_class("caption")

        box.append(pwd_label)
        box.append(pwd_entry)
        box.append(confirm_label)
        box.append(confirm_entry)
        box.append(hint_label)

        def validate_passwords(*_):
            p1 = pwd_entry.get_text()
            p2 = confirm_entry.get_text()
            if len(p1) < 8 or len(p1) > 16:
                hint_label.set_label("Password must be between 8 and 16 characters.")
                dialog.set_response_enabled("enroll", False)
            elif p1 != p2:
                hint_label.set_label("Passwords do not match.")
                dialog.set_response_enabled("enroll", False)
            else:
                hint_label.set_label("✓ Password valid and confirmed.")
                dialog.set_response_enabled("enroll", True)

        pwd_entry.connect("notify::text", validate_passwords)
        confirm_entry.connect("notify::text", validate_passwords)

        dialog.set_extra_child(box)

        def on_enroll_response(dlg, response):
            if response == "enroll":
                pwd = pwd_entry.get_text()
                self.log("\n[*] Staging MOK key enrollment via pkexec mokutil --import...")

                def enroll_worker():
                    success, msg = self.kernel_manager.enroll_mok_key_gui(der_path, pwd)
                    GLib.idle_add(self._on_mok_enroll_result, success, msg)

                threading.Thread(target=enroll_worker, daemon=True).start()
            else:
                self.log("[i] MOK key enrollment postponed by user.")

        dialog.connect("response", on_enroll_response)
        dialog.present()
        return False

    def _on_mok_enroll_result(self, success, msg):
        if success:
            self.log(f"[✓] {msg}")
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="MOK Enrollment Staged",
                body=(
                    "MOK key import was successfully scheduled!\n\n"
                    "Next time you restart your computer, the blue MokManager screen will appear:\n\n"
                    "  1. Press any key to enter MokManager\n"
                    "  2. Select 'Enroll MOK'\n"
                    "  3. Select 'Continue' and 'Yes' to confirm\n"
                    "  4. Enter the one-time password you just created\n"
                    "  5. Select 'Reboot'\n\n"
                    "After that, your signed CachyOS kernel will boot securely!"
                )
            )
            dialog.add_response("ok", "Got It")
            dialog.present()
        else:
            self.log(f"[!] MOK enrollment error: {msg}")
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="MOK Enrollment Failed",
                body=f"Failed to stage MOK enrollment:\n\n{msg}"
            )
            dialog.add_response("ok", "Close")
            dialog.present()
        return False

    def on_sign_built_debs_clicked(self, button):
        is_native = self.system_opt_row.get_active()
        candidate_dirs = []
        if self.kernel_manager.last_output_dir and os.path.isdir(self.kernel_manager.last_output_dir):
            candidate_dirs.append(self.kernel_manager.last_output_dir)
        default_dir = self.kernel_manager.get_output_kernel_dir(is_native=is_native)
        if os.path.isdir(default_dir) and default_dir not in candidate_dirs:
            candidate_dirs.append(default_dir)
        base_dir = self.kernel_manager.output_base_dir
        if os.path.isdir(base_dir):
            for entry in os.listdir(base_dir):
                full_p = os.path.join(base_dir, entry)
                if os.path.isdir(full_p) and full_p not in candidate_dirs:
                    candidate_dirs.append(full_p)

        import glob
        target_dir = None
        for d in candidate_dirs:
            if glob.glob(os.path.join(d, "linux-image-*.deb")):
                target_dir = d
                break

        if target_dir:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Sign Debian Kernel Packages (MOK)",
                body=(
                    f"Found compiled Debian packages in:\n📂 {target_dir}\n\n"
                    f"Would you like to sign these packages with your UEFI MOK key, or choose another folder?"
                )
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("browse", "Choose Folder...")
            dialog.add_response("sign", "Sign Packages")
            dialog.set_response_appearance("sign", Adw.ResponseAppearance.SUGGESTED)

            def on_resp(dlg, resp):
                if resp == "sign":
                    self._start_deb_signing(target_dir)
                elif resp == "browse":
                    self._choose_folder_and_sign()

            dialog.connect("response", on_resp)
            dialog.present()
        else:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="No Built Packages Found",
                body=(
                    f"No compiled linux-image-*.deb packages were found in the default output location:\n"
                    f"📂 {default_dir}\n\n"
                    f"Would you like to select a folder containing compiled kernel packages?"
                )
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("browse", "Browse Folder...")
            dialog.set_response_appearance("browse", Adw.ResponseAppearance.SUGGESTED)

            def on_browse_resp(dlg, resp):
                if resp == "browse":
                    self._choose_folder_and_sign()

            dialog.connect("response", on_browse_resp)
            dialog.present()

    def _choose_folder_and_sign(self):
        if hasattr(Gtk, "FileDialog"):
            dialog = Gtk.FileDialog(title="Select Directory with .deb Packages")

            def on_folder_selected(dlg, result):
                try:
                    gfile = dlg.select_folder_finish(result)
                    if gfile:
                        folder_path = gfile.get_path()
                        if folder_path:
                            self._start_deb_signing(folder_path)
                except Exception as e:
                    self.log(f"[i] Folder selection cancelled or error: {e}")

            dialog.select_folder(self, None, on_folder_selected)
        else:
            self.log("[!] Folder picker not available on this GTK version.")

    def _start_deb_signing(self, folder_path):
        self.log("\n=======================================================")
        self.log(f"[*] Starting MOK signing for packages in:\n    {folder_path}")
        self.log("=======================================================\n")
        if hasattr(self, "sign_deb_mok_button"):
            self.sign_deb_mok_button.set_sensitive(False)
        if hasattr(self, "sign_wizard_button"):
            self.sign_wizard_button.set_sensitive(False)

        def sign_task():
            success = self.kernel_manager.sign_built_deb_packages(folder_path, log_callback=self.log)
            GLib.idle_add(self._on_deb_signing_complete, success, folder_path)

        threading.Thread(target=sign_task, daemon=True).start()

    def _on_deb_signing_complete(self, success, folder_path):
        if hasattr(self, "sign_deb_mok_button"):
            self.sign_deb_mok_button.set_sensitive(True)
        if hasattr(self, "sign_wizard_button"):
            self.sign_wizard_button.set_sensitive(True)
        if success:
            self.log(f"[✓] Package MOK signing finished for: {folder_path}")
            keys = self.kernel_manager.ensure_mok_keys()
            der = keys.get("der")
            if der and not self.kernel_manager.is_mok_enrolled(der):
                self.show_mok_enrollment_dialog(der)
        else:
            self.log(f"[!] Package MOK signing failed or was incomplete.")
        return False

    def on_sign_debs_clicked(self, button):
        is_native = self.system_opt_row.get_active()
        target_dir = self.kernel_manager.last_output_dir or self.kernel_manager.get_output_kernel_dir(is_native=is_native)
        if not os.path.isdir(target_dir):
            self.log(f"[!] Package folder {target_dir} not found. Please compile the kernel first.")
            return

        self.sign_debs_button.set_sensitive(False)
        self.log("\n=======================================================")
        self.log(f"[*] Starting GPG signing for packages in:\n    {target_dir}")
        self.log("=======================================================\n")

        def sign_task():
            try:
                self.kernel_manager.sign_deb_packages(deb_dir=target_dir, progress_callback=self.log)
                GLib.idle_add(self._on_sign_debs_complete, True)
            except Exception as e:
                self.log(f"\n[!] Package GPG signing failed: {e}\n")
                GLib.idle_add(self._on_sign_debs_complete, False)

        threading.Thread(target=sign_task, daemon=True).start()

    def _on_sign_debs_complete(self, success):
        self.sign_debs_button.set_sensitive(True)
        if success:
            self.log("[✓] Debian package GPG signing completed successfully!")
        return False

    def on_rollback_clicked(self, button):
        installed_kernels = self.kernel_manager.get_installed_kernels()
        if not installed_kernels:
            self.log("[!] No installed kernel packages found.")
            return

        current_kernel = self.kernel_manager.get_current_kernel_version()

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Rollback Kernel",
            body="Select an installed kernel package to remove.\n\n⚠️ Caution: Do not remove the kernel you are currently running!"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove Package")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

        dropdown = Gtk.DropDown.new_from_strings(installed_kernels)

        # Select a kernel that isn't the currently running one to prevent accidental bricking
        for i, pkg in enumerate(installed_kernels):
            if current_kernel not in pkg:
                dropdown.set_selected(i)
                break

        dialog.set_extra_child(dropdown)

        def on_response(dlg, response):
            if response == "remove":
                selected_item = dropdown.get_selected_item()
                if selected_item:
                    package_name = selected_item.get_string()
                    self.log(f"[*] Requesting root authentication to purge {package_name}...")

                    def remove_task():
                        success = self.kernel_manager.remove_kernel(package_name, progress_callback=self.log)
                        if success:
                            GLib.idle_add(self.log, f"[✓] Removed {package_name}. Reboot your computer to boot the previous kernel.")

                    threading.Thread(target=remove_task, daemon=True).start()

        dialog.connect("response", on_response)
        dialog.present()

class KernelUpdaterApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='org.cachyos.debian.kernelupdater')

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = KernelUpdaterWindow(self)
        win.present()

if __name__ == '__main__':
    app = KernelUpdaterApp()
    sys.exit(app.run(sys.argv))
