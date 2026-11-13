"""Explicit offline session bundles and adapter routing."""
from __future__ import annotations
import csv
import hashlib
import io
import json
from pathlib import Path
from urd.model import safe_path, sha256_file, validate_session, integer


def read_json(path: Path):
    def reject(value):
        raise ValueError(f'Nonfinite JSON value: {value}')
    return json.loads(path.read_bytes().decode('utf-8-sig'), parse_constant=reject)


def load_session(manifest_path: Path | str) -> dict:
    path = Path(manifest_path).resolve()
    manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes.decode('utf-8-sig'), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
    if not isinstance(manifest, dict):
        raise ValueError('Manifest must be a JSON object')
    if type(manifest.get('synthetic')) is not bool or manifest.get('schema_version') != 1:
        raise ValueError('Declare schema_version=1 and synthetic=true/false explicitly')
    if not isinstance(manifest.get('metadata'), dict):
        raise ValueError('metadata object is required')
    root = path.parent
    adapter = manifest.get('adapter')
    if adapter == 'hookshot':
        from urd.adapters.hookshot import load_native
        session = load_native(root, manifest)
    elif adapter == 'generic':
        session = _load_generic(root, manifest)
    else:
        raise ValueError(f'Unknown adapter: {adapter!r}; supported: generic, hookshot')
    provenance = session.setdefault('provenance', [])
    provenance.insert(0, {'file': path.name, 'sha256': hashlib.sha256(manifest_bytes).hexdigest()})
    validate_session(session)
    _apply_phase_annotations(session, manifest)
    session['_input_root'] = str(root)
    session['metadata']['adapter'] = adapter
    session['metadata']['manifest_file'] = path.name
    return session


def _load_generic(root: Path, manifest: dict) -> dict:
    if not manifest['metadata'].get('clock_domain'):
        raise ValueError('Generic metadata.clock_domain is required; use unknown when uncalibrated')
    session = {k: manifest[k] for k in ('schema_version', 'session_id', 'synthetic', 'metadata')}
    session.update(frames=[], events=[], captures=[], warnings=[], provenance=[])
    frame_path = safe_path(root, manifest['frames'])
    frame_bytes = frame_path.read_bytes()
    with io.StringIO(frame_bytes.decode('utf-8-sig'), newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {'frame_id', 't_ns', 'frame_ms'} <= set(reader.fieldnames):
            raise ValueError('Frame CSV requires frame_id,t_ns,frame_ms columns')
        for line, row in enumerate(reader, 2):
            if None in row:
                raise ValueError(f'Extra CSV columns at line {line}')
            record = {k: v for k, v in row.items() if v not in (None, '')}
            record['source'] = {'file': manifest['frames'], 'line': line}
            session['frames'].append(record)
    session['provenance'].append({'file': manifest['frames'], 'sha256': hashlib.sha256(frame_bytes).hexdigest()})
    if manifest.get('events'):
        event_path = safe_path(root, manifest['events'])
        event_bytes = event_path.read_bytes()
        with io.StringIO(event_bytes.decode('utf-8-sig')) as stream:
            for line, text in enumerate(stream, 1):
                if text.strip():
                    event = json.loads(text, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
                    if not isinstance(event, dict):
                        raise ValueError('Event must be JSON object')
                    event['source'] = {'file': manifest['events'], 'line': line}
                    session['events'].append(event)
        session['provenance'].append({'file': manifest['events'], 'sha256': hashlib.sha256(event_bytes).hexdigest()})
    load_captures(root, manifest, session)
    if not session['frames']:
        session['warnings'].append('No per-frame metrics available')
    return session


def load_captures(root: Path, manifest: dict, session: dict):
    for item in manifest.get('captures', []):
        capture = dict(item)
        path = safe_path(root, capture['path'])
        if not path.is_file():
            raise ValueError(f'Missing capture: {capture["path"]}')
        session['provenance'].append({'file': capture['path'], 'sha256': sha256_file(path)})
        capture['relative_path'] = capture['path']
        capture['path'] = str(path)
        session['captures'].append(capture)


def _apply_phase_annotations(session: dict, manifest: dict):
    """Explicit replay annotations are declarations, not automatically detected phases."""
    annotations=manifest.get('phase_annotations', [])
    if not isinstance(annotations,list): raise ValueError('phase_annotations must be a list')
    frames={frame['frame_id']:frame for frame in session['frames']}
    annotated=set()
    for item in annotations:
        if not isinstance(item,dict): raise ValueError('Phase annotation must be an object')
        first=integer(item.get('start_frame'),'annotation start_frame')
        last=integer(item.get('end_frame'),'annotation end_frame')
        phase=item.get('phase'); basis=item.get('basis')
        if phase not in ('gameplay','loading','menu','warmup') or not isinstance(basis,str) or not basis.strip():
            raise ValueError('Phase annotation requires a valid phase and an explicit evidence basis')
        if first>last or first not in frames or last not in frames:
            raise ValueError('Phase annotation endpoints must exist in this recording')
        selected=[frame for frame_id,frame in frames.items() if first<=frame_id<=last]
        for frame in selected:
            frame_id=frame['frame_id']
            if frame_id in annotated: raise ValueError('Overlapping phase annotations are not permitted')
            if frame.get('phase')=='warmup' and phase!='warmup':
                raise ValueError('Native startup warmup cannot be relabeled as gameplay')
            frame['phase']=phase
            frame['phase_annotation_basis']=basis
            annotated.add(frame_id)
    if annotations:
        session['warnings'].append('Phase annotation supplied by manifest; replay/scene equivalence is declared, not independently verified')
