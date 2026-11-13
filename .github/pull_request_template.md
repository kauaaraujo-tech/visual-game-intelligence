## Change

Describe the problem, the resulting behavior, and any limits to the evidence.

## Validation

- [ ] `python -S -m vgi self-test`
- [ ] `python -m unittest discover -s tests -v` (note whether Pillow was available)
- [ ] `python scripts/check_release.py`
- [ ] New behavior has a regression test where appropriate.

## Public evidence

- [ ] Added sessions, captures, traces, and reports are generated synthetic data with explicit markers.
- [ ] No game binaries, ROMs, copyrighted assets, private logs, credentials, or personal installation paths are included.
- [ ] Claims distinguish software tests, heuristic candidates, and observations from real runs.
- [ ] Any new third-party code or dependency has its license and attribution recorded.

The release check scans tracked working-tree files with finite patterns. Review
new files and history separately; a passing check does not establish permission
to redistribute data or guarantee the absence of secrets.
