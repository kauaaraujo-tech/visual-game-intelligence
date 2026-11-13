# VGI 0.1.1 — experimental audit summary

Audit date: 2026-11-13. The original MVP at commit `48f0047` was extracted separately and tested independently: **110 tests passed**. The updated VGI working tree passed **134 tests**, including regressions for both issues found during the audit. Core synthetic self-tests also passed with `python -S`, without site-packages.

Two correctness defects were reproduced and fixed: generic phase annotations were matched before CSV frame IDs were normalized, and event timestamp uncertainty was ignored during evidence association.

Standard-library trace observed **1,202/1,297 executable lines (92.6754%)** across original modules loaded in the test process. CLI subprocess execution is excluded from that denominator. This is line coverage, not branch coverage or a measure of diagnostic accuracy.

The architecture separates importers, normalized evidence, detection, reporting and optional visual/model assistance. Reviewed networking is an explicit loopback-only model request; core analysis performs no automatic external uploads. This was a scoped review, not a security certification or complete dependency audit.

**Real-game diagnostic accuracy remains unvalidated.** Log-only input correctly produces `insufficient_data`; successful import does not establish incident accuracy, cause, false-positive rate or capture overhead. Controlled, independently labeled runs remain the next acceptance step. Windows execution, scale limits and optional dependency reproducibility need further validation.
