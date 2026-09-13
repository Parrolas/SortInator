# Windows installation and notifications

The easiest download is `Organizador-<versão>-Setup.exe`. It installs for the
current user under `%LOCALAPPDATA%\Programs\Organizador`, without requesting
administrator rights. Close Organizador through its tray menu before installing
or uninstalling; a transfer already in progress finishes before the app exits.

Setup adds a Start Menu entry and optionally a desktop shortcut. Starting with
Windows remains an explicit setting inside the app. Existing settings and the
catalog in `%LOCALAPPDATA%\Organizador` are reused. Neither uninstalling nor
updating removes that data or your university and Downloads folders. A portable
ZIP remains available; after switching to Setup, launch the installed copy from
the Start Menu rather than the old portable copy.

Click a filing notification to select the document in File Explorer. Notifications
remain actionable for seven days, including after closing the app. For a batch
with several destination folders, Organizador lists its files with a Show in
folder action. Missing files and expired alerts produce an explanation instead
of opening a different document. Quiet mode and Windows notification preferences
still control whether alerts appear.

The current candidate is unsigned. Setup simplifies installation but does not
remove SmartScreen reputation warnings or certify the app as safe. Future trusted
signing can establish a verified publisher. Do not disable Defender or add
exclusions to install the app. If a concrete detection occurs, record its exact
name and the artifact SHA-256 and investigate it before distributing that build.

## Building

Run `scripts\build.ps1`, then `scripts\setup_installer.ps1` once to obtain the
pinned, publisher-verified Inno Setup 6.7.3 compiler, and finally
`scripts\build_installer.ps1`. Outputs are under `artifacts\releases`; `-OutputRoot`
selects a separate output directory. Setup compilation consumes the already-built
payload and uses its version manifest. Inno Setup requests a commercial license
for commercial use; this project's current personal-use build uses its
non-commercial edition.

For a future signed build, provide `-SigningCertificateThumbprint`, `-SignTool`
and optionally `-TimestampUrl` to both build scripts. The certificate must be
available in the signing machine's certificate store. Build signs and verifies
the application before archiving; Setup signs its installer and uninstaller.
Checksums are generated after signing. No certificate or secret belongs in Git.

## Release acceptance in a disposable Windows account or VM

- Download the exact candidate and verify its SHA-256.
- Install without elevation; verify Start Menu, optional desktop shortcut,
  onboarding and the Installed Apps entry.
- Organize two files separately, click the older alert, and verify its own file
  is selected. Test a batch in one folder and a batch spanning folders.
- Exit the app; click an alert in Notification Center. Verify the correct file
  appears and only one watcher runs. Repeat after an update and after undo.
- Watch startup, registration, update and rollback: no console should flash.
- Try reinstalling and uninstalling during a transfer; Setup must ask for normal
  exit rather than terminate the worker.
- Reinstall, update through the portable update payload, then uninstall. Verify
  the uninstaller survives the update, managed binaries are removed, and seeded
  coursework, settings and catalog remain intact. Reinstall and confirm reuse.
- Run Defender against both final artifacts. A clean scan is evidence for that
  build and signature database, not a guarantee about every antivirus product.

These interactive checks require an actual Windows notification center and a
disposable installation environment; headless tests do not replace them.

The release workflow also runs `scripts/run_installer_e2e.py --disposable-account`
with `--installer` and `--zip` pointing at the candidate and its checksum files.
It refuses accounts with existing Organizador data or registrations, and checks
install, catalog migration, reinstall, a real updater swap, uninstall and data
reuse. It retains its fixture data and logs for inspection in that disposable
account. Popup clicks and visual checks remain the interactive acceptance step.
