import random
import ctypes
import unittest

from bloomer import (
    DEFAULT_CONFIG,
    MONKEYS,
    MacroEngine,
    INPUT,
    PixelFrame,
    PlacedTower,
    classify_end_screen,
    deep_merge,
    generate_build,
    image_diff_score,
    parse_cash_text,
    prepare_cash_ocr_frame,
    target_map_name,
)
from btd6_costs import PURCHASE_COSTS, tower_cost, upgrade_cost


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

    def test_command_timing_defaults_are_user_safe(self):
        loop = DEFAULT_CONFIG["loop"]
        self.assertGreaterEqual(loop["fast_forward_delay_seconds"], 0.20)
        self.assertGreaterEqual(loop["command_delay_seconds"], 0.10)
        self.assertGreaterEqual(loop["action_interval_seconds"], 0.5)

    def test_purchase_costs_cover_every_supported_monkey(self):
        self.assertEqual(set(PURCHASE_COSTS), set(MONKEYS))
        for name in MONKEYS:
            self.assertGreater(tower_cost(name), 0)
            for path in range(3):
                for tier in range(4):
                    self.assertGreater(upgrade_cost(name, path, tier), 0)

    def test_budget_gate_blocks_unaffordable_actions(self):
        class CashReader:
            last_text = "$650"

            def read(self, _image):
                return 650

        engine = MacroEngine.__new__(MacroEngine)
        engine.cash_reader = CashReader()
        engine._budget_notice = ""
        engine._screenshot = lambda: PixelFrame.solid(1, 1, (0, 0, 0))
        engine.log = lambda _message: None

        self.assertFalse(engine._can_afford(700, "test tower"))
        self.assertTrue(engine._can_afford(600, "test tower"))

    def test_game_start_uses_exactly_one_double_press(self):
        class Controller:
            def __init__(self):
                self.keys = []

            def press(self, key):
                self.keys.append(key)

        engine = MacroEngine.__new__(MacroEngine)
        engine.config = {
            "hotkeys": {"start_round": "space"},
            "loop": {"fast_forward_delay_seconds": 0.55},
        }
        engine.controller = Controller()
        engine._wait = lambda seconds: seconds == 0.55
        engine.log = lambda _message: None

        self.assertTrue(engine._start_game_fast_forward())
        self.assertEqual(engine.controller.keys, ["space", "space"])

    def test_unavailable_upgrade_path_can_be_skipped(self):
        tower = PlacedTower("Boomerang Monkey", (0.2, 0.3), (4, 2, 0), [0, 1, 0, 1, 0, 0])
        tower.upgrade_index = 2
        tower.failed_upgrades = 4

        skipped = tower.skip_remaining_path(0)

        self.assertEqual(skipped, 3)
        self.assertEqual(tower.sequence, [0, 1, 1])
        self.assertEqual(tower.upgrade_index, 2)
        self.assertFalse(tower.complete)
        self.assertEqual(tower.failed_upgrades, 0)

    def test_skipping_last_available_path_completes_tower(self):
        tower = PlacedTower("Dart Monkey", (0.2, 0.3), (4, 0, 2), [2, 2, 0, 0, 0, 0])
        tower.upgrade_index = 2

        self.assertEqual(tower.skip_remaining_path(0), 4)
        self.assertTrue(tower.complete)


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

    def test_cash_ocr_parser_handles_symbols_and_common_substitutions(self):
        self.assertEqual(parse_cash_text("$2,423"), 2423)
        self.assertEqual(parse_cash_text("Cash: $65O"), 650)
        self.assertEqual(parse_cash_text("$1 O2O"), 1020)
        self.assertIsNone(parse_cash_text("cash unavailable"))

    def test_cash_ocr_preprocessing_is_scaled_black_on_white(self):
        image = PixelFrame.solid(2, 1, (245, 245, 245))
        image.fill_rect((1, 0, 2, 1), (20, 150, 40))
        prepared = prepare_cash_ocr_frame(image, scale=2)
        self.assertEqual(prepared.size, (4, 2))
        self.assertEqual(tuple(prepared.data[:4]), (0, 0, 0, 255))
        self.assertEqual(tuple(prepared.data[8:12]), (255, 255, 255, 255))

if __name__ == "__main__":
    unittest.main()
