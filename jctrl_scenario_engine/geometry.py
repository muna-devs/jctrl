"""
geometry.py
===========
Pure coordinate math for a fixed four-way intersection. No Pygame, no
drawing - just the vector math that turns "how far a vehicle is from
the center, on which approach" into an (x, y) position.

Coordinate system: intersection center is (0, 0). Units are arbitrary
simulation units (a renderer maps these to pixels however it likes).

Each approach has:
  - a "spawn unit vector": the direction FROM the center TOWARD where
    vehicles on that approach are created (i.e. where they start).
  - a small perpendicular lane offset, purely so opposing-direction
    traffic on the same road doesn't overlap at x==0 or y==0.

A vehicle's position is fully described by one scalar,
`distance_to_center`:
  - starts at +spawn_distance (vehicle just spawned)
  - decreases toward 0 as the vehicle approaches/crosses the center
  - continues negative after crossing, until -exit_distance, at which
    point the engine removes the vehicle from the simulation.
"""

from dataclasses import dataclass
from typing import Tuple

from .vehicle_state import DIRECTIONS


@dataclass(frozen=True)
class IntersectionGeometry:
    spawn_distance: float = 200.0     # distance from center where vehicles enter
    exit_distance: float = 200.0      # distance PAST center where vehicles despawn
    stop_line_distance: float = 20.0  # distance from center where a closed
                                       # approach must halt
    vehicle_gap: float = 10.0         # minimum bumper-to-bumper spacing in a queue
    lane_offset: float = 6.0          # perpendicular offset so N/S and E/W
                                       # streams don't overlap visually

    # unit vector pointing FROM center TOWARD this approach's spawn point
    _spawn_unit = {
        "N": (0.0, 1.0),
        "S": (0.0, -1.0),
        "E": (1.0, 0.0),
        "W": (-1.0, 0.0),
    }

    def _perp_offset(self, direction: str) -> Tuple[float, float]:
        """Small perpendicular offset so N/S and E/W streams don't overlap."""
        lo = self.lane_offset
        return {
            "N": (lo, 0.0),
            "S": (-lo, 0.0),
            "E": (0.0, -lo),
            "W": (0.0, lo),
        }[direction]

    def position_for(self, direction: str, distance_to_center: float) -> Tuple[float, float]:
        """Convert (approach, scalar distance) -> (x, y) simulation coordinates."""
        if direction not in DIRECTIONS:
            raise ValueError(f"Unknown direction: {direction!r}")
        sx, sy = self._spawn_unit[direction]
        ox, oy = self._perp_offset(direction)
        x = sx * distance_to_center + ox
        y = sy * distance_to_center + oy
        return (x, y)
