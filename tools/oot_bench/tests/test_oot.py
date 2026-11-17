import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vgi_oot import parse_presentmon, analyze, fps_summary, compare_runs

class OotTest(unittest.TestCase):
    def make_csv(self, p, n=100, extra=False):
        with p.open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['Application', 'ProcessID', 'SwapChainAddress', 'MsBetweenPresents', 'MsBetweenDisplayChange', 'MsGPUBusy', 'MsCPUBusy'])
            for i in range(n):
                w.writerow(['ocarina.exe','124','0x1',16.667,16.667,10,6])
            if extra:
                w.writerow(['other.exe','55','0x2',1000,1000,1000,1000])
    def test_summary(self):
        x = fps_summary([10.0]*99+[50.0]); self.assertEqual(x['samples'],100)
        self.assertTrue(x['avg_fps'] < 100)
        self.assertAlmostEqual(x['low_1pct_fps'],20,places=1)
        self.assertTrue(x['p99_ms'] > 10)
    def test_short_rejected(self):
        self.assertIsNone(fps_summary([16.6]*10))
    def test_import(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv'; self.make_csv(p)
            x=parse_presentmon(p); self.assertEqual(x['process'],'ocarina.exe')
            self.assertEqual(x['app']['samples'],100)
            self.assertAlmostEqual(x['app']['avg_fps'],59.998,places=1)
            self.assertEqual(x['gpu_busy_mean_ms'],10)
    def test_multprocess_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv'; self.make_csv(p,extra=True)
            with self.assertRaisesRegex(ValueError,'Mais de um processo'):
                parse_presentmon(p)
            self.assertEqual(parse_presentmon(p,expected_process='ocarina.exe')['app']['samples'],100)
    def test_multiswapchain_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv'; self.make_csv(p)
            with p.open('a',newline='') as f:
                w=csv.writer(f)
                for _ in range(40):
                    w.writerow(['ocarina.exe','124','0x3',33.333,'',10,6])
            x=parse_presentmon(p)
            self.assertEqual(x['app']['samples'],100)
            self.assertEqual(x['other_swapchain_frames_excluded'],40)
    def test_no_csv(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv';p.write_text('who,what\na,b\n')
            with self.assertRaisesRegex(ValueError,'MsBetweenPresents'):parse_presentmon(p)
    def test_vgi_contract_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv';self.make_csv(p)
            folder,x=analyze(p,recomp='Longshot (Recomper)',scenario='kokiri',frame_generation='off',dest=Path(d)/'result')
            manifest=json.loads((folder/'session.json').read_text())
            self.assertEqual(manifest['adapter'],'generic')
            self.assertEqual(manifest['metadata']['clock_domain'],'presentmon.app_present_reconstructed_monotonic')
            self.assertEqual(len((folder/'frames.csv').read_text().splitlines()),101)
            self.assertTrue((folder/'resumo.md').exists())
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv';self.make_csv(p)
            out=Path(d)/'result'
            analyze(p,dest=out)
            with self.assertRaisesRegex(ValueError,'nao sobrescreveremos'):
                analyze(p,dest=out)
    def test_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv';self.make_csv(p)
            root=Path(d)/'results'
            analyze(p,recomp='A',scenario='kokiri',settings='same',frame_generation='off',cache_state='warm',dest=root/'a')
            analyze(p,recomp='B',scenario='kokiri',settings='same',frame_generation='off',cache_state='warm',dest=root/'b')
            compare_runs(root)
            txt=(root/'COMPARATIVO.md').read_text()
            self.assertIn('| A |',txt);self.assertIn('| B |',txt)
if __name__=='__main__':unittest.main()
