"""One-command local acceptance evidence. Import success never proves diagnostic accuracy."""
from __future__ import annotations
import json
from pathlib import Path
from urd.adapters.bundle import load_session
from urd.collect import collect_hookshot
from urd.report import build_report,write_report


def accept_local(source: Path | str, destination: Path | str, *, session_closed: bool,
                 synthetic: bool=False, metadata: dict | None=None, visual: bool=False) -> dict:
    if not session_closed:
        raise ValueError('Close the session and explicitly pass --session-closed before acceptance')
    source=Path(source).resolve(); destination=Path(destination).resolve()
    evidence_root=source if source.is_dir() else source.parent
    if destination.exists() or destination.is_relative_to(evidence_root) or evidence_root.is_relative_to(destination):
        raise ValueError('Choose a new acceptance directory outside the input evidence tree')
    if not source.exists(): raise ValueError('Input session/directory does not exist')
    if source.is_dir():
        manifest=collect_hookshot(source,destination/'session',session_closed=True,synthetic=synthetic,metadata=metadata)
    elif source.suffix.lower()=='.json':
        manifest=source
    else:
        raise ValueError('Supply a Hookshot metrics directory or explicit session JSON manifest')
    session=load_session(manifest)
    if synthetic and not session['synthetic']:
        raise ValueError('Do not relabel real-declared manifest evidence synthetic; correct provenance at its source')
    report=build_report(session,visual=visual)
    write_report(report,destination/'report')
    captures=sum(len(i['captures']) for i in report['incidents'])
    events=sum(len(i['events']) for i in report['incidents'])
    result={'schema_version':1,'tool':'VGI — Visual Game Intelligence','status':'import_pipeline_exercised',
            'experimental':True,'synthetic':session['synthetic'],
            'data_origin':'synthetic_test' if session['synthetic'] else 'user_declared_real_unverified',
            'diagnostic_status':report['status'],'real_game_diagnostic_validated':False,
            'checks':{'native_import_valid':session['metadata']['adapter']=='hookshot',
                      'per_frame_metrics_available':bool(session['frames']),
                      'frame_count':len(session['frames']),'associated_capture_count':captures,
                      'associated_event_count':events,'original_inputs_hashed':bool(session['provenance'])},
            'false_positive_rate':None,'capture_overhead_ms':None,
            'report':'report/report.md','machine_report':'report/report.json',
            'limitations':['Successful import does not verify capture authenticity, incident accuracy, false positives or hardware/port causality.',
                           'Capture overhead and baseline/control equivalence require separate controlled real runs.',
                           'Untimed logs and domain-mismatched captures remain unjoined context.'],
            'next_steps':['Confirm the source build and event/capture clock domains.',
                          'Repeat a stable control and a known incident replay; label expected incidents independently.',
                          'Record instrumented/uninstrumented alternating runs before estimating capture overhead.']}
    destination.mkdir(parents=True,exist_ok=True)
    with (destination/'acceptance.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')
    return result
