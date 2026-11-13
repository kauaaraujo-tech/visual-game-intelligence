"""Read-only, explicit snapshots of existing Hookshot metrics. No game launch."""
from __future__ import annotations
import json
from pathlib import Path
from urd.model import safe_path
from urd.adapters.bundle import load_session


def collect_hookshot(game_dir: Path | str, destination: Path | str, *, session_closed: bool,
                     synthetic: bool=False, metadata: dict | None=None) -> Path:
    if not session_closed:
        raise ValueError('Close the game first and explicitly pass --session-closed; active traces may be buffered/incomplete')
    source=Path(game_dir).resolve(); target=Path(destination).resolve()
    if not source.is_dir(): raise ValueError('Game directory does not exist')
    if target.exists() or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('Choose a new output directory outside input evidence')
    # Explicitly marked input bundle cannot be silently relabeled as real.
    existing=source/'session.json'
    if existing.is_file():
        value=json.loads(existing.read_text(encoding='utf-8-sig'))
        if value.get('synthetic') is True and not synthetic:
            raise ValueError('Input directory is marked synthetic; pass --synthetic or use a real session')
    primary=safe_path(source,'hookshot_frames.csv')
    if not primary.is_file() and not safe_path(source,'hookshot_log.txt').is_file():
        raise ValueError('Missing hookshot_frames.csv. A future launch needs RX_VK_FRAME_TRACE=1; no settings were changed')
    snapshots={}
    for name in ('hookshot_frames.csv','hookshot_log.txt'):
        path=safe_path(source,name)
        if path.exists():
            if not path.is_file(): raise ValueError(f'Not a regular file: {name}')
            if path.stat().st_size>256*1024*1024: raise ValueError('Trace exceeds 256 MiB collector limit; split session locally')
            before=path.stat(); data=path.read_bytes(); after=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or len(data)!=after.st_size:
                raise ValueError('Input changed during copy; close the game and retry into a new directory')
            snapshots[name]=data
    meta=dict(metadata or {})
    meta.update(collector='urd.readonly_snapshot.v1',capture_session_closed_declared=True,
                data_origin='synthetic_test' if synthetic else 'user_declared_real_unverified')
    manifest={'schema_version':1,'adapter':'hookshot','session_id':'SYNTHETIC-COLLECTED' if synthetic else target.name,
              'synthetic':synthetic,'metadata':meta,'captures':[]}
    if 'hookshot_frames.csv' in snapshots: manifest['performance_trace']='hookshot_frames.csv'
    if 'hookshot_log.txt' in snapshots: manifest['log']='hookshot_log.txt'
    target.mkdir(parents=True)
    for name,data in snapshots.items(): (target/name).write_bytes(data)
    path=target/'session.json'; path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    load_session(path) # validates actual export schema; never fabricates missing rows
    return path
