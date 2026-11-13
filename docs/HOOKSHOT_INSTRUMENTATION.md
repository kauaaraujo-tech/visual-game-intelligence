# Hookshot instrumentation evidence (2026-11-13)

Public primary repository: https://github.com/NotRexed/Hookshot . HookshotBuilder is in the same repository (`builder/HookshotBuilder/HookshotBuilder.csproj`), not a separate instrumentation SDK. Inspected immutable main snapshot **e9975d6c245275aaf89a34e8d17a6bbe8badab46**, authored 2026-11-13T01:54:56Z. This is an inspection pin, not a supported release recommendation. Public selected files are in `recon/hookshot/`; no game files or executable were obtained or run.

## Verified exports

| Export | Actual schema / meaning | Evidence at the pinned commit |
|---|---|---|
| `RX_VK_FRAME_LOG=<csv>` | Header `frame,time_s,frametime_ms`. Independent uint64 frame counter starts 0; first row `0,0.0000,0.000`; `time_s` elapsed from first sample (4 decimals); `frametime_ms` previous-to-current CPU interval (3 decimals). `steady_clock`. Flush every 60 records. | `gpu/vk/vk_replay.cpp:3287-3303` |
| `HOS_PRESENT_TRACE=<csv>` | Header `frame,return_ns,interval_ns,present_begin_ns,renderer_begin_ns,renderer_end_ns,vcore_back_ns`. Game's 1-based native present counter; first interval 0. Values from `hos_now_ns`. Buffered, flush every second. CPU wall phases before queue flush, around renderer call, after virtual-core reacquisition, return. Async renderer call measures enqueue. | `host/nn_vi.c:453-510`; `host/nvn_native.c:2493-2515` |
| `RX_VK_FRAME_TRACE=1` | `hookshot_frames.csv` beside game. Header `frame,ms,pipe_waits,pipe_wait_ms,left_out,translate_ms,uploads,upload_mb,textures,memsync_ms,pipelines_ms,uploads_ms,programs_ms,slot_wait_ms,gpu_behind_ms,draw_ms,desc_ms,cmds_ms,tex_lookup_ms,textures_gone,late_wait_ms,readback_wait_ms,tex_frame_ms`. `ms` is an interval, NOT timestamp. Counters/per-category accumulated duration deltas, not causal proof or mutually exclusive times. Independent counter; no absolute monotonic stamp. | `gpu/vk/vk_replay.cpp:3214-3264` |
| `RX_VK_FRAMELOG=<file>` | Binary fixed records: little-endian `u64 time_ns,u32 sequence,u32 kind` then **320×180×4 RGBA**; 230416 bytes each. `kind=0` game, 1 generated. `<file>.go` gates recording. `sequence` uint32 wrap possible. Three GPU readback slots, worker writes; timestamp taken at capture via `host->now_ns`. | `gpu/vk/vk_replay.cpp:3814-4000,4161`; `scripts/framelog.py:22-64`; `tests/test_framelog_clock.py` |
| Human log | `[hos <thread-name>] <message>\n`; body truncated to bounded buffers, no timestamp in line format. Vulkan delegates through host logger. Icon launch uses `hookshot_log.txt`, retains four older logs; terminal behavior differs. | `host/hos_thread.c:304-323`; `gpu/vk/vk_main.cpp:111-121`; `host/hos_main.c:1758-1785` |
| Local control bridge | Opt-in `HOS_CONTROL`, JSONL protocol 1 on Unix socket (Linux) / named pipe (Windows), local user only, no TCP. `status`, `subscribe` events `present,state,log,map` and `log_dropped`; `shot` PNG response includes renderer `present`, current game `frame`, dimensions/path. Replies have `id,ok,frame`. | `docs/control.md`; `host/control.c` |

Source link prefix: https://github.com/NotRexed/Hookshot/blob/e9975d6c245275aaf89a34e8d17a6bbe8badab46/ (append each path above; GitHub `#L3287` etc anchor exact lines).

## Clock and identity limits

`hos_now_ns` uses QueryPerformanceCounter/frequency (host/hos_thread.c:1050). Control uses QPC on Windows and CLOCK_MONOTONIC on Linux (`host/control.c:72-88`). RX_VK_FRAME_LOG uses C++ steady_clock, has a different origin, and only exports elapsed time. Never assume its numeric IDs equal native game presents, renderer `presents`, binary sequences, or `status_tick` IDs. Display frame log is called from `present_finish`, including generated presentations, and headless after offscreen submission (`vk_replay.cpp:3805,4333`). It is NOT GPU completion or scanout measurement; even errors can reach `present_finish`. Control `frame` counts game presents; framegen excluded. Control `shot.present` is renderer count. Binary only has sequence and kind, not a game frame ID. No defensible exact cross-file join exists from matching integers alone.

Preserve quantization: elapsed time printed to 0.1 ms; interval printed to 0.001 ms. For interval analysis derive start as elapsed minus interval, skip first zero interval, attach rounding uncertainty. Do not label elapsed time a Unix timestamp. Native present trace has absolute monotonic ns, but no export correlating it to the display CSV origin. Untimestamped text logs remain session context. Do not join screenshot names or mtime.

## Screenshots and debug capabilities

`RX_VK_SHOTS=<dir>` writes `vk_<present>.png` every `RX_VK_SHOT_EVERY` (default 300) at default 1280×720 (`RX_VK_SHOT_W/H`). `RX_VK_DUMP` emits per-step PNGs; `RX_VK_PASS_TRACE`, `RX_VK_PROBE`, `RX_VK_VALIDATION`, checkpoint/device-loss reports, `RX_VK_PASS_TIMING`, CPU samplers `HOS_PROFILE/HOS_SAMPLE/HOS_SAMPLE_ALL`, wait/signal chain `HOS_CHAIN` already exist. Details are in `docs/development.md`; scripts include `run-vk.ps1`, `prof.py`, `vkprof.py`, `chain.py`, `framelog.py`, `hookshot_ctl.py`. Do not import game-derived shader/native program dumps into a shareable report automatically. `shot` is a write request and control also exposes input/settings/memory-write/exit, so an observational adapter should avoid invoking those commands.

## License

README explicitly identifies **GPL-3.0-or-later**; root LICENSE is GPLv3 text. Third-party folders keep their notices. Independent file-format adapter can cite provenance and implement observed parsing; copying upstream implementation would need license consideration. No upstream source is copied into adapter production code.

## Smallest useful adapter

Offline ingest `RX_VK_FRAME_LOG` with exact current header and strict decimal validation, hash original source, derive local frame intervals with rounding uncertainty, skip zero sentinel. Keep `HOS_PRESENT_TRACE` phases and ordinary log as unjoined source context unless explicit clock calibration/identity evidence is provided. Allow only explicitly supplied capture metadata and safe session-relative paths. Optional next increment: binary capture reader with fixed-record checks, monotonic timestamp validation and modular sequence gaps, retaining kind; do not infer sequence equals display CSV frame. No app/network hooks or user-PC access required. Fixture tests can reproduce public export *formats* using synthetic data, clearly tagged synthetic, without shipping game data.

Implemented increment: `performance_trace` can alternatively select native `hookshot_frames.csv` as primary, enabling exact same-row association of positive metric durations with that row's frame ID. Its timeline is explicitly **reconstructed** by cumulative rounded `ms`, with accumulating 5000 ns per preceding interval; no absolute clock is invented. First row marked warmup and its metric events omitted because initial counter deltas can aggregate startup. `performance_trace` and `frame_log` are mutually exclusive; separate sessions avoid unsupported cross-domain joins. Metadata uses `hookshot.performance_frame` / `hookshot.performance_reconstructed_monotonic`, or `hookshot.display_present` / `hookshot.display_elapsed_monotonic`. Supplied captures need a matching explicitly declared frame/clock domain before identity joins are allowed. The parser source pin describes inspected schema, never verifies a user's build. Implemented native tests: 15; broader suite at handoff: 51 passing. Binary image capture ingest remains deferred.

Downloaded `recon/hookshot` source is temporary research evidence. Exclude it from the independent MIT tool's distributed archive; include this source map/links instead.

Web discovery sources: `turn0search0` official repository, `turn0search2` same-repo HookshotBuilder solution. Direct GitHub API confirmed commit and exact source. A parent response wishing to cite web refs must reopen relevant official URLs itself.
