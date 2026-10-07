# Releasing

Desktop releases build in GitHub Actions (`.github/workflows/desktop.yml`) on every `v*.*.*` tag: macOS (Apple silicon and Intel), Linux (AppImage, deb, rpm) and Windows (MSI, NSIS). The release job collects the bundles into a draft GitHub release; publishing the draft makes it the one the updater feed points at.

## One-time setup: repository secrets

Add these under Settings, Secrets and variables, Actions. Builds work without them (unsigned, no updater artifacts); each group switches on its feature when present.

| Secret | What it is |
| --- | --- |
| `APPLE_CERTIFICATE` | Your Developer ID Application certificate exported as `.p12`, then base64-encoded |
| `APPLE_CERTIFICATE_PASSWORD` | The password chosen when exporting the `.p12` |
| `APPLE_SIGNING_IDENTITY` | The certificate's name, for example `Developer ID Application: Your Name (TEAMID)` |
| `APPLE_ID` | The Apple ID email used for notarization |
| `APPLE_PASSWORD` | An app-specific password for that Apple ID |
| `APPLE_TEAM_ID` | Your ten-character team ID |
| `TAURI_SIGNING_PRIVATE_KEY` | The updater private key (below) |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Its password, if you set one |

## One-time setup: the updater key pair

Generate it on your own machine and keep the private key out of the repository:

```bash
cd frontend && npx tauri signer generate -w ~/.tauri/formlit.key
```

Put the private key file's contents in `TAURI_SIGNING_PRIVATE_KEY` and paste the printed public key into `plugins.updater.pubkey` in `src-tauri/tauri.conf.json`. Until the public key is there, the app skips update checks.

## Cutting a release

1. Bump the version in every place `.docs/BRANCHING.md` lists, as the last commit of the series, and tag `vX.Y.Z`.
2. Push the tag. The workflow freezes the engine on each platform, builds the bundles, signs and notarizes the macOS app, and writes `latest.json` from the updater signatures.
3. Check the draft release's assets, then publish it.

## Notes

- The macOS bundle runs with the hardened runtime; `src-tauri/entitlements.plist` lets the PyInstaller sidecar load the libraries it unpacks at launch.
- Windows builds are unsigned until a code-signing certificate is available, so SmartScreen warns on first run.
