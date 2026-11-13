import json
import tempfile
import unittest
from pathlib import Path
from urd.collect import collect_hookshot
from urd.fixtures import create_demo
from urd.adapters.bundle import load_session

class CollectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        create_demo(self.root/'game',native=True)
        (self.root/'game/secret-game.bin').write_bytes(b'PROPRIETARY')
    def test_only_allowlisted_metrics_logs_copied_read_only(self):
        original=(self.root/'game/hookshot_frames.csv').read_bytes()
        path=collect_hookshot(self.root/'game',self.root/'out',session_closed=True,synthetic=True)
        session=load_session(path)
        self.assertTrue(session['synthetic']) # explicitly synthetic collector test input
        self.assertNotIn('secret-game.bin',[p.name for p in path.parent.iterdir()])
        self.assertEqual((self.root/'game/hookshot_frames.csv').read_bytes(),original)
    def test_closed_session_required_and_existing_out_refused(self):
        with self.assertRaises(ValueError): collect_hookshot(self.root/'game',self.root/'out',session_closed=False)
        self.root.joinpath('out').mkdir()
        with self.assertRaises(ValueError): collect_hookshot(self.root/'game',self.root/'out',session_closed=True)
    def test_missing_native_metrics_does_not_fabricate(self):
        self.root.joinpath('game/hookshot_frames.csv').unlink()
        with self.assertRaises(ValueError): collect_hookshot(self.root/'game',self.root/'out',session_closed=True)
    def test_symlink_outside_game_is_not_collected(self):
        self.root.joinpath('game/hookshot_frames.csv').unlink()
        self.root.joinpath('external.csv').write_text('secret')
        self.root.joinpath('game/hookshot_frames.csv').symlink_to(self.root/'external.csv')
        with self.assertRaises(ValueError): collect_hookshot(self.root/'game',self.root/'out',session_closed=True)
