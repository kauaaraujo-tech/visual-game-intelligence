import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urd.adapters.bundle import load_session
from urd.analysis import analyze
from urd.fixtures import create_demo
from urd.report import build_report,write_report
from urd.model import sha256_file

class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.manifest=create_demo(self.root/'demo')
    def test_explicit_foreign_domains_never_join(self):
        session=load_session(self.manifest)
        session['metadata']['frame_domain']='normalized.frame'
        session['events']=[{'id':'wrong-frame','kind':'wait','frame_id':31,'frame_domain':'native.game'},
                           {'id':'wrong-clock','kind':'wait','t_ns':570000000,'clock_domain':'other.monotonic'}]
        session['captures'][0]['frame_domain']='native.game'
        result=analyze(session)
        self.assertEqual(result['incidents'][0]['events'],[])
        self.assertEqual(result['incidents'][0]['captures'],[])
        self.assertTrue(any('domain' in w.lower() for w in result['warnings']))
    def test_inconsistent_generic_intervals_rejected(self):
        frames=self.root/'demo/frames.csv'
        frames.write_text('frame_id,t_ns,frame_ms\n0,0,80\n1,16000000,16\n')
        with self.assertRaises(ValueError): load_session(self.manifest)
    def test_csv_uncertainty_normalized_and_honored(self):
        frames=self.root/'demo/frames.csv'
        lines=frames.read_text().splitlines()
        lines[0]+=',uncertainty_ns'
        lines[1:]=[line+',20000000' for line in lines[1:]]
        frames.write_text('\n'.join(lines)+'\n')
        session=load_session(self.manifest)
        self.assertEqual(session['frames'][0]['uncertainty_ns'],20000000)
        session['events']=[{'id':'e','kind':'wait','frame_id':30,'t_ns':481000000}]
        self.assertIn('uncertain',analyze(session)['incidents'][0]['events'][0]['association'])
    def test_capture_copy_reads_one_hash_verified_snapshot(self):
        report=build_report(load_session(self.manifest)); capture=self.root/'demo/SYNTHETIC-frame31.ppm'
        from urd import report as report_module
        original=report_module.sha256_file
        def race(path):
            digest=original(path)
            if Path(path)==capture: capture.write_bytes(b'MODIFIED')
            return digest
        with patch.object(report_module,'sha256_file',side_effect=race):
            try:
                write_report(report,self.root/'out')
            except ValueError:
                return # changed snapshot rejected
        output=json.loads((self.root/'out/report.json').read_text())
        cap=output['incidents'][0]['captures'][0]['capture']
        copied=self.root/'out'/cap['report_image']
        expected={p['file']:p['sha256'] for p in output['provenance']}[cap['relative_path']]
        self.assertEqual(sha256_file(copied),expected)
    def test_report_capture_references_are_portable(self):
        report=build_report(load_session(self.manifest))
        write_report(report,self.root/'out')
        data=(self.root/'out/report.json').read_text()
        self.assertNotIn(str(self.root),data)
    def test_visual_only_evidence_is_packaged(self):
        session=load_session(self.manifest); report=build_report(session)
        report['incidents']=[]
        report['visual']={'status':'candidates_detected','candidates':[{'kind':'test','confidence':'low','status':'candidate_not_proven','evidence':[dict(session['captures'][0])]}]}
        write_report(report,self.root/'out')
        output=json.loads((self.root/'out/report.json').read_text())
        evidence=output['visual']['candidates'][0]['evidence'][0]
        self.assertTrue((self.root/'out'/evidence['report_image']).is_file())
    def test_parser_hashes_the_same_bytes_it_parses(self):
        frames=self.root/'demo/frames.csv'; expected=sha256_file(frames)
        from urd.adapters import bundle
        original=bundle.sha256_file
        def race(path):
            if Path(path)==frames: frames.write_text('frame_id,t_ns,frame_ms\n0,0,999\n')
            return original(path)
        with patch.object(bundle,'sha256_file',side_effect=race):
            session=load_session(self.manifest)
        self.assertEqual(session['frames'][0]['frame_ms'],16)
        self.assertEqual(next(p['sha256'] for p in session['provenance'] if p['file']=='frames.csv'),expected)
    def test_native_explicit_phase_annotations_support_controlled_cohort(self):
        manifest=create_demo(self.root/'native',True)
        data=json.loads(manifest.read_text())
        data['phase_annotations']=[{'start_frame':2,'end_frame':63,'phase':'gameplay','basis':'synthetic fixed replay fixture'}]
        manifest.write_text(json.dumps(data))
        session=load_session(manifest)
        self.assertEqual(session['frames'][0]['phase'],'warmup')
        self.assertTrue(all(f['phase']=='gameplay' for f in session['frames'][1:]))
        self.assertTrue(any('annotation' in w for w in session['warnings']))
    def test_phase_annotations_require_evidence_basis_and_preserve_startup(self):
        manifest=create_demo(self.root/'native',True)
        for annotation in [
            {'start_frame':2,'end_frame':10,'phase':'gameplay'},
            {'start_frame':1,'end_frame':10,'phase':'gameplay','basis':'synthetic'},
            {'start_frame':2,'end_frame':999,'phase':'gameplay','basis':'synthetic'},
        ]:
            data=json.loads(manifest.read_text()); data['phase_annotations']=[annotation]
            manifest.write_text(json.dumps(data))
            with self.subTest(annotation=annotation),self.assertRaises(ValueError): load_session(manifest)
    def test_dominant_internal_wait_yields_specific_falsifiable_hypothesis(self):
        session=load_session(self.manifest)
        session['events']=[{'id':'pipe','kind':'pipe_wait_ms','frame_id':31,'duration_ms':45,'message':'SYNTHETIC'}]
        hypotheses=analyze(session)['incidents'][0]['hypotheses']
        specific=[h for h in hypotheses if h.get('investigation')=='shader_pipeline_wait']
        self.assertTrue(specific)
        self.assertIn('pipe',specific[0]['evidence_ids'])
        self.assertEqual(specific[0]['status'],'hypothesis')
        self.assertIn('cache',specific[0]['next_test'].lower())
    def test_tiny_internal_duration_does_not_become_dominant_cause(self):
        session=load_session(self.manifest)
        session['events']=[{'id':'tiny','kind':'pipe_wait_ms','frame_id':31,'duration_ms':0.001}]
        hypotheses=analyze(session)['incidents'][0]['hypotheses']
        self.assertFalse(any(h.get('investigation')=='shader_pipeline_wait' for h in hypotheses))
    def test_reproduction_uses_actual_manifest_and_visual_option(self):
        named=self.root/'demo/custom-manifest.json'
        self.manifest.rename(named)
        result=build_report(load_session(named),visual=True)
        self.assertIn('custom-manifest.json',result['reproduction']['command'])
        self.assertIn('--visual',result['reproduction']['command'])
    def test_collector_cannot_write_inside_game_directory(self):
        from urd.collect import collect_hookshot
        native=create_demo(self.root/'native',True)
        with self.assertRaises(ValueError):
            collect_hookshot(native.parent,native.parent/'new-session',session_closed=True,synthetic=True)
