import random
import unittest

from bloomer import (
    DEFAULT_CONFIG,
    MONKEYS,
    PixelFrame,
    classify_end_screen,
    deep_merge,
    generate_build,
    image_diff_score,
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


if __name__ == "__main__":
    unittest.main()
