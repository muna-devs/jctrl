"""
scenarios.py
============
Declarative traffic-demand presets. A ScenarioConfig only describes
*how many vehicles arrive per second, per approach, over time* and
*what mix of vehicle types* to generate. It knows nothing about
movement, waiting, or geometry - that's the engine's job.

Each scenario exposes `arrival_rate_fn(direction, sim_time) -> veh/sec`
so rates can be constant (balanced/heavy-NS/heavy-EW) or time-varying
(rush hour).
"""

import math
from dataclasses import dataclass, field
from typing import Callable, Dict

from .vehicle_state import DIRECTIONS, VEHICLE_TYPES

ArrivalRateFn = Callable[[str, float], float]

DEFAULT_TYPE_WEIGHTS: Dict[str, float] = {
    "car": 0.75,
    "bus": 0.12,
    "truck": 0.10,
    "ambulance": 0.03,
}


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    arrival_rate_fn: ArrivalRateFn
    vehicle_type_weights: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_TYPE_WEIGHTS)
    )

    def rate(self, direction: str, sim_time: float) -> float:
        if direction not in DIRECTIONS:
            raise ValueError(f"Unknown direction: {direction!r}")
        return max(0.0, self.arrival_rate_fn(direction, sim_time))


# -------------------------------------------------------------------------
# Preset builders - each returns a fresh ScenarioConfig instance.
# -------------------------------------------------------------------------

def balanced_scenario(rate: float = 0.30) -> ScenarioConfig:
    """All four approaches receive the same, constant arrival rate."""
    return ScenarioConfig(
        name="balanced",
        arrival_rate_fn=lambda direction, t: rate,
    )


def heavy_ns_scenario(heavy_rate: float = 0.70, light_rate: float = 0.15) -> ScenarioConfig:
    """North/South carry heavy traffic; East/West are light."""
    def _rate(direction, t):
        return heavy_rate if direction in ("N", "S") else light_rate
    return ScenarioConfig(name="heavy_ns", arrival_rate_fn=_rate)


def heavy_ew_scenario(heavy_rate: float = 0.70, light_rate: float = 0.15) -> ScenarioConfig:
    """East/West carry heavy traffic; North/South are light."""
    def _rate(direction, t):
        return heavy_rate if direction in ("E", "W") else light_rate
    return ScenarioConfig(name="heavy_ew", arrival_rate_fn=_rate)


def rush_hour_scenario(
    base_rate: float = 0.20,
    peak_rate: float = 0.90,
    peak_time: float = 90.0,
    spread: float = 35.0,
    dominant_direction: str = "N",
    dominant_bonus: float = 0.25,
) -> ScenarioConfig:
    """
    All approaches ramp up to a shared traffic peak around `peak_time`
    (a bell-curve multiplier), modeling a city-wide rush-hour surge.
    `dominant_direction` gets an extra bonus rate on top (e.g. the main
    approach heading into a city center during the morning rush).
    """
    def _rate(direction, t):
        bell = math.exp(-((t - peak_time) ** 2) / (2 * spread ** 2))
        r = base_rate + (peak_rate - base_rate) * bell
        if direction == dominant_direction:
            r += dominant_bonus * bell
        return r
    return ScenarioConfig(name="rush_hour", arrival_rate_fn=_rate)


_REGISTRY: Dict[str, Callable[..., ScenarioConfig]] = {
    "balanced": balanced_scenario,
    "heavy_ns": heavy_ns_scenario,
    "heavy_ew": heavy_ew_scenario,
    "rush_hour": rush_hour_scenario,
}


def get_scenario(name: str, **kwargs) -> ScenarioConfig:
    """Factory lookup by name: get_scenario('heavy_ns', heavy_rate=0.8)."""
    try:
        builder = _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown scenario '{name}'. Available: {sorted(_REGISTRY)}"
        ) from None
    return builder(**kwargs)


def available_scenarios():
    return sorted(_REGISTRY)
