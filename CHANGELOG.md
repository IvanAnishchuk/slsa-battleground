# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Opted the repo into the cadence handoff convention (`cadence: handoff-guard`
  tag in CLAUDE.md).

## [0.0.2] - 2026-04-11

### Added

- Provenance verification script (`scripts/verify_provenance.py`).

### Fixed

- Sigstore bundle glob in release workflow (`.sigstore` -> `.sigstore.json`).
- Sigstore bundle path in SECURITY.md verification command.

## [0.0.1] - 2026-04-11

### Added

- Initial project scaffold.
