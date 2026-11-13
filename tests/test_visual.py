"""Synthetic patterns exercise candidate gating, never diagnose real game bugs."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None

from urd.visual import analyze_visual


@unittest.skipIf(Image is None, "Pillow optional")
class VisualTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.session = {"schema_version": 1, "session_id": "visual-synthetic", "synthetic": True,
                        "metadata": {"frame_domain": "normalized.frame", "clock_domain": "test.monotonic"},
                        "captures": [], "frames": [], "provenance": []}

    def texture(self, offset=0):
        image = Image.new("RGB", (160, 90), (80, 80, 80))
        draw = ImageDraw.Draw(image)
        for x in range(0, 160, 10):
            for y in range(0, 90, 10):
                shade = 70 + (((x // 10 + offset) * 7 + (y // 10) * 3) % 9) * 10
                draw.rectangle((x, y, x + 9, y + 9), fill=(shade,) * 3)
        return image

    def add(self, frame_id, image, **attrs):
        path = self.root / f"capture_{len(self.session['captures'])}.png"
        image.save(path)
        self.session["captures"].append({"path": str(path), "frame_id": frame_id, "t_ns": None, **attrs})

    def test_persistent_black_candidate_needs_dense_textured_bracketing(self):
        self.add(10, self.texture())
        for number in (11, 12, 13):
            self.add(number, Image.new("RGB", (160, 90), "black"))
        self.add(14, self.texture())
        original = copy.deepcopy(self.session)
        result = analyze_visual(self.session)
        candidate = next(c for c in result["candidates"] if c["kind"] == "persistent_black")
        self.assertEqual(candidate["status"], "candidate_not_proven")
        self.assertEqual(candidate["confidence"], "low")
        self.assertEqual([c["frame_id"] for c in candidate["evidence"]], [10, 11, 12, 13, 14])
        self.assertTrue(result["synthetic"])
        self.assertTrue(candidate["limitations"])
        self.assertEqual(self.session, original)

    def test_uniform_dark_scene_without_bracketing_is_not_a_bug_candidate(self):
        for number in range(6):
            self.add(number, Image.new("RGB", (160, 90), "black"))
        self.assertEqual(analyze_visual(self.session)["candidates"], [])

    def test_local_one_frame_flash_returns_to_similar_textured_neighbors(self):
        background = self.texture()
        flash = background.copy()
        ImageDraw.Draw(flash).rectangle((40, 20, 79, 49), fill="white")
        self.add(1, background)
        self.add(2, flash)
        self.add(3, background)
        result = analyze_visual(self.session)
        flashes = [c for c in result["candidates"] if c["kind"] == "isolated_local_flash"]
        self.assertEqual(len(flashes), 1)
        self.assertEqual([c["frame_id"] for c in flashes[0]["evidence"]], [1, 2, 3])

    def test_global_change_remains_ambiguous(self):
        self.add(1, self.texture())
        self.add(2, Image.new("RGB", (160, 90), "white"))
        self.add(3, self.texture())
        result = analyze_visual(self.session)
        self.assertEqual(result["candidates"], [])
        self.assertTrue(any("global" in w.lower() for w in result["warnings"]))

    def test_ordinary_camera_motion_is_not_a_flash(self):
        for number in range(5):
            self.add(number, self.texture(number))
        self.assertEqual(analyze_visual(self.session)["candidates"], [])

    def test_repeated_textured_frames_require_explicit_expected_motion(self):
        images = [self.texture(1), self.texture(0), self.texture(0), self.texture(0), self.texture(2)]
        for number, image in enumerate(images):
            self.add(number, image)
        self.assertEqual(analyze_visual(self.session)["candidates"], [])
        self.session["metadata"]["expected_motion"] = True
        result = analyze_visual(self.session)
        repeats = [c for c in result["candidates"] if c["kind"] == "repeated_during_expected_motion"]
        self.assertEqual(len(repeats), 1)
        self.assertEqual([c["frame_id"] for c in repeats[0]["evidence"]], [0, 1, 2, 3, 4])

    def test_sparse_or_missing_identity_never_uses_filename_or_mtime(self):
        for number, image in zip((0, 100, 200), (self.texture(), Image.new("RGB", (160, 90), "white"), self.texture())):
            self.add(number, image)
        result = analyze_visual(self.session)
        self.assertEqual(result["candidates"], [])
        self.assertTrue(any("sparse" in w.lower() for w in result["warnings"]))
        for capture in self.session["captures"]:
            capture["frame_id"] = None
        result = analyze_visual(self.session)
        self.assertEqual(result["candidates"], [])
        self.assertTrue(any("identity" in w.lower() for w in result["warnings"]))

    def test_generated_frame_kind_is_excluded_from_flash_triplets(self):
        background = self.texture()
        flash = background.copy()
        ImageDraw.Draw(flash).rectangle((40, 20, 79, 49), fill="white")
        self.add(1, background, frame_kind="game")
        self.add(2, flash, frame_kind="generated")
        self.add(3, background, frame_kind="game")
        self.assertEqual(analyze_visual(self.session)["candidates"], [])

    def test_framegen_without_sample_kinds_is_ambiguous(self):
        self.session["metadata"]["frame_generation"] = True
        background = self.texture()
        flash = background.copy()
        ImageDraw.Draw(flash).rectangle((40, 20, 79, 49), fill="white")
        for number, image in enumerate((background, flash, background)):
            self.add(number, image)
        result = analyze_visual(self.session)
        self.assertEqual(result["candidates"], [])
        self.assertTrue(any("generation" in w.lower() for w in result["warnings"]))

    def test_corrupt_and_size_changed_images_are_skipped_safely(self):
        self.add(1, self.texture())
        self.add(2, Image.new("RGB", (80, 45), "white"))
        self.add(3, self.texture())
        corrupt = self.root / "corrupt.png"
        corrupt.write_bytes(b"not an image")
        self.session["captures"].append({"path": str(corrupt), "frame_id": 4})
        result = analyze_visual(self.session)
        self.assertEqual(result["candidates"], [])
        self.assertTrue(any("size" in w.lower() for w in result["warnings"]))
        self.assertTrue(any("unreadable" in w.lower() for w in result["warnings"]))

    def test_loading_phase_is_not_flagged(self):
        self.add(10, self.texture())
        for number in (11, 12, 13):
            self.add(number, Image.new("RGB", (160, 90), "black"))
            self.session["frames"].append({"frame_id": number, "phase": "loading"})
        self.add(14, self.texture())
        self.assertEqual(analyze_visual(self.session)["candidates"], [])

    def test_conflicting_timestamp_cannot_override_frame_identity(self):
        background = self.texture()
        flash = background.copy()
        ImageDraw.Draw(flash).rectangle((40, 20, 79, 49), fill="white")
        for number, image in enumerate((background, flash, background)):
            self.add(number, image, t_ns=number * 10_000_000)
            self.session["frames"].append({"frame_id": number, "t_ns": number * 10_000_000,
                                           "frame_ms": 10.0})
        self.session["captures"][1]["t_ns"] = 90_000_000
        result = analyze_visual(self.session)
        self.assertEqual(result["candidates"], [])
        self.assertTrue(any("disagree" in w.lower() for w in result["warnings"]))

    def test_capture_count_is_bounded(self):
        for number in range(130):
            self.add(number, self.texture())
        result = analyze_visual(self.session)
        self.assertLessEqual(result["summary"]["images_read"], 128)
        self.assertTrue(any("limit" in w.lower() for w in result["warnings"]))

    def test_oversized_image_is_not_decoded(self):
        self.add(1, Image.new("L", (4097, 4097), 0))
        result = analyze_visual(self.session)
        self.assertEqual(result["summary"]["images_read"], 0)
        self.assertEqual(result["candidates"], [])

    def test_total_pixel_budget_stops_many_large_captures(self):
        path = self.root / "reused.png"
        Image.new("L", (1024, 1024), 80).save(path)
        self.session["captures"] = [{"path": str(path), "frame_id": frame} for frame in range(100)]
        result = analyze_visual(self.session)
        self.assertEqual(result["summary"]["images_read"], 64)
        self.assertTrue(any("pixel limit" in warning.lower() for warning in result["warnings"]))

    def test_pillow_absence_returns_explicit_unavailable(self):
        with patch.dict("sys.modules", {"PIL": None}):
            result = analyze_visual(self.session)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["candidates"], [])


if __name__ == "__main__":
    unittest.main()
