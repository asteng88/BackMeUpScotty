# Changelog

All notable changes to BackMeUpScotty are documented in this file.

## [Unreleased]

### Added

- Initial public source release.
- Git, contribution, security, and third-party licensing documentation.
- A canonical `VERSION` file displayed in the application interface.

### Changed

- Replaced the custom packaging script with a documented direct PyInstaller build command.
- Migrated dependency management, development commands, and CI to UV.

### Fixed

- Prevented multiple running instances from registering duplicate system-tray icons.
