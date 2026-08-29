# JCTRL — Intersection Blueprint module

Independent, self-contained visualization module for the JCTRL traffic
signal simulation prototype. Implements **only** the "Intersection
Blueprint" box in the pipeline:

```
Scenario Engine → VehicleState[] → [Intersection Blueprint] → TrafficState → Model
                                            ↑
SignalState (from Signal Controller) ──────┘
```

It does not generate traffic, decide signal phases, or run any model —
it just renders whatever `VehicleState[]` / `SignalState` it's given, and
derives `TrafficState` from the current vehicle snapshot.

## Project structure

```
jctrl_intersection_blueprint/
├── intersection_blueprint.py   # the module itself (contracts + rendering + metrics)
├── demo.py                     # mock Scenario Engine + Signal Controller stand-ins
├── requirements.txt
└── README.md
```

## Install & run

```bash
pip install -r requirements.txt

# Option A: run the module's own built-in self-test (static mock data)
python intersection_blueprint.py

# Option B: run the fuller mock demo (moving vehicles, cycling signal)
python demo.py
```

Both open a Pygame window showing the 4-way intersection, live vehicle
positions, the current signal phase, and a metrics panel. Close the
window or press the window-close button to quit.

## Public interface (`intersection_blueprint.py`)

### Data contracts
- `VehicleState` — dataclass matching the spec (`id, x, y, speed, direction, vehicle_type, waiting`). Has `VehicleState.from_dict(d)`.
- `SignalState` — dataclass matching the spec (`active_phase, state, remaining_time`). Has `SignalState.from_dict(d)`.
- `TrafficState` — dataclass with one `ApproachMetrics` per direction (`N/S/E/W`), each holding `vehicle_count, queue_length, average_wait`. Call `.to_dict()` to get the plain JSON-shaped dict from the spec.

### `IntersectionBlueprint`
- `IntersectionBlueprint(width=900, height=900)` — construct the blueprint (does not require a live signal/vehicle source).
- `update_vehicles(vehicles: list[dict | VehicleState])` — replace the current vehicle snapshot. Accepts raw dicts (e.g. parsed JSON) or `VehicleState` instances.
- `update_signal(signal: dict | SignalState)` — replace the current signal snapshot. Accepts a raw dict or `SignalState`.
- `tick(dt_seconds=1.0)` — advance internal bookkeeping (wait-time accumulation used for `average_wait`). This is the "simulation loop hook": call it once per frame/step from whatever is driving the blueprint.
- `get_traffic_state() -> TrafficState` — compute and return the current `TrafficState` from the latest vehicle snapshot.
- `render(surface: pygame.Surface)` — draw the current frame (roads, lanes, signal lights, vehicles, and an HUD metrics panel) onto the given surface.

The blueprint never reaches out to find its own data — everything comes
in through `update_vehicles` / `update_signal`, which is what keeps it
decoupled from the Scenario Engine, Model, and Signal Controller.

## Proof of independence (`demo.py`)

`demo.py` contains two intentionally simple mocks:

- `MockVehicleFeed` — stands in for the future Scenario Engine. Spawns/moves vehicles and marks them `waiting` near a stop line if their direction isn't currently open.
- `MockSignalFeed` — stands in for the future Signal Controller/Model. Runs a plain fixed-time NS/EW cycle.

The demo loop only ever calls the blueprint's public methods
(`update_vehicles`, `update_signal`, `tick`, `render`,
`get_traffic_state`) with plain dicts matching the contracts — exactly
how the real Scenario Engine and Signal Controller would call it once
they exist. Every ~2 seconds it also prints the derived `TrafficState`
to the console so you can see the output contract being produced
correctly in real time, e.g.:

```
TrafficState: {'N': {'vehicle_count': 5, 'queue_length': 1, 'average_wait': 0.03}, ...}
```

## Notes on design choices (kept intentionally simple)

- Vehicles are colored rectangles (blue=car, yellow=bus, orange=truck, white with a red cross=ambulance); a red outline marks `waiting == True`.
- Each direction has one signal head pair; the "off" phase is always shown RED, since the contract only carries state for the currently active phase.
- `average_wait` is computed by accumulating seconds-waited per vehicle `id` across `tick()` calls while `waiting` is `True`, then averaging over all vehicles currently assigned to that approach direction. This is metrics bookkeeping required to satisfy the `TrafficState` contract, not traffic/scenario generation.
- No networking, threading, or persistence — a plain Pygame loop is enough for this module's scope.
