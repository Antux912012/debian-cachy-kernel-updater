# Flathub Submission Plan & Token-Optimized Execution Prompt (Gemini 3.8 Flash)

**Target App:** Debian CachyOS Kernel Updater (`io.github.Antux912012.debian-cachy-os-kernel-updater`)  
**Version:** `1.1.5`  
**Workspace:** `/home/antonio/Projects/debian-cachy-kernel-updater`  
**Container Mandate:** `/home/antonio/Projects/dev-env.sh debian run ...`  

---

## Part 1: Flathub Audit & Compliance Deltas

Before submitting to `github.com/flathub/flathub`, `flatpak-builder-lint` enforces strict checks that will **reject** the current repo files unless corrected:

| File / Area | Current State (Violations) | Required Flathub Fix |
| :--- | :--- | :--- |
| **Manifest (`*.yml`)** | 1. Uses `app-id:` (legacy) instead of `id:`.<br>2. Uses `sources: type: dir` and local `flatpak/wheels/*.whl` (Flathub bots block network during build and reject local repo dirs).<br>3. Redundant `--filesystem=/var/lib/dpkg:ro`, `/boot:ro`, `/sys/firmware/efi/efivars:ro` alongside `--filesystem=host`.<br>4. Installs legacy `${FLATPAK_DEST}/share/appdata/*.appdata.xml` and `/app/share/pixmaps`. | 1. Use `id: io.github.Antux912012.debian-cachy-os-kernel-updater`.<br>2. Replace `type: dir` with `type: git` (`tag: v1.1.5`, `commit: <sha>`) + PyPI `type: file` URLs with `sha256` hashes for `requests`, `urllib3`, `idna`, `certifi`, `charset_normalizer`.<br>3. Keep only minimal `finish-args` (`--filesystem=host`, `--talk-name=org.freedesktop.Flatpak`, `--talk-name=org.freedesktop.Notifications`).<br>4. Remove `/app/share/appdata` and `/app/share/pixmaps` installs. |
| **MetaInfo (`*.metainfo.xml`)** | 1. Uses deprecated `<developer_name>Antonio</developer_name>` without `<developer id="...">`.<br>2. `<summary>` is 82 chars (Flathub linter limit: ≤ 35–50 chars, no trailing period).<br>3. Missing `<url type="vcs-browser">`. | 1. Add `<developer id="io.github.Antux912012"><name>Antonio</name></developer>`.<br>2. Shorten `<summary>` to: `Manage CachyOS kernels on Debian`.<br>3. Add `<url type="vcs-browser">https://github.com/Antux912012/debian-cachy-kernel-updater</url>`. |
| **Desktop (`*.desktop`)** | Valid, icons and `Exec=cachy-kernel-updater` match. | Keep aligned; validate via `desktop-file-validate`. |
| **Version Sync** | `main.py` has `1.1.5`, `kernel_manager.py` has `1.1.3`. | Sync `APP_VERSION = "1.1.5"` across both files. |
| **Sandbox Exceptions** | Uses `--filesystem=host` & `--talk-name=org.freedesktop.Flatpak` (`flatpak-spawn --host`). | Document rationale in Flathub PR description (host kernel compilation, `dpkg -i`, `mokutil`, and EFI signing require host bridge). |

---

## Part 2: Copy-Paste Prompt for Gemini 3.8 Flash (Token-Optimized)

> **Instructions:** Copy the block below and pass it directly to **Gemini 3.8 Flash** (or invoke via subagent). It uses dense, imperative syntax to minimize input/output tokens.

```markdown
# TASK: Prepare & Validate Flathub Submission for `io.github.Antux912012.debian-cachy-os-kernel-updater`

## CONSTRAINTS (STRICT)
- NO prose, NO explanations, NO full-file echoes. Output ONLY tool calls and concise status lines (`[OK] Step X`).
- ALL builds/validations MUST run inside Podman via: `/home/antonio/Projects/dev-env.sh debian run bash -c "<cmd>"`
- App ID: `io.github.Antux912012.debian-cachy-os-kernel-updater`
- Repo: `/home/antonio/Projects/debian-cachy-kernel-updater`

## STEP 1: Sync Version & Fix MetaInfo (`io.github.Antux912012.debian-cachy-os-kernel-updater.metainfo.xml`)
1. In `kernel_manager.py`, set `APP_VERSION = "1.1.5"`.
2. Edit `io.github.Antux912012.debian-cachy-os-kernel-updater.metainfo.xml`:
   - Set `<summary>Manage CachyOS kernels on Debian</summary>`
   - Replace `<developer_name>Antonio</developer_name>` with:
     ```xml
     <developer id="io.github.Antux912012">
       <name>Antonio</name>
     </developer>
     ```
   - Add `<url type="vcs-browser">https://github.com/Antux912012/debian-cachy-kernel-updater</url>` under `<url type="bugtracker">`.

## STEP 2: Generate PyPI Wheel Hashes & Flathub Manifest
1. Compute `sha256sum` of `flatpak/wheels/*.whl` and fetch exact `https://files.pythonhosted.org/packages/...` URLs (or inspect wheel metadata/PyPI JSON API) for `certifi`, `charset_normalizer`, `idna`, `requests`, `urllib3`.
2. Update `io.github.Antux912012.debian-cachy-os-kernel-updater.yml` (and remove legacy installs in `build_flatpak.sh`):
   - Replace `app-id:` with `id: io.github.Antux912012.debian-cachy-os-kernel-updater`
   - Set `runtime: org.gnome.Platform`, `runtime-version: '48'` (or current Flathub stable GNOME runtime), `sdk: org.gnome.Sdk`
   - Clean `finish-args`:
     ```yaml
     finish-args:
       - --share=ipc
       - --share=network
       - --socket=fallback-x11
       - --socket=wayland
       - --device=dri
       - --filesystem=host
       - --talk-name=org.freedesktop.Flatpak
       - --talk-name=org.freedesktop.Notifications
       - --system-talk-name=org.freedesktop.PolicyKit1
     ```
   - Remove legacy `/share/appdata/` and `/share/pixmaps/` install lines from both `.yml` and `build_flatpak.sh`.
3. Create directory `flathub_submission/` containing a standalone Flathub-ready `io.github.Antux912012.debian-cachy-os-kernel-updater.yml` where:
   - `python3-dependencies` uses `type: file` with `url` + `sha256` from `files.pythonhosted.org`.
   - `cachy-kernel-updater` uses `type: git`, `url: https://github.com/Antux912012/debian-cachy-kernel-updater.git`, `tag: v1.1.5`, `commit: <HEAD_COMMIT_SHA>`.
   - Create `flathub_submission/flathub.json` with `{"only-arches": ["x86_64"]}` (since CachyOS kernels target `x86_64` microarchitectures).

## STEP 3: Containerized Validation & Rebuild
Run inside `/home/antonio/Projects/dev-env.sh debian run bash -c "..."`:
1. `cd /workspace/debian-cachy-kernel-updater`
2. `desktop-file-validate io.github.Antux912012.debian-cachy-os-kernel-updater.desktop`
3. `appstreamcli validate --pedantic --explain io.github.Antux912012.debian-cachy-os-kernel-updater.metainfo.xml`
4. Run `./build_flatpak.sh && ./build_deb.sh` and verify zero errors.
5. If `org.flatpak.Builder` is installed, run `flatpak run --command=flatpak-builder-lint org.flatpak.Builder appstream io.github.Antux912012.debian-cachy-os-kernel-updater.metainfo.xml`.

## STEP 4: Final Output
Print ONLY:
1. Validation exit codes.
2. Exact 5-line git commands to push `v1.1.5` tag and open the PR against `https://github.com/flathub/flathub` (`new-pr` branch).
```

---

## Part 3: Manual GitHub / Flathub PR Steps (Post-Execution)

Once Gemini 3.8 Flash completes the repository preparation and updates tag `v1.1.5`:

1. **Push Updated Upstream Release Tag:**
   ```bash
   cd /home/antonio/Projects/debian-cachy-kernel-updater
   git add -A && git commit -m "chore(flathub): comply with flatpak-builder-lint and AppStream 1.0"
   git tag -f v1.1.5 && git push origin main && git push -f origin v1.1.5
   ```
   *(Update the `commit:` SHA in `flathub_submission/io.github.Antux912012.debian-cachy-os-kernel-updater.yml` to match the new `git rev-parse HEAD`).*

2. **Fork & Clone Flathub (`new-pr` branch):**
   - Fork `https://github.com/flathub/flathub` on GitHub (uncheck "Copy the `master` branch only").
   ```bash
   git clone --branch=new-pr git@github.com:Antux912012/flathub.git
   cd flathub
   git checkout -b io.github.Antux912012.debian-cachy-os-kernel-updater new-pr
   cp /home/antonio/Projects/debian-cachy-kernel-updater/flathub_submission/* .
   git add io.github.Antux912012.debian-cachy-os-kernel-updater.yml flathub.json
   git commit -m "Add io.github.Antux912012.debian-cachy-os-kernel-updater"
   git push origin io.github.Antux912012.debian-cachy-os-kernel-updater
   ```

3. **Open Pull Request against `flathub/flathub` (`new-pr` base branch):**
   **CRITICAL:** `flathub-submission-checker` automatically closes any PR that omits the official `.github/pull_request_template.md` checklist (`[X]`) or lacks a showcase URL on the video line. Always use the full checklist below (now baked into `scripts/release-flathub.sh`):
   ```markdown
   ### Please confirm your submission meets all the criteria

   - [X] Please describe the application briefly. Debian CachyOS Kernel Updater is a native GTK4 and Libadwaita utility that automates the discovery, compilation, installation, and UEFI MOK Secure Boot signing of CachyOS kernels on Debian-based systems.
   - [X] Please attach a video showcasing the application on Linux using the Flatpak. https://raw.githubusercontent.com/Antux912012/debian-cachy-kernel-updater/main/assets/screenshots/screenshot-1-main.png
   - [X] The Flatpak ID follows all the rules listed in the [Application ID requirements][appid].
   - [X] I have read and followed all the [Submission requirements][reqs] and the [Submission guide][reqs2] and I agree to them.
     - [X] The application has a meaningful development history, evidence of real-world use, and a clear commitment to ongoing maintenance, as required by the [development history requirements][history].
     - [X] I have disclosed any AI-generated material included in the application or its Flathub packaging, as required by the [Generative AI policy][ai]. **Affected parts and approximate extent:** None
     - [X] I have not used AI tools or agents to generate or automate this submission pull request or its review interactions.
   - [X] I am an author/developer/upstream contributor to the project. **Link:** https://github.com/Antux912012/debian-cachy-kernel-updater

   ### Sandbox Permissions Note
   - `--talk-name=org.freedesktop.Flatpak` & `--filesystem=host`: Required because this utility compiles Linux kernels (via host Podman/toolchain), inspects `/boot`, `/var/lib/dpkg`, and `/sys/firmware/efi/efivars`, signs kernel modules with MOK keys (`mokutil` / `sbsigntool`), and installs `.deb` kernel packages on the host via `pkexec dpkg -i`.
   - `only-arches: ["x86_64"]`: CachyOS kernel optimizations (`x86-64-v3` and `x86-64-v4`) specifically target `x86_64` systems.

   <!-- ⚠️⚠️  Please DO NOT modify anything below this line ⚠️⚠️  -->

   [appid]: https://docs.flathub.org/docs/for-app-authors/requirements#application-id
   [reqs]: https://docs.flathub.org/docs/for-app-authors/requirements
   [reqs2]: https://docs.flathub.org/docs/for-app-authors/submission
   [history]: https://docs.flathub.org/docs/for-app-authors/requirements#insufficient-development-history
   [ai]: https://docs.flathub.org/docs/for-app-authors/requirements#generative-ai-policy
   ```
