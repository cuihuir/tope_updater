# OTA State And Version Handling Design

## Goal

Make OTA behavior reliable when cloud versions use a `v` prefix, when a downloaded-but-not-installed package is superseded, and when the updater restarts around install state transitions.

## Requirements

- External API requests may use versions like `v0.1.1`.
- Internal deployment logic must use normalized versions like `0.1.1` so version snapshot paths remain `/opt/tope/versions/v0.1.1`, never `vv0.1.1`.
- Reports sent to device-api must continue to include `version` with a `v` prefix.
- `POST /download` must allow a new download while current status is `toInstall`.
- A new download must clear any stale pending package state and stale ZIP file before it starts.
- Expired pending packages must not block a new download; they should be removed and replaced.
- Active operations remain exclusive: `downloading`, `verifying`, `installing`, and `rebooting` reject new downloads.
- `POST /update` should install only from a valid pending package. It may allow retry from `failed` only when a persistent package state still exists and matches the requested version.
- The updater must persist an `installing` state before deployment starts so startup can detect an interrupted install.
- On startup, an interrupted `installing` state should reset to `failed` and keep enough context for the user/cloud to retry or push a newer package.
- Progress values exposed or reported by download must be clamped to `0..100`.

## Architecture

Add a small version utility as the single boundary for version string normalization. API models accept `vX.Y.Z`; route handlers normalize before storing state or calling services. Manifest parsing accepts either `X.Y.Z` or `vX.Y.Z`, then normalizes to `X.Y.Z`.

Keep the existing state manager and service structure. Add narrowly scoped cleanup behavior in the download route/service path so stale pending packages are removed before a superseding download. Persist install state in `_update_workflow` before deployment, and recover it conservatively during startup.

## Testing

Unit tests cover:

- API requests accepting `v0.1.1` for both download and update.
- route handlers passing normalized `0.1.1` into workflows.
- `toInstall` allowing new download.
- expired pending package cleanup allowing download.
- stale pending package ZIP cleanup before superseding downloads.
- manifest version normalization.
- version directory creation remaining `v0.1.1`.
- install state persistence before deploy.
- startup recovery from interrupted install.
- download progress clamping.
