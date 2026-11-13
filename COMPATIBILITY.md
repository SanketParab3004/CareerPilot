# Compatibility matrix

Tested means exercised by the Windows synthetic suite or installer smoke test. Expected means documented integration with prerequisites and no live verification. Unsupported means the release has no applicable integration without an external host capability.

| Feature | Codex on Windows | Claude Code on Windows | Generic on Windows | macOS/Linux |
|---|---|---|---|---|
| Installation path | Tested | Tested | Tested | Expected |
| Local Python state, dashboard API and archives | Tested | Tested | Tested | Expected |
| Windows DPAPI | Tested | Tested | Tested | Unsupported |
| Native Keychain / Secret Service | Unsupported | Unsupported | Unsupported | Expected |
| Browser and Gmail via available host tools | Expected | Expected | Expected | Expected |
| Telegram delivery with configured token | Expected | Expected | Expected | Expected |
| Optional archive encryption with cryptography | Expected | Expected | Expected | Expected |
| Voice without a host voice tool | Unsupported | Unsupported | Unsupported | Unsupported |

Host capability checks are separate from installation checks. The Windows tests do not establish live connector availability, macOS/Linux behavior or mobile browser compatibility.
