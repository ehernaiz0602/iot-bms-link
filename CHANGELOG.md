# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.4.0] - 2025-11-07

### Added

- Support for batching multiple devices into a single IoT Hub message
- `CHANGELOG.md` file with Keep a Changelog format
- Added support for configurable logging level, log file sizes, and number of log backups
- Added hard stop behavior when certificates are unable to be exported

### Fixed

- Bug where full frames were sent too frequently due to incorrect interval units
- Fixed a bug where certain message sizes would trigger a failed send to IoTHub
- Fixed a bug where circuit information was sometimes not properly read
- Fixed a bug where certificates could not properly be loaded sometimes

---
