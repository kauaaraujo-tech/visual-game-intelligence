import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urd.fixtures import create_demo

class IncrementCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def run_cli(self,*args):
        return subprocess.run([sys.executable,'-m','urd',*map(str,args)],capture_output=True,text=True)
    def test_visual_and_source_fields_are_integrated(self):
        manifest=create_demo(self.root/'native',True)
        result=self.run_cli('analyze',manifest,'--visual','--out',self.root/'report')
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads((self.root/'report/report.json').read_text())
        self.assertIn('visual',report)
        self.assertTrue(report['source_correlations'])
        self.assertTrue(report['synthetic'])
    def test_brief_is_saved_without_inference(self):
        manifest=create_demo(self.root/'demo')
        self.assertEqual(self.run_cli('analyze',manifest,'--out',self.root/'report').returncode,0)
        result=self.run_cli('brief',self.root/'report/report.json','--out',self.root/'brief.json')
        self.assertEqual(result.returncode,0,result.stderr)
        brief=json.loads((self.root/'brief.json').read_text())
        self.assertTrue(brief['synthetic'])
        self.assertNotIn(str(self.root),json.dumps(brief))
    def test_compare_missing_controls_is_inconclusive(self):
        a=create_demo(self.root/'before'); b=create_demo(self.root/'after')
        result=self.run_cli('compare',a,b,'--out',self.root/'comparison.json')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads((self.root/'comparison.json').read_text())['status'],'inconclusive')
    def test_collect_copies_only_declared_synthetic_session(self):
        create_demo(self.root/'game',True)
        result=self.run_cli('collect',self.root/'game','--session-closed','--synthetic','--out',self.root/'collected')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads((self.root/'collected/session.json').read_text())['synthetic'])
    def test_output_file_is_exclusive(self):
        manifest=create_demo(self.root/'demo')
        self.run_cli('analyze',manifest,'--out',self.root/'report')
        self.root.joinpath('brief.json').write_text('precious')
        result=self.run_cli('brief',self.root/'report/report.json','--out',self.root/'brief.json')
        self.assertEqual(result.returncode,2)
        self.assertEqual(self.root.joinpath('brief.json').read_text(),'precious')
