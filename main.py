import sys
import os
import subprocess
import threading
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk

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
            subtitle="Installer, Updater & Rollback (v1.0.6)"
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

        self.output_row = Adw.ActionRow()
        self.output_row.set_title("Output Package Folder")
        self.output_row.set_subtitle(self.kernel_manager.get_output_kernel_dir(is_native=False))

        self.open_output_button = Gtk.Button(label="Open Folder")
        self.open_output_button.set_valign(Gtk.Align.CENTER)
        self.open_output_button.connect("clicked", self.on_open_output_clicked)
        self.output_row.add_suffix(self.open_output_button)

        self.options_group.add(self.output_row)
        self.content_box.append(self.options_group)

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
        is_native = self.system_opt_row.get_active()
        output_dir = self.kernel_manager.get_output_kernel_dir(is_native=is_native)
        use_container = self.container_row.get_active()
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
            self.log("[✓] Click 'Install (.deb)' to install immediately or 'Open Folder' to view packages.")
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
