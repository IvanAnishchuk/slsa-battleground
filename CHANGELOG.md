# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Opted the repo into the cadence handoff convention (`cadence: handoff-guard`
  tag in CLAUDE.md).
- `scripts/regen_requirements.py` now exports on demand: `--stdout` streams one
  set (prod-only by default, `--include-dev` for both), `--output-dir` writes
  both files, default target `.reports/requirements/` (git-ignored).
- `scripts/audit.py` exports requirements ephemerally into a tempdir (importing
  the regen helper in-process) instead of auditing committed files; dropped the
  staleness check.
- Release workflow generates `requirements-release.txt` through the regen helper.
- Branch protection on `main` allows non-linear history so merge commits work
  (`required_linear_history: false`); repo merge policy is now merge-commit-only
  (`allow_squash_merge`/`allow_rebase_merge: false`, `allow_merge_commit: true`).

### Fixed

- Branch protection on `main` now applies: added the `restrictions: null` key the
  Probot Settings app requires (it silently skips the block when it's absent).

### Removed

- Committed `requirements.txt` / `requirements-dev.txt` — `uv.lock` is the single
  source of truth; requirements are generated on demand. Dropped the
  `regen-requirements` pre-commit hook (kept `uv-lock`).

## [0.0.2] - 2026-04-11

### Added

- Provenance verification script (`scripts/verify_provenance.py`).

### Fixed

- Sigstore bundle glob in release workflow (`.sigstore` -> `.sigstore.json`).
- Sigstore bundle path in SECURITY.md verification command.

## [0.0.1] - 2026-04-11

### Added

- Initial project scaffold.
