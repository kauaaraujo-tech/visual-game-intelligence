# Local acceptance — real validation still pending

VGI v0.1.1 is experimental. This procedure is intended for a machine with a supported Hookshot build and a legitimate local installation. No real Windows/Hookshot gameplay session or diagnostic effectiveness validation has been performed. Synthetic tool checks have passed on Windows CI; see the validation summary. Remote access is not required to run these commands.

A successful command establishes that a particular declared session was imported and checked. It does not prove the recording is genuine, a slowdown was correctly diagnosed, a visual candidate is a bug, or a fix works. Those claims require the controlled checks below.

## 1. Check the tool independently of the game

From the repository directory, on Windows:

```powershell
py -3 -m vgi self-test
py -3 -m unittest discover -s tests -v
```

On Linux, use `python3` in place of `py -3`. Core checks use synthetic data. Image tests need optional Pillow; a skip is not image verification. The local-model client is exercised with a mock server, not a real model. Python commands are the direct fallback if a convenience script cannot be run; do not change PowerShell execution policy solely for a wrapper.

## 2. Preserve and prepare evidence

Start with an existing complete `hookshot_frames.csv` if one is available. It must match the inspected schema or an adapter for the actual installed build. Do not rename columns to force acceptance.

If the installed build supports it, a future intentional game launch may enable `RX_VK_FRAME_TRACE=1` only for that process. VGI does not configure or execute this step. The trace is written beside the executable and may overwrite a previous file, so preserve the previous recording before launching again. Instrumentation can add overhead.

Record roughly 20–60 seconds of a repeatable scene and input sequence, including a stable interval before the suspected issue. Keep startup preparation separate from the gameplay baseline. Record the actual build, hardware, driver, settings, cache state, power profile, frame generation, and scenario. Close the game to flush buffered files.

Presentation intervals measure CPU-side timing, not GPU completion or scanout. Different counters and clocks are not interchangeable. See [HOOKSHOT_INSTRUMENTATION.md](HOOKSHOT_INSTRUMENTATION.md).

## 3. Run one local acceptance command

Supply the directory that contains `hookshot_frames.csv` and a new output directory:

```powershell
py -3 -m vgi accept 'C:\Games\Hookshot\bin' --session-closed --out .\local-acceptance\run-001
```

The path is a placeholder. On Linux:

```bash
python3 -m vgi accept /path/to/hookshot/bin --session-closed --out local-acceptance/run-001
```

The command orchestrates read-only collection, analysis, and import/evidence checks. It copies only the known metrics file and optional `hookshot_log.txt`; it does not search for ROMs, assets, saves, shader caches, or screenshots, and does not alter the game. The closed-session flag is your declaration, not detection that the process has ended. Evidence is marked user-declared real, not independently verified.

Read `acceptance.json`, `report/report.md`, and `report/report.json`. A successful import still records `real_game_diagnostic_validated=false`, unknown false-positive rate, and unknown capture overhead. For an existing session manifest with correctly aligned captures, pass that JSON file as the source and add `--visual` when Pillow is installed.

Read the generated result, warnings, limitations, and reports. Missing traces, incompatible headers, incomplete evidence, or absent independent validation must remain visible. A command failure can leave a partial new output directory; inspect it and choose a fresh destination for a retry.

For explicit separate steps:

```powershell
py -3 -m vgi collect 'C:\Games\Hookshot\bin' --session-closed --out .\local-sessions\run-001
py -3 -m vgi analyze .\local-sessions\run-001\session.json --out .\output\run-001
```

## 4. Review real diagnostic effectiveness

The acceptance run cannot automate these judgments:

- Confirm the report's SHA256 inputs match the preserved recording, and that import did not change them.
- Independently identify a known slowdown after a sufficient stable baseline. Check whether it was detected and whether a stable control interval produced spurious incidents.
- Check same-row native metric associations. Ordinary untimestamped text logs must remain context, not synchronized incident evidence.
- Associate images only when independent evidence establishes the counter/clock mapping. Otherwise retain the limitation.
- Verify that each proposed explanation is labeled a hypothesis with an evidence reference and a falsifiable next test. Busy GPU time or compilation overlap does not establish a hardware limit or a port defect.
- Repeat the same scenario and record missed incidents, false positives, and run-to-run variability.
- Measure observer overhead with controlled instrumented versus uninstrumented runs rather than assuming recording is free.

Keep these observations with the session. A clean import and plausible-looking report alone do not complete real validation.

## 5. Declare gameplay only with evidence

Native traces do not recognize scene semantics. If a controlled replay establishes which frames are gameplay, add a traceable annotation to the manifest:

```json
"phase_annotations": [
  {"start_frame": 120, "end_frame": 899, "phase": "gameplay", "basis": "fixed replay X; interval independently confirmed in this recording"}
]
```

Endpoints must exist, ranges must not overlap, and startup warmup cannot be relabeled as gameplay. The basis is a declaration preserved for review, not automatic scene verification. Do not annotate solely to make a comparison pass.

## 6. Compare controlled repetitions

Use the conditions listed in the [README](../README.md), continuous cohorts of at least 30 gameplay samples, equal sample counts and independent replay coverage, and multiple alternating or randomized A/B runs. VGI's pair comparison is descriptive and does not establish statistical significance.

If pipeline waits overlap the incident, first compare recorded cold/warm cache state, program reuse, and identical replay/build/driver conditions. Do not automatically clear caches or change a driver. If GPU backpressure appears, test resolution scaling with CPU/GPU busy time, clocks, and power recorded. Vary one condition at a time.

Only a reproducible effect supports evaluating a specific code change. Preserve before/after evidence and retain uncertainty. Review all outputs before sharing: reports may include sensitive metadata, raw log context, and evidence images. Do not publish proprietary or private material.
