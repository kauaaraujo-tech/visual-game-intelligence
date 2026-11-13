import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urd.fixtures import create_demo
from urd.report import build_report, write_report
from urd.adapters.bundle import load_session

class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
    def test_synthetic_demo_end_to_end(self):
        manifest = create_demo(self.root / 'demo')
        session = load_session(manifest)
        report = build_report(session)
        self.assertTrue(report['synthetic'])
        self.assertEqual(report['status'], 'incidents_detected')
        self.assertEqual(report['incidents'][0]['frame_ids'], [30,31,32])
        self.assertTrue(report['incidents'][0]['events'])
        self.assertTrue(report['incidents'][0]['captures'])
        write_report(report, self.root / 'out')
        text = (self.root / 'out' / 'report.md').read_text()
        self.assertIn('SINTÉTICOS', text)
        self.assertIn('sha256', text.lower())
        self.assertIn('Não comprovada', text)
        self.assertIn('Reprodução', text)
    def test_report_is_deterministic_and_byte_identical(self):
        session = load_session(create_demo(self.root / 'demo'))
        for directory in ('one','two'):
            write_report(build_report(session), self.root / directory)
        self.assertEqual((self.root/'one/report.json').read_bytes(), (self.root/'two/report.json').read_bytes())
    def test_cli_creates_reports_and_handles_invalid_input(self):
        manifest = create_demo(self.root / 'demo')
        p = subprocess.run([sys.executable,'-m','urd','analyze',str(manifest),'--out',str(self.root/'out')],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        bad = subprocess.run([sys.executable,'-m','urd','analyze',str(self.root/'missing.json'),'--out',str(self.root/'out')],capture_output=True,text=True)
        self.assertEqual(bad.returncode,2)
        self.assertNotIn('Traceback', bad.stderr)
    def test_refuses_to_overwrite_source_evidence(self):
        manifest = create_demo(self.root / 'demo')
        report = build_report(load_session(manifest))
        with self.assertRaises(ValueError):
            write_report(report, manifest.parent)
    def test_fixture_refuses_existing_directory(self):
        self.root.joinpath('demo').mkdir()
        self.root.joinpath('demo/precious').write_text('keep')
        with self.assertRaises(ValueError): create_demo(self.root/'demo')
        self.assertEqual(self.root.joinpath('demo/precious').read_text(),'keep')
    def test_markdown_does_not_include_raw_external_link(self):
        session=load_session(create_demo(self.root/'demo'))
        session['events'][0]['message']='[click](https://evil.invalid) <script>alert(1)</script>'
        write_report(build_report(session),self.root/'out')
        md=(self.root/'out/report.md').read_text()
        self.assertNotIn('<script>',md)
