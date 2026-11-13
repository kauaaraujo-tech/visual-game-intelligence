# Synthetic examples only

Every included session and image is generated software-test data. No real game result or real code fix is represented.

- SYNTHETIC-before / SYNTHETIC-after: native published Hookshot performance CSV schema, annotated fixed synthetic replay. The "after" data were manually generated with lower frame durations, not measured after applying a correction. SYNTHETIC-comparison.json demonstrates descriptive comparison.
- SYNTHETIC-before-report: performance incident, same-row internal pipeline-wait event, explicitly aligned artificial image, hypotheses, source pointer and hashes.
- SYNTHETIC-visual: five artificial checkerboard images with a localized flash. No timing incident is expected (insufficient baseline); SYNTHETIC-visual-report packages the visual candidate independently.
- SYNTHETIC-ai-brief.json: reduced evidence summary only, no real model inference.

From project root, reproduce into a new directory:

```text
python -m urd analyze examples/SYNTHETIC-before/session.json --visual --out NEW_BEFORE_REPORT
python -m urd analyze examples/SYNTHETIC-visual/session.json --visual --out NEW_VISUAL_REPORT
python -m urd compare examples/SYNTHETIC-before/session.json examples/SYNTHETIC-after/session.json --out NEW_COMPARISON.json
```

Pillow is needed for visual heuristic execution; otherwise status is unavailable. A report's own reproduction command assumes working from the directory containing its input manifest. Its relative capture paths refer to original session evidence; packaged incident/visual evidence uses report_image under evidence/.
