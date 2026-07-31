"""Small persistent bandit optimizer for Bloomer placements and builds."""

from __future__ import annotations

import json
import math
from pathlib import Path
import random
from typing import Iterable, Sequence


SCHEMA_VERSION = 1


def point_key(point: Sequence[float]) -> str:
    return f"{float(point[0]):.4f},{float(point[1]):.4f}"


def game_reward(result: str, round_reached: int | None, duration_seconds: float) -> float:
    """Normalize a game outcome; wins dominate and quicker wins break ties."""
    if result == "victory":
        speed_bonus = min(0.50, 120.0 / max(1.0, duration_seconds))
        return 1.0 + speed_bonus
    if round_reached is None:
        return 0.05
    return min(0.975, max(0.0, round_reached / 40.0))


class LearningOptimizer:
    def __init__(
        self,
        state_path: Path | None,
        monkey_name: str,
        exploration: float = 0.45,
        rng: random.Random | None = None,
    ) -> None:
        self.state_path = state_path
        self.monkey_name = monkey_name
        self.exploration = max(0.0, float(exploration))
        self.rng = rng or random.Random()
        self.state = self._load()
        self.profile = self.state.setdefault("monkeys", {}).setdefault(monkey_name, self._new_profile())

    @staticmethod
    def _new_profile() -> dict:
        return {"games": 0, "points": {}, "builds": {}}

    def _load(self) -> dict:
        if self.state_path is None or not self.state_path.exists():
            return {"schema": SCHEMA_VERSION, "monkeys": {}}
        try:
            loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema": SCHEMA_VERSION, "monkeys": {}}
        if loaded.get("schema") != SCHEMA_VERSION or not isinstance(loaded.get("monkeys"), dict):
            return {"schema": SCHEMA_VERSION, "monkeys": {}}
        return loaded

    @property
    def games(self) -> int:
        return int(self.profile.get("games", 0))

    @staticmethod
    def _arm(table: dict, key: str) -> dict:
        return table.setdefault(key, {"uses": 0, "reward": 0.0})

    def _ucb_score(self, arm: dict, total_uses: int) -> float:
        uses = int(arm.get("uses", 0))
        if uses == 0:
            return 10.0 + self.rng.random()
        average = float(arm.get("reward", 0.0)) / uses
        bonus = self.exploration * math.sqrt(math.log(max(2, total_uses + 1)) / uses)
        return average + bonus + self.rng.random() * 1e-6

    def rank_points(self, points: Iterable[Sequence[float]]) -> list[tuple[float, float]]:
        table = self.profile.setdefault("points", {})
        normalized = [(float(point[0]), float(point[1])) for point in points]
        total = sum(
            max(int(value.get("uses", 0)), int(value.get("placement_attempts", 0)))
            for value in table.values()
        )

        def score(point: tuple[float, float]) -> float:
            arm = self._arm(table, point_key(point))
            attempts = int(arm.get("placement_attempts", 0))
            successes = int(arm.get("placement_successes", 0))
            validity = (successes + 1) / (attempts + 2)
            # A rejected placement is an observation even though it never
            # participates in a completed game's reward.
            scoring_arm = arm
            if int(arm.get("uses", 0)) == 0 and attempts:
                scoring_arm = {"uses": attempts, "reward": 0.0}
            return self._ucb_score(scoring_arm, total) + validity * 0.35

        # MacroEngine pops from the end, so the highest-scoring point goes last.
        return sorted(normalized, key=score)

    def choose_build(self, builds: Sequence[tuple[int, int, int]]) -> tuple[int, int, int]:
        table = self.profile.setdefault("builds", {})
        total = sum(int(value.get("uses", 0)) for value in table.values())
        return max(
            builds,
            key=lambda build: self._ucb_score(self._arm(table, "".join(map(str, build))), total),
        )

    def record_placement(self, point: Sequence[float], success: bool) -> None:
        arm = self._arm(self.profile.setdefault("points", {}), point_key(point))
        arm["placement_attempts"] = int(arm.get("placement_attempts", 0)) + 1
        if success:
            arm["placement_successes"] = int(arm.get("placement_successes", 0)) + 1

    def record_game(
        self,
        choices: Iterable[tuple[Sequence[float], str]],
        result: str,
        round_reached: int | None,
        duration_seconds: float,
    ) -> float:
        reward = game_reward(result, round_reached, duration_seconds)
        point_table = self.profile.setdefault("points", {})
        build_table = self.profile.setdefault("builds", {})
        for point, build_label in choices:
            for arm in (
                self._arm(point_table, point_key(point)),
                self._arm(build_table, build_label),
            ):
                arm["uses"] = int(arm.get("uses", 0)) + 1
                arm["reward"] = round(float(arm.get("reward", 0.0)) + reward, 6)
        self.profile["games"] = self.games + 1
        self.save()
        return reward

    def reset(self) -> None:
        self.state.setdefault("monkeys", {})[self.monkey_name] = self._new_profile()
        self.profile = self.state["monkeys"][self.monkey_name]
        self.save()

    def save(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)
