"""Conservative, offline analysis of normalized frame timing sessions.

Thresholds are operational heuristics, not statistical significance or causal
proof. Baselines are preceding local observations, never a hardware target.
"""
from __future__ import annotations

import copy
import math
from collections import Counter, deque
from statistics import median

_MIN_BASELINE = 12
_WINDOW = 60
_MAD_SCALE = 1.4826


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _frame_valid(frame):
    return (isinstance(frame, dict) and _integer(frame.get('frame_id'))
            and _integer(frame.get('t_ns')) and _number(frame.get('frame_ms'))
            and frame['frame_ms'] > 0)


def _end(frame):
    return frame['t_ns'] + max(1, round(frame['frame_ms'] * 1_000_000))


def _shared_clock(metadata):
    domain = metadata.get('clock_domain', '')
    if not isinstance(domain, str):
        return False
    domain = domain.strip().lower()
    return bool(domain and 'monotonic' in domain and not any(
        word in domain for word in ('unknown', 'uncalibrated', 'unshared', 'unverified')))


def _frame_uncertainty(frame):
    value = frame.get('uncertainty_ns', 0)
    return value if _integer(value) and value >= 0 else 0


def _percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (position - lower)


def _overlap(start, end, incident, start_uncertainty=0, end_uncertainty=0):
    if start == end:  # A timestamp denotes a point, using half-open frame intervals.
        return incident['start_ns'] - start_uncertainty <= start < incident['end_ns'] + end_uncertainty
    return start < incident['end_ns'] + end_uncertainty and end > incident['start_ns'] - start_uncertainty


def _evidence_interval(item, *, capture=False):
    timestamp = item.get('t_ns')
    if not _integer(timestamp):
        return None
    duration = item.get('duration_ms', 0) if not capture else 0
    if not _number(duration) or duration < 0:
        return None
    uncertainty = item.get('uncertainty_ns', 0)
    if not _integer(uncertainty) or uncertainty < 0:
        return None
    return timestamp, timestamp + round(duration * 1_000_000), uncertainty


def _associate(items, incidents, frames, shared_clock, warnings, *, capture=False, metadata=None):
    """Associate identity first; verify a supplied time against that identity.

    Duration extends an event's overlap, but only its start validates the frame
    identity: an event can legitimately begin before an incident and run into it.
    """
    linked = set()
    kind = 'Capture' if capture else 'Event'
    output_key = 'captures' if capture else 'events'
    record_key = 'capture' if capture else 'event'
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            warnings.append(f'{kind} at index {index} is malformed and was not associated.')
            continue
        metadata = metadata or {}
        if any(item.get(domain) is not None and item.get(domain) != metadata.get(domain) for domain in ('frame_domain', 'clock_domain')):
            warnings.append(f'{kind} at index {index}: explicit domain mismatch; retained as unjoined context.')
            continue
        identity = str(item.get('path' if capture else 'id', index))
        frame_id = item.get('frame_id')
        matched_frame = frames.get(frame_id) if _integer(frame_id) else None
        interval = _evidence_interval(item, capture=capture)
        uncertain_identity = False
        if shared_clock and matched_frame is not None and interval is not None:
            start, _, uncertainty = interval
            frame_uncertainty = _frame_uncertainty(matched_frame)
            nominal_agrees = (matched_frame['t_ns'] + frame_uncertainty <= start - uncertainty
                              and start + uncertainty < _end(matched_frame) - frame_uncertainty)
            possible_agrees = (start + uncertainty >= matched_frame['t_ns'] - frame_uncertainty
                               and start - uncertainty < _end(matched_frame) + frame_uncertainty)
            if not possible_agrees:
                warnings.append(f'{kind} {identity!r}: frame and timestamp disagree; no incident association was made.')
                continue
            uncertain_identity = not nominal_agrees
        for incident in incidents:
            association = None
            if matched_frame is not None and frame_id in incident['frame_ids']:
                association = 'exact_frame_uncertain' if uncertain_identity else 'exact_frame'
            elif shared_clock and interval is not None:
                start, end, uncertainty = interval
                first = frames.get(incident['frame_ids'][0], {})
                last = frames.get(incident['frame_ids'][-1], {})
                start_uncertainty = _frame_uncertainty(first)
                end_uncertainty = _frame_uncertainty(last)
                # A point's uncertainty window is closed at both ends.
                # Represent its inclusive upper nanosecond as a half-open end.
                expanded_end = end + uncertainty + int(bool(uncertainty) and start == end)
                if _overlap(start - uncertainty, expanded_end, incident, start_uncertainty, end_uncertainty):
                    if ((uncertainty or start_uncertainty or end_uncertainty)
                            and (not _overlap(start, end, incident)
                                 or start - uncertainty < incident['start_ns'] + start_uncertainty
                                 or end + uncertainty >= incident['end_ns'] - end_uncertainty)):
                        association = 'timestamp_uncertain'
                    else:
                        association = 'timestamp_overlap'
            if association:
                incident[output_key].append({record_key: copy.deepcopy(item), 'association': association})
                linked.add(index)
    return len(items) - len(linked)


def _hypotheses(incident, frame_map):
    evidence = [f'frame:{frame_id}' for frame_id in incident['frame_ids']]
    hypotheses = [{
        'id': incident['id'] + '-relative-degradation',
        'claim': 'Additional workload or waiting may explain this degradation relative to the preceding local baseline.',
        'status': 'hypothesis', 'confidence': 'low', 'evidence_ids': evidence,
        'next_test': 'Repeat the same scene with synchronized CPU/GPU timing and internal traces; compare incident frames with the preceding baseline.',
    }]
    event_rows = incident['events']
    if event_rows:
        uncertain = any('uncertain' in row['association'] for row in event_rows)
        event_ids = [str(row['event'].get('id', 'unidentified-event')) for row in event_rows]
        hypotheses.append({
            'id': incident['id'] + '-event-correlation',
            'claim': 'Associated internal events may be related to the slowdown; temporal association does not establish causation.',
            'status': 'hypothesis', 'confidence': 'low' if uncertain else 'medium',
            'evidence_ids': event_ids + evidence,
            'next_test': 'Inspect the associated event durations and repeat a controlled run with the suspected operation isolated or instrumented.',
        })
    investigations = {
        'pipe_wait_ms': ('shader_pipeline_wait', 'Blocking shader/pipeline availability is a concrete investigation candidate.',
                         'Repeat the same replay with separately recorded cold/warm cache state and identical build/driver; inspect pipeline wait counts and program-cache reuse. Do not infer unnecessary recompilation from this metric alone.'),
        'pipelines_ms': ('pipeline_creation', 'Pipeline creation work overlaps the slow interval and merits investigation.',
                         'Compare pipeline-creation durations and counts across repeated identical replays; isolate build/driver and cache-state changes.'),
        'translate_ms': ('shader_translation', 'Shader translation work overlaps the slow interval and merits investigation.',
                         'Compare translation counts and durations on repeated identical scenes; check cache-hit evidence and whether the same program keys recur.'),
        'gpu_behind_ms': ('gpu_backpressure', 'GPU backpressure waiting is an investigation candidate; it does not distinguish hardware capacity from inefficient rendering.',
                         'Repeat the scene at a lower render resolution with CPU/GPU busy timing, clocks and power recorded; compare waiting with GPU work and CPU submission.'),
        'slot_wait_ms': ('submission_slot_wait', 'Submission-slot waiting may indicate work queued behind earlier GPU submissions.',
                         'Record GPU busy timing and queue/slot occupancy over the same replay; compare affected and baseline frames at identical settings.'),
        'memsync_ms': ('memory_synchronization', 'Memory synchronization work overlaps the slowdown and merits investigation.',
                         'Compare memory synchronization, upload volume and late/readback waits on the same replay; do not sum overlapping aggregate timings.'),
        'readback_wait_ms': ('gpu_readback_wait', 'GPU readback waiting overlaps the slowdown and merits investigation.',
                         'Compare the same replay with instrumented readback reasons and capture settings; measure observer overhead before changing renderer behavior.'),
    }
    ranked = sorted(event_rows, key=lambda row: row['event'].get('duration_ms', 0), reverse=True)
    included = set()
    for row in ranked:
        event = row['event']; metric = event.get('kind'); duration = event.get('duration_ms', 0)
        if metric not in investigations or not _number(duration) or duration < max(5.0, (incident['peak_ms']-incident['baseline_ms'])*0.2):
            continue
        investigation, claim, next_test = investigations[metric]
        if investigation in included or len(included) >= 3:
            continue
        included.add(investigation)
        hypotheses.append({'id': incident['id']+'-'+investigation, 'investigation': investigation,
                           'claim': claim+' Aggregate durations can overlap; correlation is not causal proof.',
                           'status': 'hypothesis', 'confidence': 'low' if 'uncertain' in row['association'] else 'medium',
                           'evidence_ids': [event['id']]+evidence, 'observed_metric_ms': duration,
                           'next_test': next_test})
    incident_frames = [frame_map[frame_id] for frame_id in incident['frame_ids'] if frame_id in frame_map]
    if not incident_frames or any(not _number(frame.get('gpu_ms')) for frame in incident_frames):
        incident['limitations'].append('GPU busy timing is missing for some or all incident frames; hardware limits and port behavior cannot be distinguished from these data.')
    else:
        incident['limitations'].append('GPU busy timing alone cannot establish whether hardware limits or port behavior caused the degradation.')
    incident['hypotheses'] = hypotheses


def analyze(session: dict) -> dict:
    """Return a deterministic JSON-compatible diagnostic report without I/O.

    Warmup/menu/loading and recording discontinuities reset the local baseline.
    A slowdown needs at least 12 preceding samples and must exceed ratio,
    absolute, and robust dispersion guards simultaneously. A detected episode
    freezes its baseline until recovery, so a sustained drop cannot train away.
    """
    warnings = list(session.get('warnings', []))
    limitations = [
        'Thresholds are heuristic; an incident indicates relative degradation, not a proven cause.',
        'At least 12 preceding continuous gameplay frames are required; startup and changes before that baseline may be missed.',
    ]
    shared_clock = _shared_clock(session.get('metadata', {}))
    if not shared_clock:
        limitations.append('A shared monotonic clock is not established; only exact frame identities can associate evidence.')
    frames = session.get('frames', [])
    valid_frames = [frame for frame in frames if _frame_valid(frame)]
    identities = Counter(frame['frame_id'] for frame in valid_frames)
    frame_map = {frame['frame_id']: frame for frame in valid_frames if identities[frame['frame_id']] == 1}
    if any(count > 1 for count in identities.values()):
        warnings.append('Repeated frame identities cannot support exact evidence associations.')
    history = deque(maxlen=_WINDOW)
    incidents = []
    active = None
    previous = None
    analyzed_frames = 0
    qualified_frames = 0
    excluded_frames = 0
    discontinuities = 0

    for index, frame in enumerate(frames):
        if not _frame_valid(frame):
            warnings.append(f'Frame at index {index} is invalid; the preceding baseline was reset.')
            history.clear()
            previous = None
            active = None
            continue
        if frame.get('phase', 'gameplay') in ('warmup', 'menu', 'loading'):
            excluded_frames += 1
            history.clear()
            previous = None
            active = None
            continue
        analyzed_frames += 1
        if previous is not None:
            delta_ns = frame['t_ns'] - previous['t_ns']
            gap_limit_ns = max(50_000_000, round(previous['frame_ms'] * 3 * 1_000_000))
            if (frame['frame_id'] != previous['frame_id'] + 1
                    or delta_ns <= 0 or delta_ns > gap_limit_ns):
                discontinuities += 1
                history.clear()
                active = None
        previous = frame
        if active is None and len(history) < _MIN_BASELINE:
            history.append(frame['frame_ms'])
            continue
        qualified_frames += 1
        if active is not None:
            baseline = active['baseline_ms']
            threshold = active['threshold_ms']
        else:
            baseline = median(history)
            mad = median(abs(value - baseline) for value in history)
            # MAD can be zero in a discrete two-mode baseline. IQR keeps a
            # repeated high mode from becoming a spurious isolated anomaly.
            iqr_scale = (_percentile(history, 0.75) - _percentile(history, 0.25)) / 1.349
            dispersion = max(_MAD_SCALE * mad, iqr_scale)
            threshold = max(baseline * 1.5, baseline + 5.0,
                            baseline + 6 * dispersion)
        if frame['frame_ms'] > threshold:
            if active is None:
                active = {
                    'id': f'incident-{len(incidents) + 1:04d}',
                    'start_ns': frame['t_ns'], 'end_ns': _end(frame),
                    'frame_ids': [], 'baseline_ms': float(baseline),
                    'peak_ms': float(frame['frame_ms']), 'threshold_ms': float(threshold),
                    'events': [], 'captures': [], 'hypotheses': [],
                    'limitations': ['The local baseline is observational; scene or workload changes may explain a relative slowdown.'],
                }
                incidents.append(active)
            active['frame_ids'].append(frame['frame_id'])
            active['end_ns'] = _end(frame)
            active['peak_ms'] = max(active['peak_ms'], float(frame['frame_ms']))
        else:
            active = None
            history.append(frame['frame_ms'])

    events = session.get('events', [])
    captures = session.get('captures', [])
    unassociated_events = _associate(events, incidents, frame_map, shared_clock, warnings, metadata=session.get('metadata', {}))
    unassociated_captures = _associate(captures, incidents, frame_map, shared_clock, warnings, capture=True, metadata=session.get('metadata', {}))
    for incident in incidents:
        _hypotheses(incident, frame_map)
    if discontinuities:
        limitations.append('Recording gaps or frame-counter discontinuities reset the baseline and split incidents.')
    if unassociated_events:
        limitations.append('Unassociated events remain session context; untimed events were not assigned guessed timestamps.')
    return {
        'schema_version': 1, 'session_id': session.get('session_id', ''),
        'synthetic': bool(session.get('synthetic', False)),
        'status': 'incidents_detected' if incidents else ('no_anomaly' if qualified_frames else 'insufficient_data'),
        'incidents': incidents,
        'summary': {
            'total_frames': len(frames), 'analyzed_frames': analyzed_frames,
            'baseline_qualified_frames': qualified_frames, 'excluded_frames': excluded_frames,
            'invalid_frames': len(frames) - len(valid_frames),
            'incident_count': len(incidents), 'discontinuities': discontinuities,
            'unassociated_events': unassociated_events, 'unassociated_captures': unassociated_captures,
            'baseline_window_frames': _WINDOW, 'minimum_baseline_frames': _MIN_BASELINE,
        },
        'limitations': limitations, 'warnings': warnings,
    }
