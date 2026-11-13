"""Synthetic fixtures of the public pinned Hookshot export formats; no game data."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from urd.adapters.hookshot import load_native


HEADER = "frame,time_s,frametime_ms\n"
TRACE_HEADER = "frame,return_ns,interval_ns,present_begin_ns,renderer_begin_ns,renderer_end_ns,vcore_back_ns\n"
PERF_HEADER = "frame,ms,pipe_waits,pipe_wait_ms,left_out,translate_ms,uploads,upload_mb,textures,memsync_ms,pipelines_ms,uploads_ms,programs_ms,slot_wait_ms,gpu_behind_ms,draw_ms,desc_ms,cmds_ms,tex_lookup_ms,textures_gone,late_wait_ms,readback_wait_ms,tex_frame_ms\n"


class HookshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = {"schema_version": 1, "adapter": "hookshot", "session_id": "test",
                         "synthetic": True, "metadata": {}, "frame_log": "frames.csv"}

    def write(self, name, text):
        (self.root / name).write_text(text, encoding="utf-8")

    def load(self, rows="0,0.0000,0.000\n1,0.0167,16.667\n2,0.0333,16.667\n"):
        self.write("frames.csv", HEADER + rows)
        return load_native(self.root, self.manifest)

    def test_intervals_are_derived_from_elapsed_end_with_rounding_uncertainty(self):
        session = self.load()
        self.assertTrue(session["synthetic"])
        self.assertEqual([f["frame_id"] for f in session["frames"]], [1, 2])
        self.assertEqual([f["t_ns"] for f in session["frames"]], [33000, 16633000])
        self.assertEqual(session["frames"][0]["frame_ms"], 16.667)
        self.assertGreaterEqual(session["frames"][0]["uncertainty_ns"], 50500)
        self.assertEqual(session["frames"][0]["source"], {"file": "frames.csv", "line": 3})
        digest = hashlib.sha256((self.root / "frames.csv").read_bytes()).hexdigest()
        self.assertIn({"file": "frames.csv", "sha256": digest}, session["provenance"])

    def test_headerless_or_wrong_header_cannot_silently_relabel_columns(self):
        for content in ("0,0.0000,0.000\n1,0.0167,16.667\n", "frame,ms,frametime_ms\n0,0,0\n"):
            with self.subTest(content=content):
                self.write("frames.csv", content)
                with self.assertRaises(ValueError):
                    load_native(self.root, self.manifest)

    def test_elapsed_clock_reversal_rejected(self):
        with self.assertRaises(ValueError):
            self.load("0,0.0000,0.000\n1,0.0200,20.000\n2,0.0100,10.000\n")

    def test_duplicate_frame_rejected(self):
        with self.assertRaises(ValueError):
            self.load("0,0.0000,0.000\n1,0.0167,16.667\n1,0.0333,16.667\n")

    def test_invalid_duration_or_inconsistent_elapsed_rejected(self):
        for rows in ("0,0.0000,0.000\n1,0.0167,nan\n", "0,0.0000,0.000\n1,0.0167,-1\n",
                     "0,0.0000,0.000\n1,0.0167,80.000\n", "0,0.0000,0.000\n1,inf,16.667\n"):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.load(rows)

    def test_source_frame_gap_is_reported_without_inventing_missing_frames(self):
        session = self.load("0,0.0000,0.000\n1,0.0167,16.667\n3,0.0500,16.667\n")
        self.assertEqual([f["frame_id"] for f in session["frames"]], [1, 3])
        self.assertTrue(any("gap" in w.lower() for w in session["warnings"]))

    def test_log_timestamps_or_numbers_in_message_never_create_join(self):
        self.write("hookshot_log.txt", "[hos host] vk: present 1: a slow shader 27 ms\n2026-01-01 gpu hang\n")
        self.manifest["log"] = "hookshot_log.txt"
        session = self.load()
        self.assertEqual(len(session["events"]), 2)
        self.assertTrue(all(e["t_ns"] is None and e["frame_id"] is None for e in session["events"]))
        self.assertEqual(session["events"][0]["source"], {"file": "hookshot_log.txt", "line": 1})

    def test_native_game_present_ids_never_join_display_present_ids(self):
        self.write("present.csv", TRACE_HEADER + "1,1000000000,0,999000000,999100000,999200000,999300000\n"
                   "2,1016667000,16667000,1015667000,1015767000,1015867000,1015967000\n")
        self.manifest["present_trace"] = "present.csv"
        session = self.load()
        self.assertEqual(len(session["events"]), 2)
        self.assertTrue(all(e["t_ns"] is None and e["frame_id"] is None for e in session["events"]))
        self.assertIn("1016667000", session["events"][1]["message"])
        self.assertTrue(any("clock" in w.lower() for w in session["warnings"]))

    def test_bad_present_phase_order_rejected(self):
        self.write("present.csv", TRACE_HEADER + "1,1000000000,0,999000000,999300000,999200000,999400000\n")
        self.manifest["present_trace"] = "present.csv"
        with self.assertRaises(ValueError):
            self.load()

    def test_captures_without_declared_alignment_remain_unjoined(self):
        (self.root / "vk_1.png").write_bytes(b"fixture")
        self.manifest["captures"] = [{"path": "vk_1.png"}]
        session = self.load()
        self.assertIsNone(session["captures"][0]["frame_id"])
        self.assertIsNone(session["captures"][0]["t_ns"])
        self.assertEqual(session["captures"][0]["path"], str(self.root / "vk_1.png"))

    def test_traversal_symlink_and_absolute_sources_rejected(self):
        self.write("frames.csv", HEADER + "0,0.0000,0.000\n1,0.0167,16.667\n")
        outside = self.root.parent / (self.root.name + "-outside.csv")
        outside.write_text(HEADER, encoding="utf-8")
        self.addCleanup(outside.unlink)
        (self.root / "linked.csv").symlink_to(outside)
        for path in ("../" + outside.name, str(outside), "linked.csv"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                load_native(self.root, {**self.manifest, "frame_log": path})

    def test_synthetic_flag_is_required_instead_of_assuming_real_session(self):
        self.manifest.pop("synthetic")
        with self.assertRaises(ValueError):
            self.load()

    def test_performance_intervals_reconstruct_timeline_and_attach_same_row_metrics(self):
        # Public export rows, synthetic values: second interval is 90 ms with 70 ms pipeline wait.
        self.write("hookshot_frames.csv", PERF_HEADER +
                   "1,16.67,0,0.00,0,0.0,0,0.00,3,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0,0.00,0.00,0.00\n" +
                   "2,90.00,1,70.00,0,0.0,0,0.00,3,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0,0.00,0.00,0.00\n" +
                   "3,16.67,0,0.00,0,0.0,0,0.00,3,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0,0.00,0.00,0.00\n")
        manifest = {**self.manifest, "performance_trace": "hookshot_frames.csv"}
        manifest.pop("frame_log")
        session = load_native(self.root, manifest)
        self.assertEqual([f["t_ns"] for f in session["frames"]], [0, 16670000, 106670000])
        self.assertEqual(session["frames"][0]["phase"], "warmup")
        self.assertEqual(session["frames"][1]["frame_ms"], 90.0)
        self.assertGreaterEqual(session["frames"][2]["uncertainty_ns"], 10000)
        event = next(e for e in session["events"] if e["kind"] == "pipe_wait_ms")
        self.assertEqual(event["frame_id"], 2)
        self.assertIsNone(event["t_ns"])
        self.assertEqual(event["duration_ms"], 70.0)
        self.assertEqual(event["source"], {"file": "hookshot_frames.csv", "line": 3})
        self.assertTrue(any("reconstruct" in w.lower() for w in session["warnings"]))

    def test_performance_and_display_sources_cannot_silently_merge(self):
        self.manifest["performance_trace"] = "performance.csv"
        with self.assertRaises(ValueError):
            self.load()

    def test_capture_wrong_frame_domain_clears_join_identity(self):
        (self.root / "shot.png").write_bytes(b"fixture")
        self.manifest["captures"] = [{"path": "shot.png", "frame_id": 1,
                                      "frame_domain": "hookshot.game_present"}]
        session = self.load()
        capture = session["captures"][0]
        self.assertIsNone(capture["frame_id"])
        self.assertEqual(capture["native_frame_id"], 1)


if __name__ == "__main__":
    unittest.main()
