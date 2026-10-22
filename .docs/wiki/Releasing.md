# Releasing

formlit's own repository builds no release; its GitHub Actions only run the checks. Desktop releases are built by formcompiler (`nodemode-ai/formcompiler`), the release pipeline for every form* app: macOS (Apple silicon and Intel), Linux (AppImage, deb, rpm) and Windows (MSI, NSIS). formcompiler collects the bundles into a draft release named `formlit-vX.Y.Z` on its own release page. Publishing the draft there makes it the one the updater feed (`formlit-updates/latest.json` on formcompiler) points at.

## One-time setup: signing secrets in formcompiler

These are set in formcompiler's repository (Settings, Secrets and variables, Actions), never in formlit's. Builds work without them (unsigned, no updater artifacts); each group switches on its feature when present.

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

Put the private key file's contents in formcompiler's `TAURI_SIGNING_PRIVATE_KEY` secret and paste the printed public key into `plugins.updater.pubkey` in `src-tauri/tauri.conf.json`. Until the public key is there, the app skips update checks.

## Cutting a release

1. Bump the version in every place `.docs/BRANCHING.md` lists, as the last commit of the series, on main.
2. Push a branch named `compile_vX.Y.Z` from that commit, for example `git push origin HEAD:compile_v0.46.1`. CI runs on it. The name must match the version in `src-tauri/tauri.conf.json`, or formcompiler refuses it and says why.
3. formcompiler finds the branch on its next watch run (every 8 hours), or at once when its watch is run by hand. Once CI has passed on that commit, it freezes the engine on each platform, builds the bundles, signs and notarizes the macOS app when its Apple secrets are set, and writes `latest.json` from the updater signatures.
4. Check the draft release's assets on formcompiler's release page, then publish it there.

## Notes

- The macOS bundle runs with the hardened runtime; `src-tauri/entitlements.plist` lets the PyInstaller sidecar load the libraries it unpacks at launch.
- Windows builds are unsigned until formcompiler holds a code-signing identity, so SmartScreen warns on first run.
