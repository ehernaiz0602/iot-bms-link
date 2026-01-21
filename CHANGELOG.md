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

## [0.5.0] - 2025-11-07

### Added

- IoTHub finite state machine watchdog to guarantee hard stopping if IoTHub is unreachable
- Small watchdog for BMS connection state

### Fixed

- Fixed a bug when setting up logging when no configuration files exist

---

## [0.5.1] - 2025-11-09

### Fixed

- Fixed danfoss alarms not getting their own grouping

---

## [0.6.0] - 2025-11-11

### Added

- Added testing mode to General-Settings file to dump IoT payloads to a local file
- Added configurable number of failed requests to mark an IP as stale/unreachable. Calculate expected program timeout by (retries x request_delay x failedConnNum)

---

## [0.7.0] - 2025-11-14

### Changed

- Changed Settings-General to standardize all configuration keys to use lowercase underscores

---

## [0.8.0] - 2025-11-18

### Added

- Ensure removal of pfx certificate after exporting from the Windows Certificate Store
- Added individualized BMS.err files for assistance with monitoring as a service
- version.txt is always created on startup, regardless of configuration settings
- version.txt now also includes the time that the application was (re)started
- Added configurable allowable time limit to azure connection being down after connecting at least once

---

## [0.9.0] - 2025-11-19

### Added

- Emerson E2 IoT Integration

---

## [0.9.1] - 2025-11-21

### Added

- Additional Emerson E2 points

---

## [0.10.0] - 2025-12-15

### Fixed

- Emerson E3 auto-normalization not working properly due to missing nodetype injection
- Fixed a bug where Emerson E2 socket handling was not properly working, leading to driver zombification

### Added

- Ability to send message to local sink (data/local_messages.jsonl) instead of Azure IoTHub for testing
- More complete README.md file
- Better pfx export behavior to handle edge cases where multiple certificates of the same name exists, grabbing the most recent valid one

### Removed

- config/ directory

### Changed

- The configuration files are now available directly in the root directory of the project/executable

---

## [0.11.0] - 2025-12-18

### Added

- Added configurable parameter to set delays between TCP requests in milliseconds for E2 controllers.

### Changed

- Massively reduced number of likely extraneous points to gather from E2 controllers, increasing loop time speed
- E2 socket now disconnects and reconnects between every request, to more accurately emulate UltraSite
- Settings-General now writes to IOTPAYLOAD by default on a new file generation

---

## [0.12.0] - 2026-01-13

### Added

- Added emerson E2 http polling method

### Changed

- E3 now closes sessions between every request

---

## [0.13.0] - 2026-01-21

### Added

- Added emerson E2 alarm parsing

### Changed

- The configuration file emerson_e2 argument now creates HTTP instances instead of TCP instances
- The configuration file emerson_e2_tcp now creates TCP instances
