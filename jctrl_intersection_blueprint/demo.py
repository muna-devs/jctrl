"""
demo.py

Small mock harness that PROVES the Intersection Blueprint works entirely
on its own. Everything in this file is a stand-in / mock:

    - MockVehicleFeed  -> stands in for the future Scenario Engine
    - MockSignalFeed   -> stands in for the future Signal Controller

Neither mock talks to the blueprint's internals. They only ever produce
plain dicts that match the VehicleState / SignalState contracts, and the
blueprint only ever consumes them through its public methods
(update_vehicles, update_signal, tick, render, get_traffic_state).

Run:
    python demo.py
"""

import random
import pygame

from intersection_blueprint import IntersectionBlueprint

WIDTH, HEIGHT = 900, 900
CX, CY = WIDTH // 2, (HEIGHT - 140) // 2 + 20


class MockVehicleFeed:
    """Fake vehicle generator. A real Scenario Engine would replace this
    entirely; the Blueprint would not need to change at all."""

    def __init__(self, n_vehicles=10):
        self._vehicles = []
        for i in range(n_vehicles):
            direction = random.choice(["N", "S", "E", "W"])
            self._vehicles.append(self._spawn(f"veh-{i}", direction))

    def _spawn(self, vid, direction):
        vtype = random.choices(
            ["car", "car", "car", "bus", "truck", "ambulance"],
            weights=[5, 5, 5, 1, 1, 1],
        )[0]
        if direction == "N":
            x, y = CX - 27 + random.randint(0, 20), random.randint(0, CY - 90)
        elif direction == "S":
            x, y = CX + 5 + random.randint(0, 20), random.randint(CY + 90, HEIGHT - 140)
        elif direction == "W":
            x, y = random.randint(0, CX - 90), CY - 27 + random.randint(0, 20)
        else:  # E
            x, y = random.randint(CX + 90, WIDTH), CY + 5 + random.randint(0, 20)

        return {
            "id": vid,
            "x": float(x),
            "y": float(y),
            "speed": 0.0,
            "direction": direction,
            "vehicle_type": vtype,
            "waiting": False,
        }

    def step(self, signal_phase_open):
        """Advance each mock vehicle a little and decide if it's waiting.
        `signal_phase_open` is the set of directions currently allowed to
        move (e.g. {'N', 'S'} when phase=NS/GREEN), purely for the mock's
        own movement logic -- the Blueprint itself never sees this."""
        for v in self._vehicles:
            near_stop = self._near_stop_line(v)
            if near_stop and v["direction"] not in signal_phase_open:
                v["waiting"] = True
                v["speed"] = 0.0
                continue
            v["waiting"] = False
            v["speed"] = 3.0
            if v["direction"] == "N":
                v["y"] += v["speed"]
                if v["y"] > HEIGHT - 140:
                    self._respawn(v)
            elif v["direction"] == "S":
                v["y"] -= v["speed"]
                if v["y"] < 0:
                    self._respawn(v)
            elif v["direction"] == "E":
                v["x"] -= v["speed"]
                if v["x"] < 0:
                    self._respawn(v)
            elif v["direction"] == "W":
                v["x"] += v["speed"]
                if v["x"] > WIDTH:
                    self._respawn(v)
        return self._vehicles

    @staticmethod
    def _near_stop_line(v):
        if v["direction"] == "N":
            return CY - 90 < v["y"] < CY - 27
        if v["direction"] == "S":
            return CY + 27 < v["y"] < CY + 90
        if v["direction"] == "W":
            return CX - 90 < v["x"] < CX - 27
        if v["direction"] == "E":
            return CX + 27 < v["x"] < CX + 90
        return False

    def _respawn(self, v):
        new = self._spawn(v["id"], v["direction"])
        v.update(new)


class MockSignalFeed:
    """Fake fixed-time signal cycle. A real Signal Controller / Model
    would replace this entirely; the Blueprint would not change."""

    CYCLE = [
        ("NS", "GREEN", 6),
        ("NS", "YELLOW", 2),
        ("EW", "GREEN", 6),
        ("EW", "YELLOW", 2),
    ]

    def __init__(self):
        self._idx = 0
        self._remaining = self.CYCLE[0][2]

    def step(self, dt_seconds):
        self._remaining -= dt_seconds
        if self._remaining <= 0:
            self._idx = (self._idx + 1) % len(self.CYCLE)
            self._remaining = self.CYCLE[self._idx][2]
        phase, state, _ = self.CYCLE[self._idx]
        return {
            "active_phase": phase,
            "state": state,
            "remaining_time": max(0, int(round(self._remaining))),
        }

    def open_directions(self):
        phase, state, _ = self.CYCLE[self._idx]
        if state != "GREEN":
            return set()
        return {"N", "S"} if phase == "NS" else {"E", "W"}


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("JCTRL - Intersection Blueprint (mock demo)")
    clock = pygame.time.Clock()

    blueprint = IntersectionBlueprint(width=WIDTH, height=HEIGHT)
    vehicle_feed = MockVehicleFeed(n_vehicles=12)
    signal_feed = MockSignalFeed()

    running = True
    ticks_since_print = 0
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # 1) mock upstream modules produce fresh contract data
        signal_dict = signal_feed.step(dt)
        vehicles_dicts = vehicle_feed.step(signal_feed.open_directions())

        # 2) feed the Blueprint through ITS public interface only
        blueprint.update_vehicles(vehicles_dicts)
        blueprint.update_signal(signal_dict)
        blueprint.tick(dt)

        # 3) render current frame
        blueprint.render(screen)
        pygame.display.flip()

        # 4) occasionally print the derived TrafficState to prove the
        #    output contract is being produced correctly
        ticks_since_print += 1
        if ticks_since_print >= 120:
            ticks_since_print = 0
            print("TrafficState:", blueprint.get_traffic_state().to_dict())

    pygame.quit()


if __name__ == "__main__":
    main()
