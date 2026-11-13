"""Bounded offline image heuristics: candidates for review, never bug verdicts."""
from __future__ import annotations

import copy
import hashlib
import io
import math
from collections import Counter
from pathlib import Path
from statistics import pstdev

from urd.model import sha256_file

_MAX_IMAGES = 128
_MAX_IMAGE_PIXELS = 16_777_216
_MAX_TOTAL_PIXELS = 67_108_864
_MAX_FILE_BYTES = 67_108_864
_GRID = (16, 9)
_LIMITATIONS = [
    "Luminance-grid heuristics identify visual candidates, not rendering bugs or their causes.",
    "Loading, fades, exposure changes, effects, menus, and intentional stillness can resemble anomalies.",
    "Only consecutive explicitly identified frames are compared; filenames and mtime never establish chronology.",
    "A 16x9 luminance grid can miss small, color-only, HUD, and spatially cancelling defects.",
    "No candidate does not establish visual correctness; sparse capture cannot resolve a one-frame event.",
]


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _distance(left, right):
    return sum(abs(a - b) for a, b in zip(left, right)) / len(left)


def _textured(grid):
    return max(grid) - min(grid) >= 25 and pstdev(grid) >= 8


def _black(grid):
    return sum(value <= 8 for value in grid) / len(grid) >= 0.98 and sum(grid) / len(grid) <= 5


def _reference(sample, synthetic):
    result = copy.deepcopy(sample["capture"])
    result.update(capture_index=sample["index"], sha256=sample["sha256"], synthetic=synthetic)
    return result


def _candidate(result, kind, samples, metrics, explanation):
    result["candidates"].append({
        "id": f"visual-{len(result['candidates']) + 1:04d}", "kind": kind,
        "status": "candidate_not_proven", "confidence": "low", "synthetic": result["synthetic"],
        "evidence": [_reference(sample, result["synthetic"]) for sample in samples],
        "metrics": metrics, "limitations": [explanation,
            "Dense surrounding captures and a controlled replay are needed to distinguish intended content from a defect."],
    })


def _segments(samples, result):
    segments = []
    for sample in samples:
        if not segments:
            segments.append([sample])
            continue
        previous = segments[-1][-1]
        if sample["capture"]["frame_id"] != previous["capture"]["frame_id"] + 1:
            result["warnings"].append("Sparse/nonadjacent frame identities split visual comparisons")
            segments.append([sample])
        elif sample["size"] != previous["size"]:
            result["warnings"].append("Image size changed; cross-size comparisons omitted")
            segments.append([sample])
        else:
            segments[-1].append(sample)
    return segments


def _inspect(segment, result, expected_motion):
    # Persistent black requires three dark frames and textured nonblack frames on both sides.
    index = 0
    while index < len(segment):
        if not _black(segment[index]["grid"]):
            index += 1
            continue
        end = index + 1
        while end < len(segment) and _black(segment[end]["grid"]):
            end += 1
        if end - index >= 3 and index > 0 and end < len(segment):
            before, after = segment[index - 1], segment[end]
            if _textured(before["grid"]) and _textured(after["grid"]):
                _candidate(result, "persistent_black", segment[index - 1:end + 1],
                           {"black_frames": end - index, "black_cell_fraction_min": 0.98},
                           "A bracketed black interval can be an intentional fade, loading screen, or transition.")
        index = end

    # A whole-image flash is indistinguishable here from exposure/effects/cuts; only local returns are candidates.
    for index in range(1, len(segment) - 1):
        before, current, after = segment[index - 1:index + 2]
        a, b, c = before["grid"], current["grid"], after["grid"]
        if not (_textured(a) and _textured(c)) or _distance(a, c) > 3:
            continue
        changed = [n for n, (x, y, z) in enumerate(zip(a, b, c))
                   if abs(x - z) <= 5 and abs(y - (x + z) / 2) >= 65]
        fraction = len(changed) / len(a)
        if fraction > 0.30:
            result["warnings"].append("Global one-frame luminance change remains ambiguous (cut, exposure, or effect)")
        elif len(changed) >= 2:
            _candidate(result, "isolated_local_flash", [before, current, after],
                       {"changed_grid_cells": len(changed), "changed_fraction": round(fraction, 6),
                        "neighbor_mean_absolute_difference": round(_distance(a, c), 6)},
                       "A local one-frame luminance change can be a legitimate effect or moving object.")

    if not expected_motion:
        return
    # A repeated textured run is interesting only when the producer explicitly expected motion.
    index = 0
    while index < len(segment):
        end = index + 1
        while end < len(segment) and _distance(segment[index]["grid"], segment[end]["grid"]) <= 0.5:
            end += 1
        if end - index >= 3 and index > 0 and end < len(segment) and _textured(segment[index]["grid"]):
            if (_distance(segment[index - 1]["grid"], segment[index]["grid"]) >= 8
                    and _distance(segment[end]["grid"], segment[index]["grid"]) >= 8):
                _candidate(result, "repeated_during_expected_motion", segment[index - 1:end + 1],
                           {"repeated_frames": end - index, "expected_motion_declared": True},
                           "Expected motion is a manifest assertion; repeated frames can be intentional or missed by this grid.")
        index = end


def analyze_visual(session: dict) -> dict:
    """Inspect local captures without network, writes, or inferred capture ordering.

    ``metadata.expected_motion=True`` enables repeat candidates. Frame IDs must
    represent adjacent normalized frames; ``capture_stride>1`` is sparse and is
    not eligible. Explicit mismatching domains, generated kinds, excluded phases,
    duplicate identities, and mixed synthetic markers are omitted from comparisons.
    """
    result = {"schema_version": 1, "session_id": session.get("session_id"),
              "synthetic": session.get("synthetic"), "status": "insufficient_data", "candidates": [],
              "summary": {"captures_seen": len(session.get("captures", [])), "images_read": 0,
                          "eligible_images": 0, "adjacent_triplets": 0},
              "limitations": list(_LIMITATIONS), "warnings": []}
    if type(session.get("synthetic")) is not bool:
        raise ValueError("Visual analysis requires explicit synthetic boolean")
    try:
        from PIL import Image
    except ImportError:
        result["status"] = "unavailable"
        result["warnings"].append("Optional Pillow is unavailable; no image analysis performed")
        return result

    metadata = session.get("metadata", {})
    captures = session.get("captures", [])
    if len(captures) > _MAX_IMAGES:
        result["warnings"].append(f"Capture count limit: inspecting at most {_MAX_IMAGES} images")
    if metadata.get("capture_stride", 1) != 1:
        result["warnings"].append("Sparse capture_stride cannot establish adjacent-frame visual events")
        return result
    phases = {frame.get("frame_id"): frame.get("phase") for frame in session.get("frames", [])
              if isinstance(frame, dict)}
    frame_info = {frame.get("frame_id"): frame for frame in session.get("frames", [])
                  if isinstance(frame, dict)}
    clock = str(metadata.get("clock_domain", "")).lower()
    shared_clock = "monotonic" in clock and not any(word in clock for word in
                   ("unknown", "uncalibrated", "unshared", "unverified"))
    identities = Counter(capture.get("frame_id") for capture in captures
                         if isinstance(capture, dict) and _integer(capture.get("frame_id")))
    provenance = {entry.get("file"): entry.get("sha256") for entry in session.get("provenance", [])
                  if isinstance(entry, dict)}
    samples = []
    pixels_read = 0
    for index, capture in enumerate(captures[:_MAX_IMAGES]):
        if not isinstance(capture, dict) or not _integer(capture.get("frame_id")):
            result["warnings"].append(f"Capture {index} lacks explicit frame identity; chronology not inferred")
            continue
        frame_id = capture["frame_id"]
        if identities[frame_id] != 1:
            result["warnings"].append(f"Duplicate capture frame identity {frame_id}; samples omitted")
            continue
        if "synthetic" in capture and capture["synthetic"] != session["synthetic"]:
            result["warnings"].append(f"Capture {index} mixed synthetic marker; omitted")
            continue
        if capture.get("frame_domain") is not None and capture["frame_domain"] != metadata.get("frame_domain"):
            result["warnings"].append(f"Capture {index} frame domain does not match normalized session")
            continue
        if (capture.get("clock_domain") is not None and capture.get("t_ns") is not None
                and capture["clock_domain"] != metadata.get("clock_domain")):
            result["warnings"].append(f"Capture {index} clock domain disagrees; identity left ambiguous")
            continue
        frame = frame_info.get(frame_id, {})
        timestamp, start, duration = capture.get("t_ns"), frame.get("t_ns"), frame.get("frame_ms")
        if (shared_clock and _integer(timestamp) and _integer(start)
                and isinstance(duration, (int, float)) and not isinstance(duration, bool)
                and math.isfinite(duration) and duration > 0):
            uncertainty = capture.get("uncertainty_ns", 0)
            uncertainty = uncertainty if _integer(uncertainty) else 0
            frame_uncertainty = frame.get("uncertainty_ns", 0)
            frame_uncertainty = frame_uncertainty if _integer(frame_uncertainty) else 0
            end = start + round(duration * 1_000_000)
            if not (start + frame_uncertainty <= timestamp - uncertainty
                    and timestamp + uncertainty < end - frame_uncertainty):
                result["warnings"].append(f"Capture {index} timestamp/frame identity disagree or overlap uncertain boundaries")
                continue
        kind = capture.get("frame_kind", capture.get("kind"))
        if kind is not None and (isinstance(kind, bool) or kind not in (0, "0", "game", "native")):
            result["warnings"].append(f"Capture {index} generated/unknown frame kind omitted")
            continue
        framegen = bool(metadata.get("frame_generation") or metadata.get("framegen"))
        if (framegen or metadata.get("frame_domain") == "hookshot.display_present") and kind is None:
            result["warnings"].append(f"Capture {index} frame generation sample kind unavailable; comparison ambiguous")
            continue
        if phases.get(frame_id) in ("loading", "menu", "warmup"):
            result["warnings"].append(f"Capture {index} excluded {phases[frame_id]} phase")
            continue
        try:
            path = Path(capture["path"])
            if not path.is_file() or path.stat().st_size > _MAX_FILE_BYTES:
                raise ValueError("missing file or file byte limit exceeded")
            snapshot = path.read_bytes()
            if len(snapshot) > _MAX_FILE_BYTES:
                raise ValueError("file byte limit exceeded")
            digest = hashlib.sha256(snapshot).hexdigest()
            expected = provenance.get(capture.get("relative_path"))
            if expected and expected != digest:
                raise ValueError("image bytes changed after ingestion")
            with Image.open(io.BytesIO(snapshot)) as image:
                width, height = image.size
                pixels = width * height
                if width < _GRID[0] or height < _GRID[1] or pixels > _MAX_IMAGE_PIXELS:
                    raise ValueError("image pixel/size limit exceeded or image smaller than grid")
                if pixels_read + pixels > _MAX_TOTAL_PIXELS:
                    result["warnings"].append("Total decoded pixel limit reached; remaining images omitted")
                    break
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("animated/multi-frame image unsupported")
                pixels_read += pixels
                grid = tuple(image.convert("L").resize(_GRID, Image.Resampling.BOX).tobytes())
                result["summary"]["images_read"] += 1
            samples.append({"capture": capture, "grid": grid, "size": (width, height),
                            "sha256": digest, "index": index})
        except (OSError, ValueError, KeyError, TypeError, Image.DecompressionBombError) as exc:
            result["warnings"].append(f"Capture {index} unreadable/unsupported: {type(exc).__name__}")
    samples.sort(key=lambda sample: sample["capture"]["frame_id"])
    result["summary"]["eligible_images"] = len(samples)
    for segment in _segments(samples, result):
        result["summary"]["adjacent_triplets"] += max(0, len(segment) - 2)
        _inspect(segment, result, metadata.get("expected_motion") is True)
    if result["candidates"]:
        result["status"] = "candidates_detected"
    elif result["summary"]["adjacent_triplets"]:
        result["status"] = "no_candidate"
    result["warnings"] = list(dict.fromkeys(result["warnings"]))
    return result
