"""Validated normalized evidence; timestamps are integers, never inferred."""
from __future__ import annotations
import hashlib
import math
import re
from pathlib import Path, PureWindowsPath


def safe_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or '\\' in value or '://' in value or PureWindowsPath(value).drive:
        raise ValueError(f'Unsafe session-relative path: {value!r}')
    rel = Path(value)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError(f'Unsafe session-relative path: {value!r}')
    target = (root / rel).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Session path escapes input directory')
    return target


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def integer(value, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r'[+-]?\d+', str(value)):
        raise ValueError(f'{name} must be an integer')
    result = int(value)
    if result < minimum:
        raise ValueError(f'{name} must be >= {minimum}')
    return result


def number(value, name: str, minimum: float = 0, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f'{name} must be finite numeric')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be finite numeric') from exc
    if not math.isfinite(result) or result < minimum or (positive and result == 0):
        raise ValueError(f'Invalid {name}: {value!r}')
    return result


def validate_session(session: dict) -> dict:
    if session.get('schema_version') != 1 or type(session.get('synthetic')) is not bool:
        raise ValueError('Require schema_version=1 and explicit synthetic boolean')
    if not isinstance(session.get('session_id'), str) or not session['session_id']:
        raise ValueError('session_id is required')
    if not isinstance(session.get('metadata'), dict):
        raise ValueError('metadata must be an object')
    last_id = last_time = -1
    previous = None
    for frame in session['frames']:
        frame['frame_id'] = integer(frame['frame_id'], 'frame_id')
        frame['t_ns'] = integer(frame['t_ns'], 't_ns')
        frame['frame_ms'] = number(frame['frame_ms'], 'frame_ms', positive=True)
        frame['uncertainty_ns'] = integer(frame.get('uncertainty_ns', 0), 'frame uncertainty_ns')
        if previous is not None:
            delta = frame['t_ns'] - previous['t_ns']
            expected = round(previous['frame_ms'] * 1_000_000)
            tolerance = frame['uncertainty_ns'] + previous['uncertainty_ns'] + 1000
            if delta < expected - tolerance or (frame['frame_id'] == previous['frame_id'] + 1 and abs(delta-expected) > tolerance):
                raise ValueError('Frame timestamp interval is inconsistent with frame_ms; do not mix clocks or sampling domains')
        previous = frame
        if frame['frame_id'] <= last_id or frame['t_ns'] <= last_time:
            raise ValueError('Duplicate/non-increasing frame identity or monotonic timestamp; split sessions on reset')
        last_id, last_time = frame['frame_id'], frame['t_ns']
        for key in ('cpu_ms', 'gpu_ms', 'gpu_util_pct'):
            if key in frame:
                frame[key] = number(frame[key], key)
                if key == 'gpu_util_pct' and frame[key] > 100:
                    raise ValueError('gpu_util_pct exceeds 100')
        if frame.get('phase', 'gameplay') not in ('gameplay', 'loading', 'menu', 'warmup', 'unknown'):
            raise ValueError('Unknown frame phase')
        _synthetic_record(session, frame)
    event_ids = set()
    for event in session['events']:
        if not isinstance(event.get('id'), str) or not event['id'] or event['id'] in event_ids:
            raise ValueError('Event IDs must be unique nonempty strings')
        event_ids.add(event['id'])
        if not isinstance(event.get('kind'), str) or not isinstance(event.get('message', ''), str):
            raise ValueError('Event kind/message must be text')
        _identity(event)
        if event.get('duration_ms') is not None:
            event['duration_ms'] = number(event['duration_ms'], 'event duration_ms')
        _synthetic_record(session, event)
    for capture in session['captures']:
        _identity(capture)
        if capture.get('frame_id') is None and capture.get('t_ns') is None:
            session.setdefault('warnings', []).append('Capture has no verified identity; retained as unjoined session context')
        if not isinstance(capture.get('path'), str):
            raise ValueError('Capture path is required')
        capture['uncertainty_ns'] = integer(capture.get('uncertainty_ns', 0), 'uncertainty_ns')
        _synthetic_record(session, capture)
    session.setdefault('warnings', [])
    session.setdefault('provenance', [])
    return session


def _identity(record):
    for key in ('frame_id', 't_ns', 'uncertainty_ns'):
        if record.get(key) is not None:
            record[key] = integer(record[key], key)


def _synthetic_record(session, record):
    if 'synthetic' in record and (type(record['synthetic']) is not bool or record['synthetic'] != session['synthetic']):
        raise ValueError('Mixed synthetic and real evidence is forbidden; split sessions')
