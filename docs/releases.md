# Releases and platform verification

[GitHub Releases](https://github.com/chasebryan/tractor/releases) is the distribution channel. A versioned source archive/wheel is different from a native application bundle. Development source follows `main`. Version tags and release assets are created only after the release workflow's validation succeeds.

The reusable Checks workflow runs Python 3.11/3.12/3.13 on Ubuntu, Windows and macOS, including lint, formatting, offline tests, migrations, secret-leak checks, benchmark and source packaging. Separate native jobs build on each target OS with PyInstaller and launch the bundled Qt application offscreen, open Settings, initialize SQLite and run the packaged benchmark. The release workflow waits for all jobs, attaches native archives plus wheel/sdist and SHA256 checksums, then creates the version tag and release notes. Existing releases are left unchanged. Live providers are never mandatory for release CI.

These checks validate startup and packaged resources on CI runners. They do not prove every OS version, architecture, graphics driver, or desktop integration works. Linux bundles use the runner's glibc baseline. macOS architecture and Windows/Linux architecture are included in each filename. Tor is an external optional dependency and is not bundled.

## Native packages

Extract the **entire** archive; keep supporting files beside the executable.

- Linux: extract the `.tar.gz`, then run `Tractor/Tractor`. A compatible graphical desktop and system graphics libraries are required.
- Windows: extract the `.zip`, then double-click `Tractor/Tractor.exe`. The console is hidden for a desktop launch; CLI output remains available from an existing terminal.
- macOS: extract the `.tar.gz` and open `Tractor.app`. For CLI access use `Tractor.app/Contents/MacOS/Tractor`.

Bundles are not notarized or signed with a publisher certificate. Operating systems may flag downloaded unsigned apps. Only allow a bundle you intended to download from this repository; do not disable global security settings. Source installation remains available when a native bundle is unsuitable. Signing/notarization and dedicated installers are deferred.

To build locally on the target OS:

```bash
python -m pip install . 'pyinstaller>=6.15,<7'
python scripts/build_native.py
```

The script runs an offline smoke test before archiving. On a headless Linux build machine, set `QT_QPA_PLATFORM=offscreen`. Native archives appear under `dist/release`. The build uses [PyInstaller's documented one-directory packaging](https://pyinstaller.org/en/stable/usage.html).

## Governance

Recommended hosted settings: protect `main`, require pull requests and the Checks jobs, require resolved conversations, block force pushes/deletion, restrict version-tag updates, and remove merged branches after release. The repository workflow does not assert that these server-side rules have been enabled. Do not merge a release when a required platform or security check fails.
