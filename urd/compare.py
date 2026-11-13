"""Descriptive comparisons of explicitly matched offline workload cohorts.

No cross-session timestamp joins or inferential significance tests are made.
Replay coverage is declared metadata, independently of measured runtime.
"""
from __future__ import annotations

import json
import math
from statistics import median

REQUIRED_CONDITIONS = (
    'scenario', 'hardware', 'settings', 'run_group', 'collector', 'sample_kind',
    'cache_state', 'driver', 'power_profile', 'frame_generation', 'replay',
)
MIN_SAMPLES = 30


def _number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _known(value):
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in ('', 'unknown', 'unspecified', 'unverified', 'unset')
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, dict):
        return bool(value) and all(isinstance(key, str) and _known(item) for key, item in value.items())
    if isinstance(value, list):
        return bool(value) and all(_known(item) for item in value)
    return False


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _quantile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (position - lower)


def _coverage(session, label, reasons):
    metadata = session.get('metadata', {})
    declared_range = metadata.get('scenario_frame_range')
    valid_range = (isinstance(declared_range, list) and len(declared_range) == 2
                   and all(_integer(value) and value >= 0 for value in declared_range)
                   and declared_range[1] >= declared_range[0])
    if not valid_range:
        reasons.append(f'{label}: scenario_frame_range must declare an inclusive nonnegative gameplay ordinal range.')
    declared_duration = metadata.get('scenario_duration_ms')
    valid_duration = _number(declared_duration) and declared_duration > 0
    if not valid_duration:
        reasons.append(f'{label}: scenario_duration_ms must declare positive finite replay/simulation coverage, independently of runtime.')
    raw = session.get('frames', [])
    if not isinstance(raw, list):
        reasons.append(f'{label}: frames must be a normalized list.')
        raw = []
    selected = []
    indices = []
    for index, frame in enumerate(raw):
        if not isinstance(frame, dict):
            reasons.append(f'{label}: malformed frame at index {index}.')
            continue
        if frame.get('phase', 'gameplay') != 'gameplay':
            continue
        selected.append(frame)
        indices.append(index)
    values = []
    usable = True
    for index, frame in enumerate(selected):
        if (not _number(frame.get('frame_ms')) or frame['frame_ms'] <= 0
                or not _integer(frame.get('frame_id')) or frame['frame_id'] < 0
                or not _integer(frame.get('t_ns')) or frame['t_ns'] < 0):
            reasons.append(f'{label}: invalid gameplay frame at cohort index {index}; samples were not silently dropped.')
            usable = False
            continue
        values.append(float(frame['frame_ms']))
    if len(selected) < MIN_SAMPLES:
        reasons.append(f'{label}: at least {MIN_SAMPLES} gameplay samples are required.')
    if valid_range and len(selected) != declared_range[1] - declared_range[0] + 1:
        reasons.append(f'{label}: gameplay sample count does not cover scenario_frame_range exactly.')
    if indices and indices != list(range(indices[0], indices[-1] + 1)):
        reasons.append(f'{label}: gameplay cohort is interrupted by other phases; compare separate matched cohorts.')
    if usable:
        discontinuity = False
        for previous, current in zip(selected, selected[1:]):
            delta_ms = (current['t_ns'] - previous['t_ns']) / 1_000_000
            uncertainty_ms = sum(frame.get('uncertainty_ns', 0) for frame in (previous, current)
                                 if _integer(frame.get('uncertainty_ns', 0)) and frame.get('uncertainty_ns', 0) >= 0) / 1_000_000
            tolerance_ms = max(0.1, previous['frame_ms'] * 0.01) + uncertainty_ms
            if (current['frame_id'] != previous['frame_id'] + 1 or delta_ms <= 0
                    or abs(delta_ms - previous['frame_ms']) > tolerance_ms):
                discontinuity = True
                break
        if discontinuity:
            reasons.append(f'{label}: frame identities or timing contain a gap/reset; workload coverage is not continuous.')
    try:
        runtime = math.fsum(values) if usable else None
        if runtime is not None and not math.isfinite(runtime):
            raise OverflowError
    except OverflowError:
        runtime = None
        reasons.append(f'{label}: total recorded duration is not finite.')
    result = {
        'samples': len(selected), 'excluded_samples': len(raw) - len(selected),
        'scenario_frame_range': list(declared_range) if valid_range else None,
        'scenario_duration_ms': float(declared_duration) if valid_duration else None,
        'recorded_duration_ms': runtime,
    }
    return values, result


def compare_sessions(before: dict, after: dict) -> dict:
    """Compare explicitly matched gameplay cohorts, otherwise return inconclusive.

    Required conditions must be known and equal; build labels may differ. A
    scenario frame range numbers retained gameplay samples in replay order,
    independently of collector frame IDs. Its length must match the cohort.
    Scenario duration is simulation/replay coverage, not elapsed capture runtime.
    Reported changes are descriptive heuristics, never statistical significance.
    """
    reasons = []
    limitations = [
        'One before/after pair cannot establish a fix, regression cause, or statistical significance; repeat randomized or alternating controlled runs.',
        'Scenario ordinals and replay duration are declared metadata; this comparison does not independently verify scene or input equivalence.',
        'p95 and p99 are interpolated sample quantiles; tail estimates are unstable with small cohorts.',
        'A material change exceeds both 5 percent and 1 ms in a reported quantile; these are descriptive thresholds, not significance tests.',
    ]
    before_metadata = before.get('metadata', {})
    after_metadata = after.get('metadata', {})
    if not isinstance(before_metadata, dict):
        before_metadata = {}
    if not isinstance(after_metadata, dict):
        after_metadata = {}
    for key in REQUIRED_CONDITIONS:
        left, right = before_metadata.get(key), after_metadata.get(key)
        if not _known(left) or not _known(right):
            reasons.append(f'Missing or unknown comparison condition: {key}.')
        elif _canonical(left) != _canonical(right):
            reasons.append(f'Comparison condition differs: {key}.')
    before_synthetic, after_synthetic = before.get('synthetic'), after.get('synthetic')
    matching_synthetic = (type(before_synthetic) is bool and type(after_synthetic) is bool
                          and before_synthetic == after_synthetic)
    if not matching_synthetic:
        reasons.append('Synthetic markers must be explicit and equal; synthetic and real evidence cannot be compared as a valid pair.')
    # Coverage uses sanitized metadata rather than assuming importer validation.
    before_view = dict(before, metadata=before_metadata)
    after_view = dict(after, metadata=after_metadata)
    before_values, before_coverage = _coverage(before_view, 'before', reasons)
    after_values, after_coverage = _coverage(after_view, 'after', reasons)
    if before_coverage['scenario_frame_range'] != after_coverage['scenario_frame_range']:
        reasons.append('Scenario frame ordinal ranges differ.')
    left_duration, right_duration = before_coverage['scenario_duration_ms'], after_coverage['scenario_duration_ms']
    if (left_duration is not None and right_duration is not None
            and not math.isclose(left_duration, right_duration, rel_tol=1e-6, abs_tol=0.001)):
        reasons.append('Scenario replay/simulation duration coverage differs.')
    metrics = {}
    status = 'inconclusive'
    if not reasons:
        directions = set()
        for name, fraction in (('p50', 0.5), ('p95', 0.95), ('p99', 0.99)):
            left, right = _quantile(before_values, fraction), _quantile(after_values, fraction)
            delta = right - left
            delta_pct = (right / left - 1) * 100
            metrics[name] = {'before_ms': left, 'after_ms': right,
                             'delta_ms': delta, 'delta_pct': delta_pct}
            if abs(delta) > 1.0 and abs(delta_pct) > 5.0:
                directions.add('regression' if delta > 0 else 'improvement')
        if any(not math.isfinite(value) for metric in metrics.values() for value in metric.values()):
            reasons.append('Effect-size arithmetic is not finite; the pair cannot support a comparison.')
            metrics = {}
        else:
            status = ('mixed_change' if len(directions) == 2 else
                      next(iter(directions)) if directions else 'no_material_change')
        for name, values in (('before', before_values), ('after', after_values)):
            spread = _quantile(values, 0.75) - _quantile(values, 0.25)
            if spread / median(values) > 0.25 or _quantile(values, 0.99) / median(values) > 3:
                limitations.append(f'{name} cohort has high frame-time variability; noisy runs cannot establish significance from this pair.')
    warnings = [text for session in (before, after) for text in session.get('warnings', []) if isinstance(text, str)]
    return {
        'schema_version': 1,
        'before_session_id': before.get('session_id', ''), 'after_session_id': after.get('session_id', ''),
        'synthetic': before_synthetic if matching_synthetic else None,
        'status': status, 'comparable': not reasons, 'reasons': reasons,
        'statistical_significance': 'not_established',
        'metrics': metrics, 'coverage': {'before': before_coverage, 'after': after_coverage},
        'limitations': limitations, 'warnings': warnings,
    }
