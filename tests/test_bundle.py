import json
import tempfile
import unittest
from pathlib import Path
from urd.adapters.bundle import load_session
from urd.model import safe_path

class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.manifest = {'schema_version': 1, 'adapter': 'generic', 'session_id': 'test',
                         'synthetic': True, 'metadata': {'clock_domain': 'session_monotonic'},
                         'frames': 'frames.csv', 'events': 'events.jsonl', 'captures': []}
        (self.root / 'frames.csv').write_text('frame_id,t_ns,frame_ms\n1,0,16\n2,16000000,32\n')
        (self.root / 'events.jsonl').write_text(json.dumps({'id': 'e1', 'kind': 'pipeline_compile', 'message': 'synthetic', 'frame_id': 2})+'\n')
    def load(self):
        (self.root / 'session.json').write_text(json.dumps(self.manifest))
        return load_session(self.root / 'session.json')
    def test_csv_and_jsonl_preserve_evidence_and_synthetic(self):
        s = self.load()
        self.assertTrue(s['synthetic'])
        self.assertEqual(s['frames'][1]['t_ns'], 16000000)
        self.assertEqual(s['events'][0]['source']['line'], 1)
        self.assertEqual(len(s['provenance']), 3)
        self.assertEqual(len(s['provenance'][0]['sha256']), 64)
    def test_unsafe_paths(self):
        for path in ['../x', '/etc/passwd', 'https://example/a', 'C:\\secret', '..\\x']:
            with self.subTest(path=path), self.assertRaises(ValueError): safe_path(self.root, path)
    def test_symlink_escape(self):
        (self.root / 'escape').symlink_to(Path(self.tmp.name).parent)
        with self.assertRaises(ValueError): safe_path(self.root, 'escape/file')
    def test_nonfinite_duration(self):
        for value in ['nan', 'inf', '-1', '0']:
            (self.root / 'frames.csv').write_text(f'frame_id,t_ns,frame_ms\n1,0,{value}\n')
            with self.subTest(value=value), self.assertRaises(ValueError): self.load()
    def test_duplicate_frames_and_clock_reset(self):
        for second in ['1,16000000,16', '2,0,16', '2,-1,16']:
            (self.root / 'frames.csv').write_text('frame_id,t_ns,frame_ms\n1,0,16\n'+second+'\n')
            with self.subTest(second=second), self.assertRaises(ValueError): self.load()
    def test_fractional_frame_id_is_not_truncated(self):
        (self.root / 'frames.csv').write_text('frame_id,t_ns,frame_ms\n1.5,0,16\n')
        with self.assertRaises(ValueError): self.load()
    def test_synthetic_and_clock_must_be_declared(self):
        del self.manifest['synthetic']
        with self.assertRaises(ValueError): self.load()
    def test_capture_must_exist_and_have_explicit_identity(self):
        (self.root / 'a.png').write_bytes(b'test')
        self.manifest['captures'] = [{'path': 'a.png', 'frame_id': 2}]
        self.assertEqual(self.load()['captures'][0]['frame_id'], 2)
        self.manifest['captures'] = [{'path': 'a.png'}]
        self.assertTrue(any('unjoined' in w for w in self.load()['warnings']))
    def test_unknown_adapter_is_rejected(self):
        self.manifest['adapter'] = 'made-up'
        with self.assertRaises(ValueError): self.load()
    def test_event_duration_and_uncertainty_validated(self):
        (self.root / 'events.jsonl').write_text(json.dumps({'id':'e','kind':'wait','duration_ms':float('nan')})+'\n')
        with self.assertRaises(ValueError): self.load()
    def test_input_change_changes_hash(self):
        before = self.load()['provenance']
        (self.root / 'events.jsonl').write_text('')
        self.assertNotEqual(before, self.load()['provenance'])
    def test_no_silent_mixed_synthetic_records(self):
        (self.root / 'events.jsonl').write_text(json.dumps({'id':'e', 'kind':'test','synthetic':False})+'\n')
        with self.assertRaises(ValueError): self.load()
