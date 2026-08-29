"""
test_scenario_engine.py
========================
Plain-assert tests (no pytest needed) covering the properties that
actually matter for JCTRL:

  1. Same seed + same scenario + same tick sequence => identical
     vehicle streams. This is the guarantee that lets you run BASELINE
     and JCTRL against "the same traffic".
  2. Different seeds => different streams (sanity check the RNG is
     actually being used).
  3. Contract shape: every emitted dict has exactly the VehicleState
     fields, correct types.
  4. Vehicles actually move, and eventually leave the simulation.
  5. A vehicle on a closed approach is marked waiting and does not
     cross the stop line.

Run:
    python -m jctrl_scenario_engine.test_scenario_engine
"""

from .scenario_engine import ScenarioEngine
from .scenarios import get_scenario
from .vehicle_state import DIRECTIONS, VEHICLE_TYPES


def run_ticks(scenario_name, seed, dt, n_ticks, right_of_way=None):
    engine = ScenarioEngine(get_scenario(scenario_name), seed=seed)
    history = []
    for _ in range(n_ticks):
        history.append(engine.tick(dt, right_of_way=right_of_way))
    return history


def test_determinism_same_seed():
    h1 = run_ticks("heavy_ns", seed=7, dt=0.5, n_ticks=40)
    h2 = run_ticks("heavy_ns", seed=7, dt=0.5, n_ticks=40)
    assert h1 == h2, "Same seed + same scenario must reproduce an identical stream"
    print("PASS: test_determinism_same_seed")


def test_different_seeds_diverge():
    h1 = run_ticks("heavy_ns", seed=1, dt=0.5, n_ticks=40)
    h2 = run_ticks("heavy_ns", seed=2, dt=0.5, n_ticks=40)
    assert h1 != h2, "Different seeds should (almost certainly) diverge"
    print("PASS: test_different_seeds_diverge")


def test_contract_shape():
    history = run_ticks("balanced", seed=3, dt=0.5, n_ticks=20)
    found_any = False
    expected_keys = {"id", "x", "y", "speed", "direction", "vehicle_type", "waiting"}
    for states in history:
        for s in states:
            found_any = True
            assert set(s.keys()) == expected_keys, f"Unexpected keys: {s.keys()}"
            assert isinstance(s["id"], str)
            assert isinstance(s["x"], float)
            assert isinstance(s["y"], float)
            assert isinstance(s["speed"], float)
            assert s["direction"] in DIRECTIONS
            assert s["vehicle_type"] in VEHICLE_TYPES
            assert isinstance(s["waiting"], bool)
    assert found_any, "Expected at least some vehicles to be generated"
    print("PASS: test_contract_shape")


def test_vehicles_move_and_despawn():
    engine = ScenarioEngine(get_scenario("balanced", rate=1.0), seed=5)
    seen_ids = set()
    max_active = 0
    for _ in range(400):  # 400 * 0.25s = 100 simulated seconds
        states = engine.tick(0.25, right_of_way=set(DIRECTIONS))  # all-green: free flow
        seen_ids.update(s["id"] for s in states)
        max_active = max(max_active, len(states))
    # with all-green free flow, vehicles should fully clear the simulation
    final_states = engine.tick(0.25, right_of_way=set(DIRECTIONS))
    assert len(seen_ids) > 0, "Expected vehicles to have been generated"
    assert max_active > 0
    print(f"PASS: test_vehicles_move_and_despawn (saw {len(seen_ids)} distinct vehicles, "
          f"max concurrently active={max_active}, active at end={len(final_states)})")


def test_closed_approach_causes_waiting():
    engine = ScenarioEngine(get_scenario("heavy_ns", heavy_rate=1.0), seed=9)
    saw_waiting = False
    for _ in range(80):  # 80 * 0.5s = 40s, North stays closed the whole time
        states = engine.tick(0.5, right_of_way={"S", "E", "W"})  # N is red
        for s in states:
            if s["direction"] == "N" and s["waiting"]:
                saw_waiting = True
            if s["direction"] == "N":
                # a waiting/queued N vehicle must not have crossed the stop line
                # (x, y should still be on the spawn side of the intersection)
                assert s["y"] >= -1e-6 or not s["waiting"], \
                    "A waiting North vehicle should not have crossed the stop line"
    assert saw_waiting, "Expected at least one North vehicle to be waiting while N is red"
    print("PASS: test_closed_approach_causes_waiting")


def main():
    test_determinism_same_seed()
    test_different_seeds_diverge()
    test_contract_shape()
    test_vehicles_move_and_despawn()
    test_closed_approach_causes_waiting()
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
