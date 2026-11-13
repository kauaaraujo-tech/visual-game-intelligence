"""Explicit synthetic fixtures. These are software tests, never game observations."""
from __future__ import annotations
import csv
import json
from pathlib import Path


def create_demo(directory: Path | str, native: bool = False) -> Path:
    root = Path(directory)
    if root.exists():
        raise ValueError('Demo destination already exists; choose a new directory')
    root.mkdir(parents=True)
    durations = [16.0] * 30 + [85.0, 72.0, 64.0] + [16.0] * 30
    metadata = {'clock_domain': 'session_monotonic', 'scenario': 'SYNTHETIC_FIXED_SCENE',
                'hardware': {'cpu': 'synthetic', 'gpu': 'synthetic'},
                'settings': {'resolution': 'synthetic', 'frame_generation': False},
                'run_group': 'synthetic-demo-v1', 'build': 'synthetic-v1',
                'sample_kind': 'game', 'collector': 'urd.synthetic.v1'}
    manifest = {'schema_version': 1, 'adapter': 'generic', 'session_id': 'SYNTHETIC-DEMO',
                'synthetic': True, 'metadata': metadata, 'frames': 'frames.csv',
                'events': 'events.jsonl', 'captures': [{'path': 'SYNTHETIC-frame31.ppm', 'frame_id': 31}]}
    with (root / 'frames.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['frame_id','t_ns','frame_ms','phase'])
        elapsed = 0
        for i, ms in enumerate(durations):
            writer.writerow([i, elapsed, ms, 'gameplay'])
            elapsed += round(ms * 1_000_000)
    event = {'id':'synthetic-pipeline-31','kind':'pipeline_compile', 'frame_id':31,
             'duration_ms':45.0,'message':'SYNTHETIC pipeline compilation interval; no real game data'}
    (root/'events.jsonl').write_text(json.dumps(event)+'\n', encoding='utf-8')
    (root/'SYNTHETIC-frame31.ppm').write_bytes(b'P6\n16 16\n255\n'+bytes([180,30,180])*256)
    if native:
        # Published native format, entirely generated test values.
        fields = ['frame','ms','pipe_waits','pipe_wait_ms','left_out','translate_ms','uploads','upload_mb','textures','memsync_ms','pipelines_ms','uploads_ms','programs_ms','slot_wait_ms','gpu_behind_ms','draw_ms','desc_ms','cmds_ms','tex_lookup_ms','textures_gone','late_wait_ms','readback_wait_ms','tex_frame_ms']
        with (root/'hookshot_frames.csv').open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields)
            writer.writeheader()
            for i,ms in enumerate(durations):
                row={name:0 for name in fields}
                row.update(frame=i+1,ms=ms,pipe_wait_ms=45 if i==31 else 0,pipe_waits=1 if i==31 else 0)
                writer.writerow(row)
        manifest.update(adapter='hookshot',session_id='SYNTHETIC-HOOKSHOT-NATIVE',performance_trace='hookshot_frames.csv')
        manifest.pop('frames'); manifest.pop('events')
        manifest['captures']=[{'path':'SYNTHETIC-frame31.ppm','frame_id':32,'frame_domain':'hookshot.performance_frame'}]
    (root/'session.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return root/'session.json'
