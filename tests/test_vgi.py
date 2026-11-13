import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class VGICompatibilityTests(unittest.TestCase):
    def cli(self,*args):
        return subprocess.run([sys.executable,'-m','vgi',*map(str,args)],capture_output=True,text=True)
    def test_official_cli_help_and_version(self):
        result=self.cli('--help')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Visual Game Intelligence',result.stdout)
        self.assertIn('python -m vgi',result.stdout)
    def test_vgi_and_urd_share_core_version(self):
        import vgi,urd
        self.assertEqual(vgi.__version__,urd.__version__)
    def test_official_cli_native_diagnosis_and_branding(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            demo=self.cli('demo','--native-hookshot','--out',root/'session')
            self.assertEqual(demo.returncode,0,demo.stderr)
            result=self.cli('analyze',root/'session/session.json','--out',root/'report')
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads((root/'report/report.json').read_text())
            self.assertTrue(report['synthetic'])
            self.assertEqual(report['tool']['name'],'VGI — Visual Game Intelligence')
            self.assertIn('python -m vgi',report['reproduction']['command'])
            self.assertIn('VGI', (root/'report/report.md').read_text())
    def test_legacy_cli_is_usable(self):
        result=subprocess.run([sys.executable,'-m','urd','self-test'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
