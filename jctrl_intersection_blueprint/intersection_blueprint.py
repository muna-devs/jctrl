"""
intersection_blueprint.py

JCTRL - Intersection Blueprint module.

Responsibility (and ONLY responsibility):
    - Own the visual model of a 4-way intersection (roads, lanes, signals).
    - Accept VehicleState[] and SignalState from the outside world.
    - Render current vehicle positions and current signal state.
    - Derive basic TrafficState metrics (vehicle_count, queue_length,
      average_wait) per approach (N/S/E/W).
    - Provide a tick() interface so any external driver (a demo script,
      the real Scenario Engine, a test harness, etc.) can advance time.

This module deliberately does NOT:
    - generate vehicles or scenarios
    - decide signal phases/timings
    - run any ML / adaptive control
    - talk to a network, server, or client

It only consumes the two input contracts (VehicleState, SignalState) and
produces the one output contract (TrafficState). Everything else in the
JCTRL pipeline is out of scope here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

import pygame

# --------------------------------------------------------------------------
# CONTRACTS
# --------------------------------------------------------------------------
# These are the data shapes that flow across module boundaries. They are
# intentionally simple and framework-agnostic (plain dataclasses). Both
# dataclass instances and plain dicts (e.g. parsed JSON) are accepted at
# the public API boundary via the `from_dict` helpers / normalization in
# IntersectionBlueprint.update_vehicles / update_signal.

DIRECTIONS = ("N", "S", "E", "W")
VEHICLE_TYPES = ("car", "bus", "truck", "ambulance")


@dataclass
class VehicleState:
    id: str
    x: float
    y: float
    speed: float
    direction: str          # "N" | "S" | "E" | "W"
    vehicle_type: str       # "car" | "bus" | "truck" | "ambulance"
    waiting: bool

    @staticmethod
    def from_dict(d: dict) -> "VehicleState":
        return VehicleState(
            id=str(d["id"]),
            x=float(d["x"]),
            y=float(d["y"]),
            speed=float(d["speed"]),
            direction=str(d["direction"]),
            vehicle_type=str(d["vehicle_type"]),
            waiting=bool(d["waiting"]),
        )


@dataclass
class SignalState:
    active_phase: str       # "NS" | "EW"
    state: str              # "GREEN" | "YELLOW" | "RED"
    remaining_time: int

    @staticmethod
    def from_dict(d: dict) -> "SignalState":
        return SignalState(
            active_phase=str(d["active_phase"]),
            state=str(d["state"]),
            remaining_time=int(d["remaining_time"]),
        )


@dataclass
class ApproachMetrics:
    vehicle_count: int = 0
    queue_length: int = 0
    average_wait: float = 0.0

    def to_dict(self) -> dict:
        return {
            "vehicle_count": self.vehicle_count,
            "queue_length": self.queue_length,
            "average_wait": self.average_wait,
        }


@dataclass
class TrafficState:
    N: ApproachMetrics = field(default_factory=ApproachMetrics)
    S: ApproachMetrics = field(default_factory=ApproachMetrics)
    E: ApproachMetrics = field(default_factory=ApproachMetrics)
    W: ApproachMetrics = field(default_factory=ApproachMetrics)

    def to_dict(self) -> dict:
        return {d: getattr(self, d).to_dict() for d in DIRECTIONS}


VehicleStateLike = Union[VehicleState, dict]
SignalStateLike = Union[SignalState, dict]


# --------------------------------------------------------------------------
# VISUAL CONSTANTS
# --------------------------------------------------------------------------

BG_COLOR = (34, 139, 34)          # grass
ROAD_COLOR = (50, 50, 55)
LANE_LINE_COLOR = (230, 230, 230)
STOP_LINE_COLOR = (255, 255, 255)
TEXT_COLOR = (255, 255, 255)
PANEL_BG = (20, 20, 20)

SIGNAL_COLORS = {
    "GREEN": (40, 200, 60),
    "YELLOW": (240, 200, 30),
    "RED": (220, 40, 40),
}

VEHICLE_COLORS = {
    "car": (60, 120, 220),
    "bus": (230, 190, 30),
    "truck": (200, 110, 40),
    "ambulance": (235, 235, 235),
}

ROAD_HALF_WIDTH = 55   # px, half width of each road (covers both directions)
LANE_HALF_WIDTH = 27   # px, half width of a single lane


# --------------------------------------------------------------------------
# INTERSECTION BLUEPRINT
# --------------------------------------------------------------------------

class IntersectionBlueprint:
    """
    Visual + metrics model of a single 4-way intersection.

    Public interface
    -----------------
    update_vehicles(vehicles)   : feed the latest VehicleState[]
    update_signal(signal)       : feed the latest SignalState
    tick(dt_seconds)            : advance internal clock (wait accumulation)
    get_traffic_state()         : -> TrafficState (dict-convertible)
    render(surface)             : draw current frame onto a pygame Surface

    The blueprint has NO knowledge of where vehicles/signals come from.
    It is safe to drive with hand-written mock data (see demo.py / the
    __main__ block below) or with real upstream modules later.
    """

    def __init__(self, width: int = 900, height: int = 900):
        self.width = width
        self.height = height
        self.cx = width // 2
        self.cy = (height - 140) // 2 + 20  # leave room for bottom HUD panel

        self.vehicles: List[VehicleState] = []
        self.signal: SignalState = SignalState(active_phase="NS", state="RED", remaining_time=0)

        # id -> accumulated waiting time in seconds (metrics only; this is
        # NOT scenario generation, it's derived bookkeeping required to
        # produce the average_wait field of TrafficState).
        self._wait_accum: Dict[str, float] = {}

        self._font = None
        self._font_small = None

    # ---- lazy font init (allows headless construction before pygame.init) --
    def _ensure_fonts(self):
        if self._font is None:
            self._font = pygame.font.SysFont("consolas", 20)
            self._font_small = pygame.font.SysFont("consolas", 16)

    # ---------------------------------------------------------------- input
    def update_vehicles(self, vehicles: List[VehicleStateLike]) -> None:
        """Replace the current vehicle snapshot with a new one."""
        normalized: List[VehicleState] = []
        for v in vehicles:
            normalized.append(v if isinstance(v, VehicleState) else VehicleState.from_dict(v))
        self.vehicles = normalized

    def update_signal(self, signal: SignalStateLike) -> None:
        """Replace the current signal snapshot with a new one."""
        self.signal = signal if isinstance(signal, SignalState) else SignalState.from_dict(signal)

    def tick(self, dt_seconds: float = 1.0) -> None:
        """
        Advance the blueprint's internal clock by dt_seconds.

        This is the "simulation loop hook" external modules use to drive
        the blueprint forward in time. It only updates wait-time
        bookkeeping used for TrafficState.average_wait; it does NOT move
        vehicles or change signals (that data must be supplied via
        update_vehicles / update_signal by the owning driver each step).
        """
        current_ids = set()
        for v in self.vehicles:
            current_ids.add(v.id)
            if v.waiting:
                self._wait_accum[v.id] = self._wait_accum.get(v.id, 0.0) + dt_seconds
            else:
                self._wait_accum.setdefault(v.id, 0.0)

        # drop bookkeeping for vehicles that are no longer present
        stale = [vid for vid in self._wait_accum if vid not in current_ids]
        for vid in stale:
            del self._wait_accum[vid]

    # --------------------------------------------------------------- output
    def get_traffic_state(self) -> TrafficState:
        """Compute TrafficState from the current vehicle snapshot."""
        state = TrafficState()
        for d in DIRECTIONS:
            group = [v for v in self.vehicles if v.direction == d]
            queued = [v for v in group if v.waiting]
            avg_wait = 0.0
            if group:
                avg_wait = sum(self._wait_accum.get(v.id, 0.0) for v in group) / len(group)
            metrics = ApproachMetrics(
                vehicle_count=len(group),
                queue_length=len(queued),
                average_wait=round(avg_wait, 2),
            )
            setattr(state, d, metrics)
        return state

    # ------------------------------------------------------------- render
    def render(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        surface.fill(BG_COLOR)
        self._draw_roads(surface)
        self._draw_signals(surface)
        self._draw_vehicles(surface)
        self._draw_hud(surface)

    def _draw_roads(self, surface: pygame.Surface) -> None:
        cx, cy = self.cx, self.cy
        w, h = self.width, self.height - 140

        # vertical road (N-S)
        pygame.draw.rect(
            surface, ROAD_COLOR,
            (cx - ROAD_HALF_WIDTH, 0, ROAD_HALF_WIDTH * 2, h)
        )
        # horizontal road (E-W)
        pygame.draw.rect(
            surface, ROAD_COLOR,
            (0, cy - ROAD_HALF_WIDTH, w, ROAD_HALF_WIDTH * 2)
        )

        # lane divider (center line) - dashed
        self._dashed_line(surface, (cx, 0), (cx, cy - ROAD_HALF_WIDTH))
        self._dashed_line(surface, (cx, cy + ROAD_HALF_WIDTH), (cx, h))
        self._dashed_line(surface, (0, cy), (cx - ROAD_HALF_WIDTH, cy))
        self._dashed_line(surface, (cx + ROAD_HALF_WIDTH, cy), (w, cy))

        # stop lines
        pygame.draw.line(surface, STOP_LINE_COLOR,
                          (cx - ROAD_HALF_WIDTH, cy - ROAD_HALF_WIDTH - 2),
                          (cx, cy - ROAD_HALF_WIDTH - 2), 4)          # N approach
        pygame.draw.line(surface, STOP_LINE_COLOR,
                          (cx, cy + ROAD_HALF_WIDTH + 2),
                          (cx + ROAD_HALF_WIDTH, cy + ROAD_HALF_WIDTH + 2), 4)  # S approach
        pygame.draw.line(surface, STOP_LINE_COLOR,
                          (cx - ROAD_HALF_WIDTH - 2, cy),
                          (cx - ROAD_HALF_WIDTH - 2, cy + ROAD_HALF_WIDTH), 4)  # W approach
        pygame.draw.line(surface, STOP_LINE_COLOR,
                          (cx + ROAD_HALF_WIDTH + 2, cy - ROAD_HALF_WIDTH),
                          (cx + ROAD_HALF_WIDTH + 2, cy), 4)          # E approach

        # intersection box
        pygame.draw.rect(
            surface, (65, 65, 70),
            (cx - ROAD_HALF_WIDTH, cy - ROAD_HALF_WIDTH, ROAD_HALF_WIDTH * 2, ROAD_HALF_WIDTH * 2)
        )

        # road labels
        for label, pos in (("N", (cx, 15)), ("S", (cx, h - 25)),
                            ("E", (w - 25, cy)), ("W", (15, cy))):
            assert self._font_small is not None
            txt = self._font_small.render(label, True, TEXT_COLOR)
            surface.blit(txt, txt.get_rect(center=pos))

    def _dashed_line(self, surface, start, end, dash=10, gap=8):
        x1, y1 = start
        x2, y2 = end
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist == 0:
            return
        dx, dy = (x2 - x1) / dist, (y2 - y1) / dist
        pos = 0.0
        drawing = True
        while pos < dist:
            seg_len = dash if drawing else gap
            nxt = min(pos + seg_len, dist)
            if drawing:
                pygame.draw.line(
                    surface, LANE_LINE_COLOR,
                    (x1 + dx * pos, y1 + dy * pos),
                    (x1 + dx * nxt, y1 + dy * nxt), 2
                )
            pos = nxt
            drawing = not drawing

    def _draw_signals(self, surface: pygame.Surface) -> None:
        cx, cy = self.cx, self.cy
        r = 10
        off = ROAD_HALF_WIDTH + 22

        ns_color = SIGNAL_COLORS.get(self.signal.state, (100, 100, 100)) \
            if self.signal.active_phase == "NS" else SIGNAL_COLORS["RED"]
        ew_color = SIGNAL_COLORS.get(self.signal.state, (100, 100, 100)) \
            if self.signal.active_phase == "EW" else SIGNAL_COLORS["RED"]

        # N/S signal heads
        pygame.draw.circle(surface, (10, 10, 10), (cx - off, cy - off), r + 4)
        pygame.draw.circle(surface, ns_color, (cx - off, cy - off), r)
        pygame.draw.circle(surface, (10, 10, 10), (cx + off, cy + off), r + 4)
        pygame.draw.circle(surface, ns_color, (cx + off, cy + off), r)

        # E/W signal heads
        pygame.draw.circle(surface, (10, 10, 10), (cx + off, cy - off), r + 4)
        pygame.draw.circle(surface, ew_color, (cx + off, cy - off), r)
        pygame.draw.circle(surface, (10, 10, 10), (cx - off, cy + off), r + 4)
        pygame.draw.circle(surface, ew_color, (cx - off, cy + off), r)

    def _draw_vehicles(self, surface: pygame.Surface) -> None:
        for v in self.vehicles:
            color = VEHICLE_COLORS.get(v.vehicle_type, (200, 200, 200))
            size = {"car": 10, "bus": 16, "truck": 15, "ambulance": 11}.get(v.vehicle_type, 10)

            if v.direction in ("N", "S"):
                rect = pygame.Rect(0, 0, size, size * 2)
            else:
                rect = pygame.Rect(0, 0, size * 2, size)
            rect.center = (int(v.x), int(v.y))

            pygame.draw.rect(surface, color, rect, border_radius=3)
            if v.vehicle_type == "ambulance":
                cx_, cy_ = rect.center
                pygame.draw.line(surface, (220, 30, 30), (cx_ - 5, cy_), (cx_ + 5, cy_), 2)
                pygame.draw.line(surface, (220, 30, 30), (cx_, cy_ - 5), (cx_, cy_ + 5), 2)
            if v.waiting:
                pygame.draw.rect(surface, (255, 0, 0), rect, width=2, border_radius=3)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        panel_y = self.height - 140
        pygame.draw.rect(surface, PANEL_BG, (0, panel_y, self.width, 140))

        sig = self.signal
        assert self._font is not None
        sig_txt = self._font.render(
            f"Signal: phase={sig.active_phase}  state={sig.state}  remaining={sig.remaining_time}s",
            True, TEXT_COLOR
        )
        surface.blit(sig_txt, (14, panel_y + 8))

        ts = self.get_traffic_state().to_dict()
        col_w = self.width // 4
        for i, d in enumerate(DIRECTIONS):
            m = ts[d]
            lines = [
                f"{d}",
                f"count: {m['vehicle_count']}",
                f"queue: {m['queue_length']}",
                f"avg wait: {m['average_wait']}s",
            ]
            for j, line in enumerate(lines):
                assert self._font_small is not None
                txt = self._font_small.render(line, True, TEXT_COLOR)
                surface.blit(txt, (14 + i * col_w, panel_y + 40 + j * 20))


# --------------------------------------------------------------------------
# SELF-TEST / INDEPENDENT EXECUTION
# --------------------------------------------------------------------------
# Running this file directly proves the Blueprint works standalone, with
# zero dependency on a Scenario Engine, Signal Controller, or Model. It
# feeds a few hand-written mock VehicleState/SignalState objects in a
# short loop. For a fuller interactive mock simulation, see demo.py.

def _self_test_main():
    pygame.init()
    screen = pygame.display.set_mode((900, 900))
    pygame.display.set_caption("JCTRL - Intersection Blueprint (self-test)")
    clock = pygame.time.Clock()

    blueprint = IntersectionBlueprint(width=900, height=900)

    mock_vehicles = [
        {"id": "v1", "x": 445, "y": 200, "speed": 0, "direction": "N", "vehicle_type": "car", "waiting": True},
        {"id": "v2", "x": 455, "y": 260, "speed": 0, "direction": "N", "vehicle_type": "bus", "waiting": True},
        {"id": "v3", "x": 445, "y": 650, "speed": 8, "direction": "S", "vehicle_type": "car", "waiting": False},
        {"id": "v4", "x": 650, "y": 445, "speed": 0, "direction": "E", "vehicle_type": "ambulance", "waiting": True},
        {"id": "v5", "x": 200, "y": 455, "speed": 6, "direction": "W", "vehicle_type": "truck", "waiting": False},
    ]
    mock_signal = {"active_phase": "NS", "state": "GREEN", "remaining_time": 12}

    blueprint.update_vehicles(mock_vehicles) # type: ignore
    blueprint.update_signal(mock_signal)

    running = True
    frames = 0
    while running and frames < 300:  # auto-close after ~5s so it can run unattended too
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        blueprint.tick(dt_seconds=1 / 60)
        blueprint.render(screen)
        pygame.display.flip()
        clock.tick(60)
        frames += 1

    print("TrafficState (final frame):", blueprint.get_traffic_state().to_dict())
    pygame.quit()


if __name__ == "__main__":
    _self_test_main()
