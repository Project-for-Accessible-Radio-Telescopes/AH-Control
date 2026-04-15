# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-15
### Major Update: Resolved issue #2
- Improved Welch method power spectrum analysis with `scipy.signal.welch` and multi-segment averaging for improved frequency resolution.
- Verified full RTL-SDR connection.
- Verified data recording and processing.

## [0.1.4] - 2026-04-08

### Added
- Implemented Welch method power spectrum analysis with `scipy.signal.welch` and multi-segment averaging for improved frequency resolution.
- Added cross-platform WiFi network scanning (macOS, Linux, Windows) in `logic/wifi_scanner.py`.
- Integrated intelligent RTL-SDR device detection with source-triggered device discovery in Data Recording UI.
- Added Virtual WiFi source option for users without RTL-SDR hardware, with real network detection and synthetic fallback.

### Changed
- Refactored Data Recording UI from "Frequency Scan Recording" to "Power Spectrum Analysis (Welch Method)" with simplified parameters.
- Enhanced plot visualization with dBm scale for improved peak visibility and realistic signal strength representation.
- Improved peak rendering with wider Gaussian envelopes (1-2% of FFT size) matching realistic WiFi channel bandwidth.
- Updated spectrum export formats to include power in dBm with comprehensive metadata.

### Fixed
- Fixed frequency validation to scope RTL-SDR hardware limits (≤1.766 GHz) separately from Virtual WiFi (2.4 GHz and 5 GHz bands).
- Enhanced WiFi peak visibility by 5x amplitude boost and proper RSSI-to-linear-to-dBm conversion.

## [0.1.3] - 2026-03-26

### Added
- Added changelog tracking for PARTApp.
- Added Lesson Wizard with classroom-ready templates loaded from `data/lesson_templates.json`.
- Added side-by-side recording comparison mode with peak, SNR, and delta-spectrum summaries.
- Added spectrum annotations in Advanced Signal View (right-click notes), with project-level save/load persistence in `.ahf` sessions.
- Added a built-in virtual network capture device option for users without RTL-SDR hardware.
- Added an RFI mapping workflow to sweep WiFi/Bluetooth-oriented frequency profiles and plot average power maps.
- Added app-wide lesson orchestration hooks so templates can launch recording, processing, advanced view, compare mode, and RFI mapping with step-specific payloads.
- Expanded `data/lesson_templates.json` into richer interactive templates with hints, expected outcomes, auto-complete behavior, and preset action arguments.

## [0.1.2] - 2026-03-26

### Added
- Added live RMS monitoring in Data Recording, including progress-aware RMS updates during capture.
- Added optional frequency reference overlays in Advanced Signal View backed by `data/frequency_reference.json`.
- Added recording integrity validation for sample/metadata pairs with non-blocking warnings in recording and advanced analysis flows.

## [0.1.1] - 2026-03-13

### Added
- Enhanced project structure with additional utility functions and modules.
- Added a signal window.
- Allowed for more flexible configuration options in the application setup.
- More complex and comprehensive waterfall visualisation of npy files after iq conversion.
- Added `.ahf` project session files to save and load the main application state.

## [0.1.0] - 2026-02-01

### Added
- Initial project structure and core application modules.
- Basic installation and usage documentation.
- Initial test and utility scaffolding.