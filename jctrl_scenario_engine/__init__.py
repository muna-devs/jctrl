"""
jctrl_scenario_engine
======================
Rendering-independent traffic scenario engine for the JCTRL project.

    Scenario Engine -> VehicleState[] -> (Intersection Blueprint / Controller / Renderer)

Public API:
    ScenarioEngine        - the engine itself: engine.tick(dt) -> List[dict]
    get_scenario(name)    - factory for built-in scenario presets
    available_scenarios() - list of preset names
    ScenarioConfig        - the config dataclass, if you want a custom scenario
    IntersectionGeometry  - override spacing/geometry if needed
    VehicleState          - the dataclass backing each returned dict
    DIRECTIONS            - ("N", "S", "E", "W")
    VEHICLE_TYPES         - ("car", "bus", "truck", "ambulance")
"""

from .scenario_engine import ScenarioEngine
from .scenarios import (
    ScenarioConfig,
    get_scenario,
    available_scenarios,
    balanced_scenario,
    heavy_ns_scenario,
    heavy_ew_scenario,
    rush_hour_scenario,
)
from .geometry import IntersectionGeometry
from .vehicle_state import VehicleState, DIRECTIONS, VEHICLE_TYPES

__all__ = [
    "ScenarioEngine",
    "ScenarioConfig",
    "get_scenario",
    "available_scenarios",
    "balanced_scenario",
    "heavy_ns_scenario",
    "heavy_ew_scenario",
    "rush_hour_scenario",
    "IntersectionGeometry",
    "VehicleState",
    "DIRECTIONS",
    "VEHICLE_TYPES",
]
