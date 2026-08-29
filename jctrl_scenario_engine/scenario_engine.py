"""
scenario_engine.py
===================
The Scenario Engine: generates vehicles and advances their state over
simulation time. This module is intentionally "dumb" about anything
outside vehicle motion:

  - It does NOT render anything (no Pygame, no drawing).
  - It does NOT decide traffic signal timing/logic (no ML model, no
    priority calculation).
  - It does NOT know about SignalState or any UI concept.

The only thing it accepts from the outside world is an OPTIONAL
`right_of_way` set passed into `tick()`, describing which approaches
currently have a green light. That's a plain, stateless input the
caller (a controller/renderer) computes and hands in each tick - the
engine itself never decides it. If the caller doesn't pass anything,
every approach is treated as open (free-flow), so this module is fully
usable standalone (see demo.py).

Public API
----------
    engine = ScenarioEngine(scenario_config, seed=42)
    vehicle_states = engine.tick(dt, right_of_way={"N"})   # -> List[dict]
"""

import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .geometry import IntersectionGeometry
from .scenarios import ScenarioConfig
from .vehicle_state import DIRECTIONS, VehicleState

# Base cruise speed per vehicle type, in simulation units / second.
# Small per-vehicle jitter is applied on spawn for variety.
BASE_SPEED = {
    "car": 14.0,
    "bus": 10.0,
    "truck": 9.0,
    "ambulance": 18.0,
}


@dataclass
class _InternalVehicle:
    """Engine-private vehicle record. Never exposed directly - converted
    to a VehicleState dict at the end of each tick."""
    id: str
    approach: str
    distance_to_center: float
    speed: float
    vehicle_type: str
    waiting: bool = False


class ScenarioEngine:
    """
    Generates and advances vehicle state for one four-way intersection.

    Parameters
    ----------
    scenario : ScenarioConfig
        Describes arrival rates per approach (and vehicle type mix).
    seed : int
        Random seed. Two engines built with the same scenario and seed,
        ticked with the same dt sequence, produce IDENTICAL vehicle
        streams - this is what makes baseline-vs-JCTRL comparisons fair.
    geometry : IntersectionGeometry, optional
        Override default intersection geometry/spacing.
    """

    def __init__(
        self,
        scenario: ScenarioConfig,
        seed: int = 42,
        geometry: Optional[IntersectionGeometry] = None,
    ):
        self.scenario = scenario
        self.seed = seed
        self.geometry = geometry or IntersectionGeometry()
        self._rng = random.Random(seed)
        self.sim_time = 0.0
        self._vehicle_counter = 0
        self._active: Dict[str, List[_InternalVehicle]] = {d: [] for d in DIRECTIONS}
        self._next_spawn_in: Dict[str, float] = {
            d: self._sample_interarrival(d) for d in DIRECTIONS
        }

    # -- public API --------------------------------------------------

    def tick(self, dt: float, right_of_way: Optional[Iterable[str]] = None) -> List[dict]:
        """
        Advance the simulation by `dt` seconds and return the full list
        of currently-active vehicles as plain dicts matching the
        VehicleState contract.

        `right_of_way`: iterable of approaches ("N"/"S"/"E"/"W") that
        currently have a green light, supplied by the caller. If None,
        every approach is treated as open (pure free-flow generation -
        useful for testing the engine in isolation).
        """
        if dt <= 0:
            raise ValueError("dt must be > 0")

        self.sim_time += dt
        open_set = set(right_of_way) if right_of_way is not None else set(DIRECTIONS)

        self._spawn_new_vehicles(dt)

        output: List[dict] = []
        for direction in DIRECTIONS:
            vehicles = self._active[direction]
            # front of queue = smallest distance_to_center (closest to junction)
            vehicles.sort(key=lambda v: v.distance_to_center)
            self._advance_approach(vehicles, dt, is_open=direction in open_set)

            still_active = [
                v for v in vehicles
                if v.distance_to_center > -self.geometry.exit_distance
            ]
            self._active[direction] = still_active

            for v in still_active:
                x, y = self.geometry.position_for(direction, v.distance_to_center)
                output.append(
                    VehicleState(
                        id=v.id,
                        x=x,
                        y=y,
                        speed=v.speed,
                        direction=direction,
                        vehicle_type=v.vehicle_type,
                        waiting=v.waiting,
                    ).to_dict()
                )
        return output

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset the engine to t=0 with a fresh (or new) seed."""
        self.__init__(self.scenario, seed=seed if seed is not None else self.seed, geometry=self.geometry)

    # -- internal helpers ---------------------------------------------

    def _sample_interarrival(self, direction: str) -> float:
        rate = max(self.scenario.rate(direction, self.sim_time), 1e-6)
        return self._rng.expovariate(rate)

    def _choose_vehicle_type(self) -> str:
        weights = self.scenario.vehicle_type_weights
        types = list(weights.keys())
        probs = list(weights.values())
        return self._rng.choices(types, weights=probs, k=1)[0]

    def _spawn_new_vehicles(self, dt: float) -> None:
        for direction in DIRECTIONS:
            self._next_spawn_in[direction] -= dt
            # while-loop handles large dt spawning more than one vehicle
            while self._next_spawn_in[direction] <= 0:
                self._spawn_vehicle(direction)
                self._next_spawn_in[direction] += self._sample_interarrival(direction)

    def _spawn_vehicle(self, direction: str) -> None:
        self._vehicle_counter += 1
        vtype = self._choose_vehicle_type()
        speed = BASE_SPEED[vtype] * self._rng.uniform(0.9, 1.1)
        vehicle = _InternalVehicle(
            id=f"{direction}-{self._vehicle_counter:05d}",
            approach=direction,
            distance_to_center=self.geometry.spawn_distance,
            speed=speed,
            vehicle_type=vtype,
        )
        self._active[direction].append(vehicle)

    def _advance_approach(self, vehicles: List[_InternalVehicle], dt: float, is_open: bool) -> None:
        """
        Simple car-following on a single approach (single lane, MVP - no
        turning movements). Vehicles must be pre-sorted front-to-back
        (ascending distance_to_center) before calling this.
        """
        stop_line = self.geometry.stop_line_distance
        gap = self.geometry.vehicle_gap
        prev_distance = None

        for v in vehicles:
            # a vehicle that has already reached/crossed the stop line is
            # "committed" and keeps going regardless of the current light,
            # matching how real vehicles don't reverse out of an intersection
            committed = v.distance_to_center <= 0.0
            naive_next = v.distance_to_center - v.speed * dt

            if committed or is_open:
                new_distance = naive_next
            else:
                # allowed to approach the stop line, not allowed to cross it
                new_distance = max(naive_next, stop_line)

            if prev_distance is not None:
                min_allowed = prev_distance + gap
                if new_distance < min_allowed:
                    new_distance = min_allowed

            v.waiting = (not committed) and (not is_open) and (new_distance <= stop_line + 1e-6)
            v.distance_to_center = new_distance
            prev_distance = new_distance
