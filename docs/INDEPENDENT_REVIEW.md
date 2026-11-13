# Independent URD review

Reviewed 2026-11-13. Read CONTRACT, design, PROGRESS, all production modules and test files. No network, user PC access, or production edits. Independently ran `python -m unittest discover -s tests -q`: **97 tests passed**. Findings below were reproduced with local temporary synthetic inputs; they are software findings, not game evidence. Snapshot reviewed before any fixes arising from this review.

## Critical

None found. Literal `127.0.0.1` HTTP transport avoids proxy environment, DNS, and redirects. No automatic external upload, game launch, or source blame was found. Paths reject absolute paths, traversal, and resolved symlink escapes in ordinary non-racing use.

## Important

### 1. Generic evidence silently joins explicitly mismatched domains

Location: `urd/adapters/bundle.py:_load_generic/load_captures`, `urd/analysis.py:_associate`.

Reproduction: generic manifest metadata `{clock_domain: "display.monotonic", frame_domain: "display.frame"}`, continuous frames 0–14 (16 ms baseline, frame 12 = 80 ms, starts summed from durations). Supply events `{id:"wrong-frame-domain",kind:"wait",frame_id:12,frame_domain:"native.game"}` and `{id:"wrong-clock-domain",kind:"wait",t_ns:193000000,clock_domain:"unrelated.monotonic"}`. Supply capture `{path:"image.png",frame_id:12,frame_domain:"native.game"}`.

Actual: events associate `exact_frame` and `timestamp_overlap`, capture associates `exact_frame`, with **no warnings**. These are explicitly different identity/clock domains. Hookshot's capture importer checks domains, but the generic route and common association engine do not. This can attribute native game events/captures to display-frame incidents by numeric coincidence.

Recommended behavior: preserve conflicting records as unjoined context with warnings (or reject the bundle), checking both identities independently before any association. Enforce this centrally so direct normalized API callers receive the same protection.

### 2. Generic importer does not validate duration/start consistency

Location: `urd/model.py:validate_session` frame loop; `urd/analysis.py:analyze` discontinuity handling.

Reproduction: CSV `frame_id,t_ns,frame_ms`, rows 0–14, every start `i*16000000`, every duration 16 except frame 12 duration 80. Frame 12 therefore begins 192 ms and allegedly ends 272 ms, but frame 13 starts 208 ms.

Actual: `load_session` accepts the overlapping/inconsistent timeline with no warning; analysis reports incident [192,272) ms. Timestamp-only events during later healthy frames can consequently be associated with the supposed slowdown. This violates CONTRACT's explicit timing consistency requirement. Native parsers perform stronger checks, so generic input is the vulnerable route.

Recommended behavior: validate start/duration relationships across consecutive frames with explicit uncertainty tolerance; detect impossible overlaps and recording discontinuities instead of manufacturing an incident interval that covers later frames. Preserve allowed genuine missing-frame gaps without synthesizing rows.

### 3. Generic frame uncertainty remains a string and is silently ignored

Location: `urd/model.py:validate_session` frame loop; `urd/analysis.py:_frame_uncertainty`.

Reproduction: valid continuous generic frame CSV with additional `uncertainty_ns` column containing `20000000` (20 ms). Frame 12 starts 192 ms, lasts 80 ms; event `{id:"timed",kind:"wait",frame_id:12,t_ns:193000000}`.

Actual: frame uncertainty remains Python `str`; association is `exact_frame`. Change only that normalized value to integer `20000000`, and the same analyzer returns `exact_frame_uncertain`. Negative/noninteger frame uncertainty is also never rejected. CSV scalar normalization supports duration/identity fields but omits the uncertainty used by association and comparison algorithms.

Recommended behavior: normalize and validate optional frame `uncertainty_ns` as a nonnegative integer, just like captures, and add a real importer-to-analyzer regression test.

### 4. Provenance hashes can describe bytes different from analyzed/copied evidence

Locations: `urd/adapters/bundle.py` reads then later `sha256_file`; `urd/adapters/hookshot.py:_rows/_logs`; `urd/report.py:write_report`; similarly `urd/visual.py` hashes before a distinct decode open.

Two deterministic race simulations reproduced using local mocks of existing hash calls:

* Generic CSV initially has one 16 ms frame. Patch bundle's `sha256_file` wrapper to change that file to 80 ms immediately before hashing it. Import returns analyzed duration **16 ms**, and provenance hash matches **80 ms** file bytes. Replaying exactly the hashed input does not reproduce the analyzed session. Manifest and native inputs have the same read-then-hash structure.
* Associated image initially contains original bytes. Patch report's `sha256_file` wrapper to compute/return its original digest, then replace the file before returning. `write_report` succeeds, copying replacement bytes under the original digest filename; actual output SHA256 differs from the filename and provenance. Existing stale-file check only closes the before-hash race.

These mocks emulate a writer or symlink replacement between separate opens; no malformed fixture or production modifications are needed. Collector's size/mtime check does not extend to general imports or report copying.

Recommended behavior: parse/hash a single captured byte snapshot (bounded/streamed as appropriate), and copy/hash the same stream or validate destination bytes before publishing output. Visual decoding should consume the byte snapshot whose hash it records. Atomic output assembly avoids leaving apparently usable partial reports on validation failure.

## Lower-priority limits and usability gaps

* `write_report` copies incident-associated images only. Visual candidates with no timing incident retain absolute source paths and hashes in JSON, but their images are not copied; moving a visual-only report makes visual evidence inaccessible. Existing Markdown does not render candidate evidence images. Prefer packaging visual-candidate images too, rewriting their portable references.
* Reproduction command is always `python -m urd analyze session.json ...` even when actual manifest filename differs; `input_manifest` records the right name but command does not use it. Report bundle does not itself include raw metrics/manifest; reproduction still requires original files, as requirements partly acknowledge.
* Hookshot performance importer marks every post-start frame phase `unknown`; comparison selects only `gameplay`. Thus direct native performance before/after sessions cannot become comparable regardless of complete control metadata. Conservative, but document the limitation or offer explicit declared cohort selection without pretending phases were measured.
* Collector error says output must be outside input evidence, but `source.is_relative_to(target)` rejects parents and allows `target` below the source directory. Explicitly supplied `game_dir/new-output` modifies the source tree, contrary to the apparent outside-input/read-only promise. Choose a consistent documented policy or reject descendant targets too.
* Reduced AI brief omits designated path/message fields, but arbitrary event IDs/kinds can still contain paths or proprietary text. Current literal loopback transport remains local, so this is a truthfulness/minimization limitation, not an external disclosure found in this review.
* No statistical-significance overclaim was found: required matched metadata, declared scenario coverage, sample minimum, continuity checks, explicit descriptive effects, and repetition caveats are present. Native schema/build remains explicitly unverified. No real-game validation was performed.
