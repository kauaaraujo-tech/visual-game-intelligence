# VGI — Visual Game Intelligence

**Experimental v0.1.1** — continuation of the experimental v0.1.0 MVP.

[![CI](https://github.com/kauaaraujo-tech/visual-game-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/kauaaraujo-tech/visual-game-intelligence/actions/workflows/ci.yml) · [MIT license](LICENSE) · [Python 3.10+](pyproject.toml)

Local evidence-based diagnostics for recompiled and emulated games. VGI imports recorded frame timings, correlates declared events and captures, and produces inspectable JSON and Markdown reports. Hookshot is the first native adapter; a generic session format keeps the analysis independent of any one project.

**The implementation has been exercised with clearly marked synthetic data. No diagnosis from a real game, real local model inference, or real-game false-positive rate has been validated.** Findings are investigation candidates, not proof of a rendering bug, its cause, or a successful fix.

## Quick start

Requires **Python 3.10 or newer**. The core uses the standard library. No administrator privileges, API key, Docker, background service, or game installation is required for the synthetic demo.

From the repository directory:

```bash
python -m vgi self-test
python -m unittest discover -s tests -v
python -m vgi demo --native-hookshot --out synthetic-session
python -m vgi analyze synthetic-session/session.json --out synthetic-report
```

Use `python3` if that is your Python command. On Windows, use `py -3`, for example `py -3 -m vgi self-test`. The self-test exercises native and generic ingestion, known synthetic incident detection, evidence association, and deterministic report output. It never runs a game.

An editable installation also exposes the `vgi` command:

```bash
python -m pip install -e .
vgi --help
```

`python -m urd` remains supported for compatibility with the original Universal Recompilation Diagnostics implementation. The internal Python package and normalized schema retain their existing names.

Pillow is optional and enables image analysis:

```bash
python -m pip install -r requirements-visual.txt
```

Without Pillow, performance analysis still works; `--visual` reports that image analysis is unavailable. Automated visual tests may be skipped when the dependency is absent. The commands above are instructions to run locally, not a claim of verification on every supported operating system.

## Current capabilities

| Capability | Implemented behavior | Validation boundary |
|---|---|---|
| Offline ingestion | Strict native Hookshot CSV and generic manifest-based bundles | Synthetic fixtures of inspected formats; installed game builds are not verified |
| Relative slowdown detection | Robust preceding baseline, incident frames, associated events and captures | Heuristic thresholds; real-game sensitivity and false positives remain unmeasured |
| Evidence reports | SHA256 provenance, source file/line references, parameters, limitations, and next tests | Hashes establish input identity, not authenticity or causal truth |
| Visual candidates | Persistent black intervals, local one-frame flashes, repeated frames during declared motion | Conservative luminance heuristics; adjacent identified captures required |
| Source references | Links to the inspected instrumentation emission at a pinned commit | Does not identify faulty code or establish the user's binary version |
| Before/after comparison | Descriptive p50/p95/p99 changes for explicitly matched cohorts | One pair cannot establish significance, causality, or a proven fix |
| Optional local model | Reduced evidence brief and loopback-only model client | Transport tested with a mock server; real model quality remains unvalidated |

VGI does not provide a live overlay, automatic continuous capture, binary `RX_VK_FRAMELOG` ingestion, automatic clock calibration, automatic fixes, or a validated hardware-versus-port verdict.

## Import an existing Hookshot session

VGI uses an existing `hookshot_frames.csv` from a build supporting `RX_VK_FRAME_TRACE=1`. **The collector does not enable instrumentation or launch the game.** Instrumentation can add overhead, and a subsequent game run may overwrite a previous trace. Preserve existing evidence before starting another instrumented run.

Record a short repeatable scenario with a stable interval before the issue. Close the game to flush buffered output. Then supply the directory containing the trace:

```bash
python -m vgi collect /path/to/hookshot/bin --session-closed --out local-sessions/run-001
python -m vgi analyze local-sessions/run-001/session.json --out output/run-001
```

Windows example:

```powershell
py -3 -m vgi collect 'C:\Games\Hookshot\bin' --session-closed --out .\local-sessions\run-001
py -3 -m vgi analyze .\local-sessions\run-001\session.json --out .\output\run-001
```

These paths are placeholders. Collection copies only `hookshot_frames.csv` and, if present, `hookshot_log.txt` into a new directory outside the input. It checks for changes during copying and validates the resulting manifest. A failed collection may leave an output directory; inspect it and choose a new destination for a retry. A real-data marker is a user declaration, not independent authentication. If only `hookshot_log.txt` exists, collection produces a context-only report with `insufficient_data`; it never invents per-frame measurements. Missing evidence or incompatible headers produce explicit errors.

For a single local acceptance run that collects, analyzes, and records import/evidence checks:

```bash
python -m vgi accept /path/to/hookshot/bin --session-closed --out local-acceptance/run-001
```

On Windows: `py -3 -m vgi accept 'C:\Games\Hookshot\bin' --session-closed --out .\local-acceptance\run-001`. This checks an imported session; it does not establish that the evidence is authentic or that diagnostics are effective in a real game. See the [local acceptance procedure](docs/LOCAL_ACCEPTANCE.md). Windows execution has not been performed as part of this project's validation.

A manifest may also be written directly:

```json
{
  "schema_version": 1,
  "adapter": "hookshot",
  "session_id": "run-001",
  "synthetic": false,
  "metadata": {"scenario": "repeatable scene", "build": "actual build identifier"},
  "performance_trace": "hookshot_frames.csv",
  "log": "hookshot_log.txt",
  "captures": []
}
```

Use `frame_log` instead of `performance_trace` for `RX_VK_FRAME_LOG`, whose inspected header is `frame,time_s,frametime_ms`. They are mutually exclusive primary traces. Optional `present_trace` is retained as unaligned context. Strict native headers protect against silently reinterpreting a different export version. See [the session contract](docs/CONTRACT.md) and [the pinned Hookshot instrumentation evidence](docs/HOOKSHOT_INSTRUMENTATION.md).

## Evidence identity and clocks

VGI preserves measured facts, declarations, correlations, and hypotheses separately:

- Metrics on one `hookshot_frames.csv` row share a frame identity. Its local timeline is reconstructed from rounded durations, with accumulated uncertainty; it is not an absolute timestamp. The first row is warmup because its accumulators can include startup.
- `RX_VK_FRAME_LOG` measures presentation-call intervals, not GPU completion or display scanout. Generated frames may add presentations.
- Ordinary text logs have no verified monotonic timestamp and remain session context. Line order does not become time.
- Game presents, renderer counters, binary sequence numbers, and display frames are distinct domains. Matching integers do not establish correspondence.
- Captures require explicit, defensible frame or clock identity. Filenames and filesystem modification times never establish synchronization.

For example, use this capture declaration **only after independently establishing the correspondence**:

```json
{"path":"images/frame.png","frame_id":321,"frame_domain":"hookshot.performance_frame"}
```

A file named `vk_321.png` alone does not justify that declaration. Conflicting domains or frame/timestamp identities prevent association. Unaligned evidence stays visible as context.

## Detection and visual limits

The detector needs at least 12 preceding continuous samples and uses up to 60, with a median and robust MAD/IQR dispersion. An incident must exceed the baseline by all three thresholds: 1.5 times baseline, 5 ms, and six dispersion units. The baseline freezes during sustained degradation; warmup, menu, loading, and gaps reset it.

A consistently slow system may have no relative incident. Gradual degradation, problems before a baseline forms, and natural scene workload changes can also defeat or confuse the heuristic. Native trace phases are not automatically recognized: unknown phases may be analyzed for relative timing, but controlled comparisons require evidence-backed gameplay annotations.

```bash
python -m vgi analyze local-sessions/run-001/session.json --visual --out output/visual-001
```

Visual analysis compares adjacent explicitly identified frames in a compatible domain. Persistent black candidates require at least three dark frames bracketed by textured scenes. Repeated-frame candidates require `metadata.expected_motion=true`; whole-image flashes remain ambiguous. Excluded phases, ambiguous frame generation, conflicting identities, sparse samples, and changing dimensions constrain comparisons.

A 16×9 luminance grid can miss small details and color-only defects. The implementation bounds image count, bytes, and pixels, but it is not a sandbox for hostile files. Candidates always have low confidence. `insufficient_data` from sparse captures is expected, and no candidate does not establish correct rendering.

## Reproducible comparisons

```bash
python -m vgi compare before/session.json after/session.json --out comparison.json
```

Both manifests must declare the same known `metadata` values for `scenario`, `hardware`, `settings`, `run_group`, `collector`, `sample_kind`, `cache_state`, `driver`, `power_profile`, `frame_generation`, and `replay`. Builds may differ to test a change. Do not invent metadata merely to make a pair comparable.

Declare an inclusive `scenario_frame_range=[start,end]` and positive `scenario_duration_ms` describing simulation/replay coverage **independently of measured runtime**. Cohorts need at least 30 continuous gameplay samples, matching sample counts and coverage, and equal synthetic markers. Otherwise the result is `inconclusive`. Native phases need explicit `phase_annotations` with existing endpoints and an evidence `basis`; startup warmup cannot be relabeled as gameplay.

`regression` and `improvement` are descriptive labels for a quantile change exceeding both 5% and 1 ms. Small cohorts have unstable tail estimates. Repeat alternating or randomized A/B runs and record observer overhead before interpreting an effect. GPU utilization, waits, or compilation correlated with a slowdown do not distinguish hardware limits from inefficient implementation; vary one controlled condition at a time.

## Optional local model assistance

Generate and inspect the reduced brief without running a model:

```bash
python -m vgi brief output/run-001/report.json --out evidence-brief.json
```

If you already run a compatible local `/api/generate` server:

```bash
python -m vgi ai-local output/run-001/report.json --model YOUR_LOCAL_MODEL --port 11434 --out ai-hypotheses.json
```

The client uses only literal `127.0.0.1`, bypassing proxies and DNS, and follows no redirects. It does not install, download, or start a model. The brief omits image pixels, raw logs, file paths, and source code; it retains numbers, evidence IDs, and event kinds. Free-text IDs and event kinds can still contain sensitive text: inspect the brief first. A locally configured server may relay requests elsewhere, which VGI cannot control.

Model suggestions must cite existing evidence IDs and include a next test. They remain untrusted hypotheses; no command is executed and no correction is applied. Valid references do not validate a claim.

## Project documentation

- [Architecture](docs/ARCHITECTURE.md): module boundaries, evidence flow, and trust boundaries.
- [Roadmap](docs/ROADMAP.md): completed capabilities, pending validation, and dependency-based next steps.
- [Contributing](CONTRIBUTING.md): reproducible changes, tests, and public-data rules.
- [Security](SECURITY.md): local processing scope and responsible reporting.
- [Changelog](CHANGELOG.md): version history and naming transition.

The [local acceptance procedure](docs/LOCAL_ACCEPTANCE.md) describes the pending real-machine validation. See the [validation summary](docs/VALIDATION.md) for audited test scope and limitations. Detailed engineering audits are maintained separately; all public examples are synthetic. Historical counts describe their own checkpoints.

## Privacy and licensing

Analysis has no automatic external uploads or telemetry. CLI invocations finish; VGI installs no scheduled tasks or persistent service. Real reports can include sensitive metadata, raw log context, and copied evidence images. Review every file before sharing. Never contribute game executables, ROMs, proprietary assets, shader dumps, saves, or private captures.

VGI is an independent MIT-licensed implementation. Hookshot is GPL-3.0-or-later; upstream implementation code is not included in this distribution. Optional Pillow has its own license and component notices. VGI is not affiliated with or endorsed by Hookshot. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
