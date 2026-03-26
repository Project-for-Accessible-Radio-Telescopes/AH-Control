# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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