"""
demo.py
=======
Standalone demo/test for the Scenario Engine. Runs entirely on the
standard library - no Pygame, no external packages.

This script plays the role of a very simple "controller" purely to
exercise the engine's waiting/passing behavior: it round-robins right
of way N -> S -> E -> W every few seconds and feeds that into
engine.tick(). The ENGINE itself has no idea this rotation exists -
it just reacts to whatever `right_of_way` set it's given each tick.

Usage:
    python -m jctrl_scenario_engine.demo
    python -m jctrl_scenario_engine.demo --scenario heavy_ns --seed 7 --seconds 20
"""

import argparse
import json

from .scenario_engine import ScenarioEngine
from .scenarios import get_scenario, available_scenarios
from .vehicle_state import DIRECTIONS


def run_demo(scenario_name: str, seed: int, seconds: float, dt: float, phase_length: float, print_every: float):
    scenario = get_scenario(scenario_name)
    engine = ScenarioEngine(scenario, seed=seed)

    order = list(DIRECTIONS)
    t = 0.0
    next_print = 0.0

    print(f"=== JCTRL Scenario Engine Demo ===")
    print(f"scenario={scenario_name} seed={seed} duration={seconds}s dt={dt}s")
    print(f"(demo-only round-robin right-of-way every {phase_length}s - the engine itself")
    print(" does not know or care about this rotation)\n")

    while t < seconds:
        phase_index = int(t // phase_length) % len(order)
        open_direction = order[phase_index]

        states = engine.tick(dt, right_of_way={open_direction})
        t += dt

        if t >= next_print:
            waiting_counts = {d: 0 for d in DIRECTIONS}
            total_counts = {d: 0 for d in DIRECTIONS}
            for s in states:
                total_counts[s["direction"]] += 1
                if s["waiting"]:
                    waiting_counts[s["direction"]] += 1

            print(f"--- t={t:5.1f}s | green={open_direction} | active_vehicles={len(states)} ---")
            print("  queue (waiting/total) per approach:",
                  {d: f"{waiting_counts[d]}/{total_counts[d]}" for d in DIRECTIONS})
            # print a couple of raw VehicleState dicts as a contract sample
            for s in states[:2]:
                print("  sample:", json.dumps(s))
            next_print += print_every

    print("\nDemo finished.")


def main():
    parser = argparse.ArgumentParser(description="JCTRL Scenario Engine demo")
    parser.add_argument("--scenario", choices=available_scenarios(), default="heavy_ns")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--dt", type=float, default=0.5)
    parser.add_argument("--phase-length", type=float, default=5.0,
                         help="demo-only: seconds per round-robin green phase")
    parser.add_argument("--print-every", type=float, default=2.0)
    args = parser.parse_args()

    run_demo(
        scenario_name=args.scenario,
        seed=args.seed,
        seconds=args.seconds,
        dt=args.dt,
        phase_length=args.phase_length,
        print_every=args.print_every,
    )


if __name__ == "__main__":
    main()
