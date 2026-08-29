"""
vehicle_state.py
=================
Defines the VehicleState contract exchanged between the Scenario Engine
and any downstream consumer (renderer, controller, ML model, etc).

This module has NO dependency on the engine, geometry, or scenarios -
it only defines the shared data shape so both sides can agree on it.
"""

from dataclasses import dataclass, asdict

# Canonical set of intersection approaches. "direction" on a VehicleState
# means "which approach this vehicle belongs to" (N/S/E/W leg of the
# junction) - NOT its compass heading. A vehicle with direction="N" is
# on the North approach, traveling toward and through the intersection.
DIRECTIONS = ("N", "S", "E", "W")

VEHICLE_TYPES = ("car", "bus", "truck", "ambulance")


@dataclass(frozen=True)
class VehicleState:
    """Public, serializable snapshot of one vehicle at one simulation tick."""
    id: str
    x: float
    y: float
    speed: float
    direction: str          # one of DIRECTIONS
    vehicle_type: str       # one of VEHICLE_TYPES
    waiting: bool

    def to_dict(self) -> dict:
        """Plain-dict form matching the contract exactly (JSON-serializable)."""
        return asdict(self)
