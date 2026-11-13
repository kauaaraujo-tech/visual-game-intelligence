# Contributing to VGI

Contributions should improve the reliability of evidence and the clarity of investigation. Keep measured facts, user declarations, correlations, and hypotheses distinct. Do not introduce unsupported causal claims or hide `inconclusive` results.

## Development setup

Use Python 3.10 or newer in an isolated environment:

```bash
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -e .
python -m vgi self-test
python -m unittest discover -s tests -v
```

The core uses the standard library. To work on image analysis, install the optional dependency and run the suite again:

```bash
python -m pip install -r requirements-visual.txt
python -m unittest discover -s tests -v
```

Do not treat skipped visual tests as verification of image behavior. Record the Python version, optional dependencies, commands run, and relevant results in your pull request. Do not claim Windows, real-game, GPU, model-inference, or CI verification unless it was actually performed.

## Making a change

Keep changes focused and use meaningful Conventional Commit messages, such as `fix: reject conflicting capture domains` or `docs: clarify replay coverage requirements`. Explain the concrete trigger, resulting behavior, compatibility impact, and validation in the pull request.

Preserve `python -m urd` compatibility when changing the VGI entry point unless an intentional breaking change is documented. Preserve explicit synthetic markers, schema validation, deterministic report serialization, and strict evidence boundaries. Update user documentation when behavior changes.

Add focused regression coverage for parser changes, identity/clock handling, comparison validity, output safety, or changed analysis behavior. Prefer deterministic synthetic cases that establish the invariant being protected. Include malformed input and uncertainty boundaries where relevant. Changes to model transport must preserve explicit loopback-only operation and untrusted-response handling.

## Adapters and reproducible experiments

An adapter proposal should identify the source format and immutable source version, explain every counter and clock, preserve uncertainty, and reject unsupported input. Prefer existing instrumentation. Never infer screenshot timing from its filename or modification time, and never equate counters just because their integers match.

For a performance comparison, record actual hardware, settings, driver, power profile, build, cache state, collector, sample kind, frame generation, replay, and scenario. Declare replay coverage independently of measured runtime. Keep cohorts continuous and equivalent, measure instrumentation overhead, and repeat controlled A/B runs. Change one experimental condition at a time. A single improved percentile is not proof of causality or a verified fix.

## Public data and privacy

Only submit data you have the right to publish. Prefer tiny, generated fixtures explicitly labeled synthetic. Do not include game executables, ROMs, proprietary assets, shader/program dumps, saves, upstream game-derived code, private logs, or real screenshots. Do not upload user evidence to external services as part of investigation or tests.

Review manifests, report context, paths, identifiers, filenames, and image metadata before opening an issue or pull request. A report is not automatically anonymous. Provide a minimal synthetic reproduction instead of a private recording whenever possible.

## Licensing and security

Contributions must be compatible with the project's MIT license and retain required third-party notices. Cite inspected upstream formats and schemas; do not copy GPL implementation code into the independent adapter. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Use the process in [SECURITY.md](SECURITY.md) for security-sensitive reports. Ordinary bug reports should include expected versus actual behavior, exact reproduction commands, the relevant version, and a safe synthetic example.
