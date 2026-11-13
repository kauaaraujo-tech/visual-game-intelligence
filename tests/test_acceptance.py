import csv,json,tempfile,unittest
from pathlib import Path
from urd.fixtures import create_demo
from vgi.acceptance import accept_local
from urd.adapters.bundle import load_session
from urd.analysis import analyze

class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def test_one_command_import_reports_only_pipeline_acceptance(self):
        source=create_demo(self.root/'native',True).parent
        result=accept_local(source,self.root/'accepted',session_closed=True,synthetic=True)
        self.assertTrue(result['checks']['native_import_valid'])
        self.assertTrue(result['synthetic'])
        self.assertFalse(result['real_game_diagnostic_validated'])
        self.assertIsNone(result['false_positive_rate'])
        self.assertIsNone(result['capture_overhead_ms'])
        self.assertTrue((self.root/'accepted/report/report.json').is_file())
    def test_existing_manifest_preserves_capture_alignment(self):
        source=create_demo(self.root/'manifest')
        result=accept_local(source,self.root/'accepted',session_closed=True)
        self.assertTrue(result['synthetic'])
        self.assertEqual(result['checks']['associated_capture_count'],1)
    def test_closed_session_and_fresh_output_required(self):
        source=create_demo(self.root/'native',True).parent
        with self.assertRaises(ValueError):accept_local(source,self.root/'out',session_closed=False)
        (self.root/'out').mkdir()
        with self.assertRaises(ValueError):accept_local(source,self.root/'out',session_closed=True)
    def test_real_declared_log_only_does_not_invent_per_frame_results(self):
        source=self.root/'log-only';source.mkdir()
        (source/'hookshot_log.txt').write_text('[hos host] vk: precompile: 8917 programs in 4920 ms\n')
        result=accept_local(source,self.root/'accepted',session_closed=True)
        self.assertFalse(result['synthetic'])
        self.assertEqual(result['diagnostic_status'],'insufficient_data')
        self.assertFalse(result['checks']['per_frame_metrics_available'])
        self.assertFalse(result['real_game_diagnostic_validated'])
        report=json.loads((self.root/'accepted/report/report.json').read_text())
        self.assertEqual(report['incidents'],[])
        self.assertEqual(len(report['session_context']['events']),1)
    def test_generic_phase_annotations_normalize_before_matching(self):
        manifest=create_demo(self.root/'generic')
        data=json.loads(manifest.read_text());data['phase_annotations']=[{'start_frame':1,'end_frame':10,'phase':'loading','basis':'synthetic replay'}]
        manifest.write_text(json.dumps(data))
        session=load_session(manifest)
        self.assertEqual(session['frames'][2]['phase'],'loading')
    def test_event_uncertainty_is_honored_like_capture_uncertainty(self):
        session=load_session(create_demo(self.root/'generic'))
        session['events']=[{'id':'uncertain','kind':'wait','t_ns':479000000,'uncertainty_ns':2000000}]
        incident=analyze(session)['incidents'][0]
        self.assertEqual(incident['events'][0]['association'],'timestamp_uncertain')
