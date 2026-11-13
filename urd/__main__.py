"""Offline command-line entry point. Never starts games or background services."""
from __future__ import annotations
import argparse
import csv
import json
import socket
import sys
import tempfile
from pathlib import Path


def save_json(path: Path, value: dict):
    data=json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream: stream.write(data)


def main(argv=None, *, prog="python -m urd"):
    parser=argparse.ArgumentParser(prog=prog,description='VGI — Visual Game Intelligence. Experimental offline reproducible diagnostics. No automatic data uploads.')
    sub=parser.add_subparsers(dest='command',required=True)
    analyze=sub.add_parser('analyze',help='Import a declared session and create evidence reports')
    analyze.add_argument('manifest',type=Path); analyze.add_argument('--out',type=Path,required=True)
    analyze.add_argument('--visual',action='store_true',help='Analyze available adjacent captures locally (optional Pillow)')
    demo=sub.add_parser('demo',help='Generate clearly marked SYNTHETIC software test data')
    demo.add_argument('--out',type=Path,required=True); demo.add_argument('--native-hookshot',action='store_true')
    compare=sub.add_parser('compare',help='Controlled before/after descriptive comparison')
    compare.add_argument('before',type=Path); compare.add_argument('after',type=Path); compare.add_argument('--out',type=Path,required=True)
    brief=sub.add_parser('brief',help='Save a reduced evidence summary, without running any model')
    brief.add_argument('report',type=Path); brief.add_argument('--out',type=Path,required=True)
    ai=sub.add_parser('ai-local',help='Explicitly send reduced evidence to your local model at 127.0.0.1 only')
    ai.add_argument('report',type=Path); ai.add_argument('--model',required=True); ai.add_argument('--port',type=int,default=11434); ai.add_argument('--out',type=Path,required=True)
    collect=sub.add_parser('collect',help='Copy existing native metrics/log, after the game is closed; no configuration changes')
    collect.add_argument('game_dir',type=Path); collect.add_argument('--session-closed',action='store_true'); collect.add_argument('--synthetic',action='store_true'); collect.add_argument('--metadata',type=Path); collect.add_argument('--out',type=Path,required=True)
    accept=sub.add_parser('accept',help='Copy/import a closed local session and generate an experimental acceptance record')
    accept.add_argument('source',type=Path); accept.add_argument('--session-closed',action='store_true'); accept.add_argument('--synthetic',action='store_true'); accept.add_argument('--visual',action='store_true'); accept.add_argument('--metadata',type=Path); accept.add_argument('--out',type=Path,required=True)
    sub.add_parser('self-test',help='Exercise ingestion, detection, image association and deterministic report locally')
    args=parser.parse_args(argv)
    try:
        if args.command=='accept':
            from vgi.acceptance import accept_local
            from urd.adapters.bundle import read_json
            metadata=read_json(args.metadata) if args.metadata else None
            result=accept_local(args.source,args.out,session_closed=args.session_closed,synthetic=args.synthetic,metadata=metadata,visual=args.visual)
            print(json.dumps(result,ensure_ascii=False)); return 0
        if args.command=='demo':
            from urd.fixtures import create_demo
            print(create_demo(args.out,args.native_hookshot)); return 0
        if args.command=='analyze':
            from urd.adapters.bundle import load_session
            from urd.report import build_report,write_report
            report=build_report(load_session(args.manifest),visual=args.visual)
            write_report(report,args.out)
            print(json.dumps({'status':report['status'],'incidents':len(report['incidents']),'synthetic':report['synthetic'],'report':str(args.out/'report.md')},ensure_ascii=False)); return 0
        if args.command=='collect':
            from urd.collect import collect_hookshot
            from urd.adapters.bundle import read_json
            metadata=read_json(args.metadata) if args.metadata else None
            print(collect_hookshot(args.game_dir,args.out,session_closed=args.session_closed,synthetic=args.synthetic,metadata=metadata)); return 0
        if args.command=='compare':
            from urd.adapters.bundle import load_session
            from urd.compare import compare_sessions
            result=compare_sessions(load_session(args.before),load_session(args.after))
            save_json(args.out,result); print(result['status']); return 0
        if args.command in ('brief','ai-local'):
            from urd.assistant import make_brief,request_local
            from urd.adapters.bundle import read_json
            if args.out.exists(): raise ValueError('Output exists; choose a new file')
            report=read_json(args.report)
            result=make_brief(report) if args.command=='brief' else request_local(report,model=args.model,port=args.port)
            save_json(args.out,result); print(str(args.out)); return 0
        if args.command=='self-test':
            from urd.fixtures import create_demo
            from urd.adapters.bundle import load_session
            from urd.report import build_report,write_report
            with tempfile.TemporaryDirectory(prefix='urd-self-test-') as tmp:
                root=Path(tmp)
                for native in (False,True):
                    manifest=create_demo(root/('native' if native else 'generic'),native)
                    report=build_report(load_session(manifest))
                    if report['status']!='incidents_detected' or not report['synthetic']:
                        raise ValueError('Self-test failed to detect known SYNTHETIC anomaly')
                    if not report['incidents'][0]['events'] or not report['incidents'][0]['captures']:
                        raise ValueError('Self-test failed SYNTHETIC evidence association')
                    for name in ('a','b'): write_report(report,root/f'{native}-{name}')
                    if (root/f'{native}-a/report.json').read_bytes()!=(root/f'{native}-b/report.json').read_bytes():
                        raise ValueError('Report is not deterministic')
            print('PASS: synthetic generic + native Hookshot; incidents, events, captures, deterministic reports. No real-game validation.'); return 0
    except (OSError,ValueError,KeyError,TypeError,OverflowError,csv.Error,socket.timeout) as exc:
        print(f'VGI: {exc}',file=sys.stderr); return 2
    return 2

if __name__=='__main__':
    sys.exit(main())
