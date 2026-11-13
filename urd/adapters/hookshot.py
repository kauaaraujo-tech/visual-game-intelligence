"""Offline parsers for public Hookshot exports, independently implemented.

Schemas inspected at upstream e9975d6c245275aaf89a34e8d17a6bbe8badab46.
This inspection pin does not verify the version of a user's executable.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from urd.model import safe_path, sha256_file, validate_session

SOURCE_COMMIT = "e9975d6c245275aaf89a34e8d17a6bbe8badab46"
DISPLAY_HEADER = ["frame", "time_s", "frametime_ms"]
PRESENT_HEADER = ["frame", "return_ns", "interval_ns", "present_begin_ns",
                  "renderer_begin_ns", "renderer_end_ns", "vcore_back_ns"]
PERFORMANCE_HEADER = ("frame,ms,pipe_waits,pipe_wait_ms,left_out,translate_ms,uploads,upload_mb,textures,"
                      "memsync_ms,pipelines_ms,uploads_ms,programs_ms,slot_wait_ms,gpu_behind_ms,draw_ms,"
                      "desc_ms,cmds_ms,tex_lookup_ms,textures_gone,late_wait_ms,readback_wait_ms,tex_frame_ms").split(",")
DISPLAY_UNCERTAINTY_NS = 50500


def _decimal(value: str, field: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {field}: {value!r}") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"Invalid {field}: {value!r}")
    return result


def _uint(value: str, field: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
        raise ValueError(f"Invalid {field}: {value!r}")
    result = int(value)
    if result > (1 << 64) - 1:
        raise ValueError(f"{field} exceeds uint64")
    return result


def _rows(root: Path, relative: str, header: list[str], session: dict):
    path = safe_path(root, relative)
    snapshot = path.read_bytes()
    with io.StringIO(snapshot.decode("utf-8-sig"), newline="") as stream:
        reader = csv.reader(stream, strict=True)
        if next(reader, None) != header:
            raise ValueError(f"{relative}: expected Hookshot header {','.join(header)}")
        for row in reader:
            if len(row) != len(header):
                raise ValueError(f"{relative}:{reader.line_num}: incomplete or extra CSV columns")
            yield reader.line_num, dict(zip(header, row))
    session["provenance"].append({"file": relative, "sha256": hashlib.sha256(snapshot).hexdigest()})


def _display(root: Path, relative: str, session: dict):
    previous_id = previous_end = None
    for line, row in _rows(root, relative, DISPLAY_HEADER, session):
        frame_id = _uint(row["frame"], "frame")
        end = _decimal(row["time_s"], "time_s") * 1_000_000_000
        duration = _decimal(row["frametime_ms"], "frametime_ms")
        duration_ns = duration * 1_000_000
        if previous_id is None:
            if frame_id != 0 or end != 0 or duration != 0:
                raise ValueError("Display CSV must begin with native frame 0 / zero-time sentinel")
            previous_id, previous_end = frame_id, end
            session["warnings"].append("Display first zero-duration sentinel omitted from frame analysis")
            continue
        if frame_id <= previous_id or end <= previous_end or duration <= 0:
            raise ValueError(f"{relative}:{line}: non-increasing frame/elapsed time or nonpositive interval")
        delta = end - previous_end
        if frame_id == previous_id + 1:
            if abs(delta - duration_ns) > 100500:
                raise ValueError(f"{relative}:{line}: duration inconsistent with rounded elapsed intervals")
        else:
            if duration_ns > delta + 100500:
                raise ValueError(f"{relative}:{line}: interval exceeds elapsed time across gap")
            session["warnings"].append(f"Display frame ID gap before {frame_id}; missing records not synthesized")
        start = int(end - duration_ns)
        if start < 0:
            if start < -DISPLAY_UNCERTAINTY_NS:
                raise ValueError(f"{relative}:{line}: interval begins before capture origin")
            start = 0
            session["warnings"].append("First interval start clamped to capture origin within rounding uncertainty")
        session["frames"].append({"frame_id": frame_id, "t_ns": start, "frame_ms": float(duration),
                                  "uncertainty_ns": DISPLAY_UNCERTAINTY_NS,
                                  "source": {"file": relative, "line": line}})
        previous_id, previous_end = frame_id, end
    session["warnings"].append(
        "Display intervals are CPU present-call/offscreen-submit intervals, not GPU completion or scanout; "
        "start estimates have 50500 ns rounding uncertainty")


def _performance(root: Path, relative: str, session: dict):
    elapsed = 0
    previous_id = None
    count = 0
    for line, row in _rows(root, relative, PERFORMANCE_HEADER, session):
        frame_id = _uint(row["frame"], "frame")
        values = {key: _decimal(value, key) for key, value in row.items() if key != "frame"}
        duration = values["ms"]
        if duration <= 0 or (previous_id is not None and frame_id <= previous_id):
            raise ValueError(f"{relative}:{line}: nonpositive interval or non-increasing frame ID")
        if previous_id is not None and frame_id != previous_id + 1:
            raise ValueError("Performance frame gap: missing interval lengths prevent a reconstructed timeline")
        frame = {"frame_id": frame_id, "t_ns": elapsed, "frame_ms": float(duration),
                 "uncertainty_ns": count * 5000, "phase": "warmup" if count == 0 else "unknown",
                 "source": {"file": relative, "line": line}}
        session["frames"].append(frame)
        # Metrics share this exact source row's identity. They have no measured onset within the interval.
        if count:
            for key, value in values.items():
                if key.endswith("_ms") and value > 0:
                    session["events"].append({"id": f"performance:{line}:{key}", "kind": key,
                        "message": f"Hookshot same-interval aggregate {key}={value} ms; not a causal attribution",
                        "frame_id": frame_id, "t_ns": None, "duration_ms": float(value),
                        "frame_domain": "hookshot.performance_frame", "source": frame["source"].copy()})
        elapsed += int(duration * 1_000_000)
        previous_id = frame_id
        count += 1
    session["warnings"].extend([
        "Performance timeline reconstructed by summing rounded ms intervals; no absolute monotonic timestamps exported. "
        "Start uncertainty accumulates 5000 ns per preceding row; interval duration uncertainty is 5000 ns",
        "First performance row marked warmup: metric deltas can aggregate startup; its diagnostic events omitted",
        "Performance counters share row identity but durations can overlap and do not prove a cause",
    ])


def _present_trace(root: Path, relative: str, session: dict):
    previous_frame = previous_return = None
    for line, row in _rows(root, relative, PRESENT_HEADER, session):
        values = {key: _uint(value, key) for key, value in row.items()}
        frame, returned, interval = values["frame"], values["return_ns"], values["interval_ns"]
        phases = [values[key] for key in PRESENT_HEADER[3:]] + [returned]
        if frame < 1 or any(a > b for a, b in zip(phases, phases[1:])):
            raise ValueError(f"{relative}:{line}: invalid native present phases")
        if previous_frame is not None:
            if frame <= previous_frame or returned <= previous_return:
                raise ValueError(f"{relative}:{line}: reversed present frame/clock")
            if frame == previous_frame + 1 and interval != returned - previous_return:
                raise ValueError(f"{relative}:{line}: inconsistent present interval")
        elif frame == 1 and interval != 0:
            raise ValueError("First native present interval must be zero")
        session["events"].append({"id": f"present-trace:{line}", "kind": "native_present_context",
            "message": "Unjoined HOS_PRESENT_TRACE " + json.dumps(values, sort_keys=True),
            "t_ns": None, "frame_id": None, "native": values,
            "source": {"file": relative, "line": line}})
        previous_frame, previous_return = frame, returned
    session["warnings"].append(
        "HOS_PRESENT_TRACE native game frame IDs and clock are uncalibrated to primary frame domain; "
        "records retained as unjoined context")


def _logs(root: Path, relative: str, session: dict):
    path = safe_path(root, relative)
    snapshot = path.read_bytes()
    with io.StringIO(snapshot.decode("utf-8-sig", errors="replace")) as stream:
        for line, text in enumerate(stream, 1):
            if text.strip():
                session["events"].append({"id": f"log:{line}", "kind": "log",
                    "message": text.rstrip("\r\n"), "t_ns": None, "frame_id": None,
                    "source": {"file": relative, "line": line}})
    session["provenance"].append({"file": relative, "sha256": hashlib.sha256(snapshot).hexdigest()})
    session["warnings"].append("Hookshot text logs have no monotonic timestamps; all lines retained as unjoined context")


def _captures(root: Path, manifest: dict, session: dict):
    from urd.adapters.bundle import load_captures
    load_captures(root, manifest, session)
    for capture in session["captures"]:
        for identity, domain in (("frame_id", "frame_domain"), ("t_ns", "clock_domain")):
            if capture.get(identity) is not None and capture.get(domain) != session["metadata"][domain]:
                capture["native_" + identity] = capture[identity]
                capture[identity] = None
                session["warnings"].append(f"Capture {capture['relative_path']} {identity} unjoined: "
                                           f"declare matching {domain} with verified alignment")
        capture.setdefault("frame_id", None)
        capture.setdefault("t_ns", None)
        capture.setdefault("uncertainty_ns", 0)
        if capture["frame_id"] is None and capture["t_ns"] is None:
            session["warnings"].append(f"Capture {capture['relative_path']} has no aligned identity; session context only")


def load_native(root: Path, manifest: dict) -> dict:
    """Load one native export clock domain, preserving unaligned evidence separately."""
    if manifest.get("schema_version") != 1 or type(manifest.get("synthetic")) is not bool:
        raise ValueError("Declare schema_version=1 and explicit synthetic boolean")
    if not isinstance(manifest.get("metadata"), dict):
        raise ValueError("metadata object is required")
    performance = manifest.get("performance_trace")
    display = manifest.get("frame_log")
    if bool(performance) == bool(display):
        raise ValueError("Provide exactly one primary: performance_trace or frame_log; their domains cannot be merged")
    metadata = dict(manifest["metadata"])
    metadata.update({"adapter": "hookshot", "parser_source_commit": SOURCE_COMMIT,
                     "native_build_verified": False,
                     "clock_domain": "hookshot.performance_reconstructed_monotonic" if performance else "hookshot.display_elapsed_monotonic",
                     "frame_domain": "hookshot.performance_frame" if performance else "hookshot.display_present"})
    session = {"schema_version": 1, "session_id": manifest.get("session_id"), "synthetic": manifest["synthetic"],
               "metadata": metadata, "frames": [], "events": [], "captures": [], "provenance": [],
               "warnings": ["Native parser schema inspected at " + SOURCE_COMMIT +
                            "; this does not verify the producing executable's build/version"]}
    if performance:
        _performance(root, performance, session)
    else:
        _display(root, display, session)
    if manifest.get("present_trace"):
        _present_trace(root, manifest["present_trace"], session)
    if manifest.get("log"):
        _logs(root, manifest["log"], session)
    _captures(root, manifest, session)
    if not session["frames"]:
        session["warnings"].append("No positive per-frame metrics available")
    return validate_session(session)
