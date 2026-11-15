# VGI 0.1.1 — experimental audit summary

Audit date: 2026-11-13. The original MVP at commit `48f0047` was extracted separately and tested independently: **110 tests passed**. The updated VGI working tree passed **134 tests**, including regressions for both issues found during the audit. Core synthetic self-tests also passed with `python -S`, without site-packages.

Two correctness defects were reproduced and fixed: generic phase annotations were matched before CSV frame IDs were normalized, and event timestamp uncertainty was ignored during evidence association.

Standard-library trace observed **1,202/1,297 executable lines (92.6754%)** across original modules loaded in the test process. CLI subprocess execution is excluded from that denominator. This is line coverage, not branch coverage or a measure of diagnostic accuracy.

The architecture separates importers, normalized evidence, detection, reporting and optional visual/model assistance. Reviewed networking is an explicit loopback-only model request; core analysis performs no automatic external uploads. This was a scoped review, not a security certification or complete dependency audit.

**Real-game diagnostic accuracy remains unvalidated.** Log-only input correctly produces `insufficient_data`; successful import does not establish incident accuracy, cause, false-positive rate or capture overhead. Controlled, independently labeled runs remain the next acceptance step. Real Windows gameplay acceptance, scale limits and optional dependency reproducibility need further validation.

## Cross-platform CI evidence

[PR workflow run 43370022464](https://github.com/kauaaraujo-tech/visual-game-intelligence/actions/runs/43370022464) passed all six jobs on source commit `c562fa88ce3d9196ab7a37c6f8a244e4e09ab8f0`: Linux and Windows with Python 3.10, 3.12, and 3.13. Jobs exercise the 134-test suite with Pillow, standard-library-only checks (16 expected visual skips), editable installation, CLI smoke tests, compilation, and the public-content scanner.

An initial Windows run exposed a test assumption about short/long temporary-directory names. The test now compares actual file identity; diagnostic behavior was preserved. These are synthetic software checks on CI runners, not a Hookshot/gameplay trial or a measured diagnostic false-positive rate.

## Local Windows check — 2026-11-14

Python 3.14.6 on a Windows account without symbolic-link creation privileges
exposed two test assumptions: UTF-8 reports were read using the system's default
encoding, and three symlink fixtures required a privilege unavailable to an
ordinary local account. Tests now read reports explicitly as UTF-8 and skip
symlink checks only when fixture creation reports an unsupported capability or
permission error. Traversal and absolute-path rejection remain independently
tested. Application behavior and system privileges are unchanged.

The resulting suite ran **136 tests with zero failures or errors**: four symlink
checks were skipped. With Pillow 13.0.0, all 16 visual checks ran. A separate
standard-library-only run passed with 20 skips (16 visual, four symlink).
The self-test, installed CLI, native synthetic demo/analysis/acceptance, source
compilation and public-content scan passed. Symlink behavior was not validated
on this local account; the historical CI evidence above is a separate checkpoint.

A separate historical text-log snapshot produced JSON/Markdown with zero frame
samples and `insufficient_data`. This exercises context-only import; no real
frametime session, diagnostic accuracy, false-positive rate or capture overhead
was validated by this check.
