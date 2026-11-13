# Roadmap

VGI prioritizes work by diagnostic impact, evidence quality, and dependencies. Version 0.1.1 is experimental. The current implementation is local and adapter-based. Synthetic tests establish software behavior; controlled real-game validation remains open.

## Implemented foundations

| Capability | Current state | Remaining evidence |
|---|---|---|
| Native Hookshot and generic session import | Implemented with strict schemas, hashes, identity/clock checks | Controlled real recordings from identified builds |
| Relative incident detection and evidence reports | Implemented with explicit uncertainty, context, and hypothesis boundaries | Real-game sensitivity, false positives, and observer overhead |
| Conservative visual candidates | Implemented with optional Pillow and synthetic adjacent-frame cases | Dense real capture sequences with independently established identity |
| Controlled pair comparison | Implemented; missing controls or coverage return `inconclusive` | Repeated real A/B runs and noise characterization |
| Instrumentation source references | Implemented for supported native metric evidence at a pinned commit | Version-specific mappings as upstream formats change |
| Optional local model assistance | Reduced brief, loopback client, and response validation implemented | Real model inference and usefulness benchmark |
| Local acceptance orchestration | Read-only collection, analysis, and import/evidence checks in one command | Human review and controlled real-game diagnostic validation |
| VGI public entry point | Public naming over the existing URD core; compatibility retained | Ongoing compatibility checks as the API evolves |

## Next work and acceptance evidence

| Workstream | Dependencies | Evidence required before claiming completion |
|---|---|---|
| Controlled real Hookshot validation | A user-recorded closed session, identified build, stable baseline, repeatable scenario | Known incident and stable control; recorded misses/false positives; preserved hashes; instrumented versus uninstrumented overhead |
| Native binary `RX_VK_FRAMELOG` ingest | Version-pinned schema, record layout, sequence/wrap/drop handling, frame-kind preservation | Synthetic malformed/truncated cases and real recordings; no assumed equality with other frame counters |
| Cross-domain clock and identity calibration | Independently observable correspondences and uncertainty model | Verified mappings among game presents, display presents, renderer captures, and binary records; rejection of unsupported joins |
| CPU/GPU diagnosis experiments | Controlled replays, complementary busy-time/queue metrics, clocks and power conditions | Falsifiable resolution/cache/build/driver experiments that separate correlated waits from causal effects |
| Real local-model benchmark | Reviewed briefs, a locally configured model, real-session ground truth | Useful versus unsupported hypotheses, valid citations, reproducibility conditions, and actionable falsifiable tests |
| Repeated comparison workflows | Stable matched cohort collection and measured run-to-run variability | Alternating or randomized A/B repetitions; explicit uncertainty; no single-pair significance claims |
| Shader-cache reuse and invalidation investigation | Controlled cache-state recording, build/driver/program identity, repeatable scenarios, correlated compile/wait evidence | Explainable reuse/invalidation across updates and repeated cold/warm runs; no automatic cache deletion or claim of unnecessary recompilation from a wait metric alone |
| Additional project adapters | Demand, accessible format documentation, explicit legal/data boundaries | The same schema, provenance, clock, malformed-input, synthetic, and real-session acceptance criteria as the first adapter |

Shader-cache behavior after Hookshot updates is part of the diagnostic work, with priority determined by impact and the evidence it needs. It should use the same reusable collection, correlation, and controlled-comparison foundations; it has no artificial priority over them.

The project does not currently promise release dates, supported game lists, a verified fix, an always-running agent, or a live UI. Each CLI invocation terminates, and real-machine work that has not been performed stays explicitly pending.
