# Normalized session v1

Plain dictionaries, JSON compatible. Python 3.10+, core stdlib. Paths stay local. No networking in analysis.

Session keys: schema_version=1, session_id (str), synthetic (bool, must propagate), metadata (dict), frames (list), events (list), captures (list), warnings (list[str]), provenance (list[{file,sha256}]). Metadata clock_domain must describe common monotonic clock. Adapter validates increasing unique frame_id and t_ns; duration finite positive, timing consistency; unknown clock means no temporal join.

Frame: frame_id (int), t_ns (int, monotonic frame start), frame_ms (float); optional cpu_ms, gpu_ms, gpu_util_pct, phase (gameplay/loading/menu/warmup), source ({file,line}).
Event: id (str), kind (str), message (str), t_ns (int or null), frame_id (int or null), duration_ms (optional float), source ({file,line}). Untimed events must not be assigned guessed timestamps.
Capture: path (local resolved str), t_ns (int or null), frame_id (int or null), uncertainty_ns (int default 0). Do not infer timing from filenames/mtime. Safe session-relative paths only.

Analysis API: urd.analysis.analyze(session: dict) -> dict.
Report keys schema_version=1, session_id, synthetic, status (incidents_detected/no_anomaly/insufficient_data), incidents (list), summary (dict), limitations (list[str]), warnings (list[str]).
Incident: id, start_ns, end_ns (includes last frame duration), frame_ids (list[int]), baseline_ms, peak_ms, threshold_ms, events (list[{event:dict,association:str}]), captures (list[{capture:dict,association:str}]), hypotheses (list[{id,claim,status:'hypothesis',confidence:'low'|'medium',evidence_ids:list[str],next_test}]), limitations (list[str]).
Event/capture exact frame join preferred; timestamp overlap only if shared monotonic clock; disagreement never yields exact join. Untimed events remain session context, outside incidents. Association within uncertainty window marked uncertain. No causal conclusions from correlation. Sustained slow hardware alone isn't abnormal relative degradation.
