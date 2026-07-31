import random
import ctypes
import unittest

from bloomer import (
    DEFAULT_CONFIG,
    MONKEYS,
    INPUT,
    PixelFrame,
    classify_end_screen,
    deep_merge,
    generate_build,
    image_diff_score,
    invalid_placement_red_ratio,
    target_map_name,
)


class BuildTests(unittest.TestCase):
    def test_roster_contains_current_25_non_hero_towers(self):
        self.assertEqual(len(MONKEYS), 25)
        self.assertIn("Mermonkey", MONKEYS)
        self.assertIn("Desperado", MONKEYS)

    def test_generated_builds_are_valid_crosspaths(self):
        rng = random.Random(1234)
        seen = set()
        for _ in range(200):
            build, sequence = generate_build(rng, 4)
            seen.add(build)
            self.assertEqual(sorted(build), [0, 2, 4])
            self.assertEqual(len(sequence), 6)
            self.assertEqual(tuple(sequence.count(path) for path in range(3)), build)
        self.assertEqual(len(seen), 6)

    def test_deep_merge_preserves_new_defaults(self):
        merged = deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"b": 9}})
        self.assertEqual(merged, {"a": {"b": 9, "c": 2}})

    def test_target_map_routing(self):
        self.assertEqual(target_map_name(MONKEYS["Dart Monkey"]), "Monkey Meadow")
        self.assertEqual(target_map_name(MONKEYS["Banana Farm"]), "Monkey Meadow")
        self.assertEqual(target_map_name(MONKEYS["Monkey Sub"]), "Spice Islands")
        self.assertEqual(target_map_name(MONKEYS["Mermonkey"]), "Spice Islands")

    def test_search_field_has_separate_calibration_point(self):
        self.assertIn("map_search", DEFAULT_CONFIG["points"])
        self.assertIn("map_search_field", DEFAULT_CONFIG["points"])
        self.assertNotEqual(DEFAULT_CONFIG["points"]["map_search"], DEFAULT_CONFIG["points"]["map_search_field"])

    def test_send_input_structure_has_windows_x64_size(self):
        # Win32 INPUT must be 40 bytes in a 64-bit Python process and 28 bytes in 32-bit.
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(INPUT), expected)

    def test_near_track_profile_replaces_legacy_land_points(self):
        points = DEFAULT_CONFIG["placements"]["monkey_meadow_near_track"]
        self.assertGreaterEqual(len(points), 12)
        self.assertNotIn([0.445, 0.700], points)
        self.assertNotIn([0.650, 0.750], points)


class VisualDetectionTests(unittest.TestCase):
    def make_dialog(self, title_color):
        image = PixelFrame.solid(400, 240, (25, 45, 35))
        image.fill_rect((105, 60, 295, 190), (90, 145, 215))
        image.fill_rect((140, 68, 260, 100), title_color)
        return image

    def test_defeat_dialog(self):
        result = classify_end_screen(self.make_dialog((235, 45, 25)), DEFAULT_CONFIG["detection"])
        self.assertEqual(result, "defeat")

    def test_victory_dialog(self):
        result = classify_end_screen(self.make_dialog((245, 185, 35)), DEFAULT_CONFIG["detection"])
        self.assertEqual(result, "victory")

    def test_bright_map_is_not_end_screen(self):
        image = PixelFrame.solid(400, 240, (25, 175, 70))
        self.assertIsNone(classify_end_screen(image, DEFAULT_CONFIG["detection"]))

    def test_image_difference(self):
        before = PixelFrame.solid(10, 10, (0, 0, 0))
        after = PixelFrame.solid(10, 10, (12, 12, 12))
        self.assertAlmostEqual(image_diff_score(before, after), 12.0)

    def test_invalid_placement_red_ratio(self):
        valid = PixelFrame.solid(20, 20, (60, 180, 70))
        invalid = PixelFrame.solid(20, 20, (220, 45, 35))
        self.assertLess(invalid_placement_red_ratio(valid), 0.01)
        self.assertGreater(invalid_placement_red_ratio(invalid), 0.99)


if __name__ == "__main__":
    unittest.main()
