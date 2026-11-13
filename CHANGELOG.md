# Changelog

This file records user-visible changes. An unreleased entry describes repository work, not a published release or verified real-game result.

## 0.1.1 — Experimental public import

### Fixed

- Compare capture file identity rather than raw short/long Windows path spelling in the native importer test.

- Normalize generic CSV frame IDs before applying declared phase annotations.
- Honor temporal uncertainty for events as well as captures.
- Permit log-only imports as explicitly insufficient per-frame evidence.

### Changed

- Adopted **VGI — Visual Game Intelligence** as the public project name.
- Added the `python -m vgi` entry point and installable `vgi` console command over the existing URD core; retained `python -m urd` compatibility.
- Reworked the public overview and roadmap in English and documented architecture, contribution expectations, security boundaries, and third-party references.
- Added a local acceptance command to collect existing closed-session evidence, analyze it, and record import/evidence checks. These checks do not establish real-game diagnostic effectiveness.

This public repository starts from the prior AI-assisted MVP, preserving its implementation and attribution. It is an initial public import and continuation of that work. Version 0.1.1 remains experimental; current verification must be recorded separately from the prior checkpoint.

## 0.1.0 — Initial local diagnostic implementation

### Added

- Offline generic and native Hookshot CSV ingestion with explicit manifests, synthetic markers, strict numeric/schema checks, and SHA256 provenance.
- Read-only snapshots of existing closed-session Hookshot metrics and optional log output.
- Relative frame-time incident detection with robust preceding baselines, compatible evidence association, uncertainty, and deterministic JSON/Markdown reports.
- Optional Pillow-based visual candidates for persistent black intervals, local flashes, and repeated frames during declared motion.
- Descriptive before/after quantile comparison guarded by declared conditions, continuous gameplay cohorts, and matching replay coverage.
- Source references to inspected Hookshot instrumentation emission at commit `e9975d6c245275aaf89a34e8d17a6bbe8badab46`.
- Offline reduced evidence briefs and an optional loopback-only local-model client with response validation.
- Synthetic fixtures, automated tests, self-test, and a real-session acceptance procedure.

### Validation limits

- The prior 0.1.0 implementation checkpoint recorded 110 passing automated tests. This historical count does not describe verification of subsequent changes.
- Synthetic cases exercise software behavior; real-game diagnosis, false-positive rates, capture overhead, and real-model inference remain unvalidated.
- Windows execution has not been performed as part of project validation.
- Binary native image-log ingestion, automatic cross-domain calibration, continuous capture, and causal diagnosis are not part of this implementation.
