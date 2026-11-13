# Upgrade to CareerPilot 1.0.0

1. Close older helpers and the dashboard. Back up your dedicated workspace and test restoring to a separate directory.
2. Move the old installed skill directory aside. Install 1.0.0 with the installer or release ZIP. The installer refuses to overwrite different files.
3. Run doctor against the intended private workspace, then reopen the dashboard and review Guided setup. Schema 6 is retained. Supported older schemas still migrate with a backup. Reconnect credentials if the original OS key store is unavailable.

[Setup, demo and workspace commands](skills/careerpilot/references/setup.md)
