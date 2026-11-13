# VGI — Visual Game Intelligence

**Independent, experimental, open-source diagnostics for game recompilations and ports.**

VGI helps investigate performance regressions and visual anomalies by analyzing frame traces, available logs, associated captures, and before/after comparisons. Hookshot is the first targeted adapter. VGI is a separate, optional tool and does not require changing the game or an upstream repository.

## Current status

**MVP v0.1.0 — experimental.** The initial implementation and 110 automated tests were independently exercised with **synthetic test data**. Real Hookshot gameplay on Windows, visual-detection reliability, and real local-model inference **remain unvalidated**. No production-readiness claim is made.

The reviewed source package, installation instructions, and CI will be published here as the release checks are completed. Until then, this repository is the project landing page, not a downloadable verified release.

## Planned capabilities

- Import Hookshot frame traces and a documented generic session format.
- Flag frame-time regressions and associate available evidence conservatively.
- Generate reproducible reports with checksums, hypotheses, confidence, and limitations.
- Compare controlled before/after sessions.
- Extend support to other ports via optional adapters.
- Expand lightweight visual capture and analysis without requiring code changes upstream.

**Important:** an observation, a timestamp correlation, or an AI suggestion does not prove root cause. VGI does not automatically repair or optimize a game's code.

## Development roadmap

1. Publish audited MVP source, tests, documentation, license, and CI.
2. Run and document the first real Hookshot acceptance test on Windows.
3. Improve lightweight collection, visual analysis, and carefully evaluated optional local AI assistance.

## Privacy and upstream projects

Do not submit game assets, ROMs, proprietary shader binaries, raw private session logs, recordings, credentials, or personal data to this repository. Read and respect upstream project licenses. VGI is not affiliated with or endorsed by the Hookshot maintainers.

## License

The MVP source package uses the MIT license. Its original license and third-party notices will accompany the audited source publication.
