# JCTRL — Development Design Specification

## 1. Document Overview & Purpose
This document defines the technical implementation plan, architectural boundaries, module interfaces, parallel development strategies, team allocations, and integration workflows for the **JCTRL (Junction Control & Real-time Logistics)** prototype system.

While high-level system responsibilities are outlined in `arch.md`, this specification establishes the operational development framework required to deliver a fully functional, testable, and demonstrable prototype.

### Core Prototype Capabilities
The delivered prototype must successfully demonstrate five fundamental capabilities:
1. **Normal Traffic Simulation:** Realistic multi-directional vehicle flow, queue formation, and signal-state interaction.
2. **Adaptive Traffic Signal Control:** Dynamic adjustment of green-light durations based on real-time traffic density, queue lengths, and waiting times.
3. **Emergency-Vehicle Priority (EVP):** Real-time preemptive signal overrides triggered by incident dispatch requests to ensure zero-delay passage for emergency responders.
4. **Baseline Performance Benchmarking:** Quantitative side-by-side comparison between fixed-time signal control and JCTRL adaptive control.
5. **Interactive Visual Demonstration:** Real-time visual rendering of the intersection, signal phases, vehicle dynamics, state metrics, and system controls.

---

## 2. System Architecture & Module Boundaries

The JCTRL platform is structured into three primary top-level modules. Each module maintains strict encapsulation, defined contract boundaries, and independent testability.

```
┌─────────────────────────────────────────────────────────┐
│              Incident Response Client                   │
│  (Emergency Dispatcher UI / Signal Preemption Trigger)  │
└───────────────────────────┬─────────────────────────────┘
                            │
                            │ EmergencyRequest
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    JCTRL Server                         │
│   (Centralized Route Engine & Junction Coordinator)     │
└───────────────────────────┬─────────────────────────────┘
                            │
                            │ EmergencyPriority
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    JCTRL System                         │
│                                                         │
│  ┌──────────────────┐          ┌─────────────────────┐  │
│  │ Scenario Engine  │ ────────►│ Intersection Sim.   │  │
│  └──────────────────┘          └──────────┬──────────┘  │
│                                           │ Observation │
│                                           ▼             │
│  ┌──────────────────┐          ┌─────────────────────┐  │
│  │ Signal Controller│ ◄─────── │ State Estimation    │  │
│  └────────┬─────────┘          └──────────┬──────────┘  │
│           │                               │ TrafficState│
│           │ SignalState                   ▼             │
│           │                    ┌─────────────────────┐  │
│           └──────────────────► │ Decision Engine     │  │
│                                └─────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │             Dashboard & UI Renderer               │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Modular Design Principles
* **Single Responsibility:** Each module fulfills a distinct operational role within the control loop.
* **Interface-Driven Interaction:** Components communicate exclusively through standardized, strongly typed data structures.
* **Zero Leaky Abstractions:** Implementation specifics (e.g., simulation geometry or specific routing algorithms) are hidden behind module interfaces.
* **Decoupled Execution:** Modules are designed to be run and validated via mock data inputs before system-level integration.

---

## 3. Module 1 — Incident Response Client

### 3.1 Overview & Responsibility
The **Incident Response Client** simulates the portal used by first responders (police, fire, ambulance) to report active emergencies and broadcast location data to the municipal traffic network.

### 3.2 Prototype Scope
The prototype client provides an intuitive interface for dispatchers to specify critical routing metadata required by the central server:
* **Vehicle Identifier & Type:** (e.g., `AMBULANCE_01`, `FIRE_TRUCK_02`, `POLICE_04`)
* **Origin / Current Junction:** Node entry point in the network.
* **Incident / Target Junction:** Destination node requiring emergency access.
* **Priority Level:** Severity rank (e.g., Level 1 Critical vs. Level 2 Standard Response).

#### Sample Incident Input
```yaml
VehicleID: "AMBULANCE_ALPHA"
VehicleType: "AMBULANCE"
Priority: 1
SourceJunction: "Junction_A"
IncidentJunction: "Junction_D"
DestinationFacility: "Central_Hospital"
Timestamp: 1772274694
```

### 3.3 System Output
The client generates an `EmergencyRequest` JSON/protobuf payload transmitted over HTTP REST or WebSocket to the JCTRL Server.

### 3.4 Development Boundaries
To maintain decoupling, the Incident Response Client **must not**:
* Calculate vehicle routes or navigation paths.
* Issue direct phase change commands to traffic lights.
* Interact directly with edge JCTRL Systems.
* Execute internal traffic simulation logic.

---

## 4. Module 2 — JCTRL Server

### 4.1 Overview & Responsibility
The **JCTRL Server** acts as the central orchestration node. It processes incoming emergency requests, computes network routes across the city grid, identifies affected intersections, and dispatches localized preemptive control commands.

### 4.2 Functional Scope
1. **Ingestion:** Consumes `EmergencyRequest` payloads from dispatch clients.
2. **Network Topology Management:** Maintains a graph representation of intersections and connecting roadways.
3. **Route Optimization:** Runs pathfinding algorithms (e.g., Dijkstra / A*) to determine the fastest emergency route.
4. **Target Identification:** Identifies specific JCTRL edge systems along the path and estimates arrival time windows.
5. **Priority Broadcast:** Emits `EmergencyPriority` notifications to relevant JCTRL Systems ahead of the vehicle's arrival.

### 4.3 Input & Output Contracts
* **Input:** `EmergencyRequest`
* **Output:** `EmergencyPriority`

### 4.4 Graph Model Simplification
For the prototype scope, the server operates on a discrete topological graph rather than a full GIS shapefile map:

```text
       [Junction A] ─────── [Junction B] ─────── [Junction C]
                                │
                                │
                          [Junction D] (Hospital Zone)
```

### 4.5 Development Boundaries
The JCTRL Server **must not**:
* Run localized micro-simulations of vehicle physics.
* Compute local vehicle densities or queue lengths.
* Directly modify low-level signal timers without sending formal priority commands.
* Render junction visualizers.

---

## 5. Module 3 — JCTRL System (Local Intersection Unit)

The **JCTRL System** is deployed per intersection (or manages a local cluster). It contains the core simulation, state calculation, adaptive decision, and rendering components.

```text
JCTRL System Architecture
├── 5.1 Scenario Engine        (Traffic demand & event generation)
├── 5.2 Intersection Simulator (Micro-simulation engine & vehicle physics)
├── 5.3 State Estimation       (Raw data extraction & metric aggregation)
├── 5.4 Decision Engine        (Adaptive timing & emergency preemption logic)
├── 5.5 Signal Controller      (State machine & safety constraint enforcer)
└── 5.6 Dashboard & Renderer   (Real-time visualization & telemetry presentation)
```

---

## 6. Internal Component Specifications

### 6.1 Scenario Engine
* **Responsibility:** Generates configurable traffic patterns, spawn rates, turn ratios, and emergency injection events.
* **Inputs:** Scenario configuration parameters, seed parameters, step commands.
* **Outputs:** `TrafficEvent` stream.
* **Deterministic Execution:** Supports fixed random seeds to enable identical replay conditions across baseline and adaptive test runs.
* **Supported Scenarios:**
  1. *Balanced Flow:* Uniform distribution across all approaches (N, S, E, W).
  2. *Asymmetric Flow:* Heavy North/South corridor demand vs. light East/West cross-street demand.
  3. *Rush-Hour Surge:* Dynamic ramp-up of traffic density to simulate peak congestion.
  4. *Emergency Infiltration:* Insertion of an emergency vehicle into heavy background traffic.

### 6.2 Intersection Simulator
* **Responsibility:** Executes micro-level vehicle movement, queueing behavior, signal adherence, and step-wise state updates.
* **Inputs:** `TrafficEvent`, `SignalState`.
* **Outputs:** `Observation` (raw vehicle positions, velocities, headways, and signal state).
* **Key Tasks:** Vehicle physics update, collision avoidance, stop-bar queue detection, waiting time accumulation, signal state compliance.

### 6.3 State Estimation
* **Responsibility:** Filters raw `Observation` telemetry into structured, high-level features for the control pipeline.
* **Inputs:** `Observation`.
* **Outputs:** `TrafficState`.
* **Calculated Feature Vector:**
  * Vehicle count per lane / approach.
  * Max & average queue length (in meters / vehicle units).
  * Aggregate accumulated delay & max waiting time.
  * Spatial occupancy / density percentages.
  * Emergency vehicle detection flag, distance to stop bar, and current approach lane.

### 6.4 Decision Engine
* **Responsibility:** Computes optimal signal phase durations based on estimated traffic state and incoming emergency priority directives.
* **Inputs:** `TrafficState`, `EmergencyPriority` (optional).
* **Outputs:** `SignalDecision`.
* **Logic Framework:**
  ```text
  IF EmergencyPriority IS ACTIVE:
      Override normal cycle -> Request IMMEDIATE GREEN for Emergency Approach
  ELSE:
      Compute Phase Weight = f(Volume, Queue Length, Max Wait Time)
      Determine Optimal Green Split Duration
      Output SignalDecision (Target Phase, Recommended Duration)
  ```
* **Design Requirement:** Algorithm must be modular and hot-swappable (e.g., swapping a rule-based algorithm for a reinforcement learning model without altering surrounding components).

### 6.5 Signal Controller
* **Responsibility:** Implements a strict, deterministic state machine enforcing signal transition sequences and safety bounds.
* **Inputs:** `SignalDecision`, current `SignalState`.
* **Outputs:** Updated `SignalState`.
* **State Machine Cycle:**
  $$	ext{GREEN} \longrightarrow 	ext{YELLOW} \longrightarrow 	ext{ALL-RED CLEARANCE} \longrightarrow 	ext{NEXT GREEN}$$
* **Safety Rules Enforced:**
  * Minimum Green Time ($T_{	ext{min\_green}}$ e.g., 7s).
  * Maximum Green Time ($T_{	ext{max\_green}}$ e.g., 60s).
  * Fixed Yellow Interval ($T_{	ext{yellow}}$ e.g., 3s-5s).
  * All-Red Clearance Interval ($T_{	ext{clearance}}$ e.g., 2s).
* **Isolation Constraint:** The Decision Engine cannot directly write signal light states; it must issue requests to the Signal Controller, which validates them against safety rules.

### 6.6 Dashboard & Renderer
* **Responsibility:** Visual presentation layer and interactive user control panel.
* **Inputs:** Complete system state (`SignalState`, `TrafficState`, `Observation`, `EmergencyPriority`, comparative metrics).
* **Outputs:** Visual display & user commands (Play, Pause, Step, Reset, Scenario Select).
* **Components:**
  * **2D Canvas Renderer:** Visual representation of intersection geometry, lane markings, signal light status, and animated vehicle entities.
  * **Telemetry Panel:** Real-time graphs showing average queue length, vehicle delay, phase timers, and control mode status.

---

## 7. Shared Data Contracts & Schemas

To facilitate seamless parallel development, all teams must adhere to the following strict data contracts.

### Contract Definitions

#### 1. EmergencyRequest
* **Producer:** Incident Response Client
* **Consumer:** JCTRL Server
```json
{
  "request_id": "REQ-20260829-001",
  "vehicle_id": "AMBULANCE_01",
  "vehicle_type": "AMBULANCE",
  "priority_level": 1,
  "source_junction": "J1",
  "destination_junction": "J4",
  "timestamp": 1772274694.0
}
```

#### 2. EmergencyPriority
* **Producer:** JCTRL Server
* **Consumer:** JCTRL System (Decision Engine / Signal Controller)
```json
{
  "priority_id": "PRI-9902",
  "target_junction": "J2",
  "approaching_lane": "NORTH_BOUND",
  "estimated_arrival_time": 1772274745.0,
  "preemption_required": true,
  "active": true
}
```

#### 3. TrafficEvent
* **Producer:** Scenario Engine
* **Consumer:** Intersection Simulator
```json
{
  "event_id": "EVT-10042",
  "timestamp": 104.5,
  "action": "SPAWN_VEHICLE",
  "vehicle_data": {
    "id": "V_892",
    "type": "PASSENGER_CAR",
    "origin_approach": "NORTH",
    "destination_approach": "SOUTH",
    "speed": 13.4
  }
}
```

#### 4. Observation
* **Producer:** Intersection Simulator
* **Consumer:** State Estimation, Dashboard/Renderer
```json
{
  "simulation_time": 105.0,
  "vehicles": [
    {
      "id": "V_892",
      "position_x": 12.4,
      "position_y": 85.1,
      "speed": 8.2,
      "lane_id": "NORTH_INBOUND",
      "waiting_time": 0.0
    }
  ],
  "current_signal_phase": "PHASE_NORTH_SOUTH_GREEN"
}
```

#### 5. TrafficState
* **Producer:** State Estimation
* **Consumer:** Decision Engine, Dashboard
```json
{
  "timestamp": 105.0,
  "approaches": {
    "NORTH": { "count": 14, "queue_length_m": 42.0, "max_wait_sec": 38.5, "has_emergency": false },
    "SOUTH": { "count": 12, "queue_length_m": 35.5, "max_wait_sec": 32.0, "has_emergency": false },
    "EAST":  { "count": 3,  "queue_length_m": 5.0,  "max_wait_sec": 8.1,  "has_emergency": false },
    "WEST":  { "count": 4,  "queue_length_m": 8.0,  "max_wait_sec": 10.2, "has_emergency": false }
  },
  "emergency_vehicle_detected": false
}
```

#### 6. SignalDecision
* **Producer:** Decision Engine
* **Consumer:** Signal Controller
```json
{
  "decision_id": "DEC-883",
  "target_phase": "PHASE_NORTH_SOUTH_GREEN",
  "recommended_duration_sec": 35.0,
  "reason": "HIGH_NORTH_SOUTH_DENSITY",
  "emergency_override": false
}
```

#### 7. SignalState
* **Producer:** Signal Controller
* **Consumer:** Intersection Simulator, Renderer/Dashboard
```json
{
  "active_phase": "PHASE_NORTH_SOUTH_GREEN",
  "phase_color": "GREEN",
  "elapsed_in_phase_sec": 12.0,
  "remaining_in_phase_sec": 23.0,
  "min_green_enforced": true
}
```

---

## 8. Team Structure & Responsibilities

The development team consists of **6 members**. Tasks are split across core development, routing logic, simulation engine, state machine control, and integrated evaluation.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          TEAM ALLOCATION ROUTE                          │
├──────────────────────┬──────────────────────────────────────────────────┤
│ Developer 1          │ System Integration & Core Contracts              │
│ Developer 2          │ Scenario Engine & Traffic Generation             │
│ Developer 3          │ Intersection Simulator                           │
│ Developer 4          │ State Estimation, Decision Engine & Controller   │
│ Developer 5          │ JCTRL Server & Incident Response Client          │
│ Technical Lead (Dev6)│ Evaluation, Benchmarking & Demo Integration      │
└──────────────────────┴──────────────────────────────────────────────────┘
```

### 8.1 Detailed Member Breakdown

#### Developer 1 — System Integration & Core Contracts
* **Primary Scope:** Architecture skeleton, repository structure, shared contract definitions, event pipeline integration, system-wide error handling.
* **Deliverables:** `contracts/` package, main application integration loop, system configuration loader.

#### Developer 2 — Scenario & Traffic Generation
* **Primary Scope:** `Scenario Engine`, traffic probability models, deterministic scenario seeding, vehicle generation routines.
* **Deliverables:** `ScenarioEngine` class, pre-configured JSON scenario files (Balanced, Peak, Emergency).

#### Developer 3 — Intersection Simulation
* **Primary Scope:** `Intersection Simulator`, vehicle movement physics, lane geometry handling, queue detection logic, collision avoidance rules.
* **Deliverables:** Micro-simulation module capable of processing `TrafficEvent` inputs and outputting step `Observation` frames.

#### Developer 4 — State, Decision & Signal Control
* **Primary Scope:** `State Estimation`, `Decision Engine`, `Signal Controller` state machine, phase interval enforcement.
* **Deliverables:** Complete control pipeline converting raw `Observation` into adaptive `SignalState` transitions.

#### Developer 5 — JCTRL Server & Incident Response
* **Primary Scope:** `Incident Response Client`, `JCTRL Server`, network topological graph, pathfinding module, emergency preemption message broker.
* **Deliverables:** Server application, dispatcher CLI/GUI tool, pathfinding module emitting `EmergencyPriority`.

#### Developer 6 — Evaluation, Benchmarking & Demo Integration (Refactored Role)
* **Technical Scope:** Quantitative benchmark suite, fixed-time baseline implementation, automated performance metric aggregation, interactive dashboard visualizer, demonstration suite.
* **Deliverables:**
  1. *Fixed-Time Baseline Module:* Static round-robin controller used for direct comparative experiments.
  2. *Evaluation Harness:* Data collection scripts recording delay, throughput, queue lengths, and preemption performance.
  3. *Demonstration GUI:* Operational dashboard rendering simulation state and benchmark charts side by side.
  4. *Presentation Deliverables:* Visual assets, performance charts, and live demo script.

---

## 9. Parallel Development Strategy & Isolation Stubs

To avoid development blockages, team members build against interface contracts using mock data stubs.

```text
Parallel Execution Architecture:

[ Dev 2: Scenario Engine ] ────> (Emits Mock TrafficEvent)
                                         │
[ Dev 3: Simulator ] <───────────────────┘ ────> (Emits Mock Observation)
                                                         │
[ Dev 4: Control Pipeline ] <────────────────────────────┘ ────> (Emits Mock SignalState)
                                                                         │
[ Dev 6: Dashboard & Benchmarks ] <──────────────────────────────────────┘
```

### Isolation Workflow
1. **Day 1 Contract Freeze:** All schema definitions (Section 7) are finalized and frozen.
2. **Mock Creation:** Each developer writes a dummy mock generator for their input dependency:
   * *Dev 4* creates a static `Observation` mock to build the `Decision Engine` without waiting for Dev 3's simulator.
   * *Dev 3* creates a mock `TrafficEvent` generator to build the simulator without waiting for Dev 2.
   * *Dev 5* uses a mock endpoint to emit `EmergencyPriority` events into a stubbed system.
3. **Stub Replacement:** Mock generators are systematically swapped for actual module implementations during integration phases.

---

## 10. Integration Sequence & Milestones

System integration follows a structured, step-by-step pipeline:

```text
Phase 1: Contract Validation (Data Schemas Verified)
   │
   ▼
Phase 2: Scenario Engine + Intersection Simulator (Vehicle Flow Working)
   │
   ▼
Phase 3: Simulator + State Estimation + Decision Engine (Closed-Loop Adaptive Control)
   │
   ▼
Phase 4: Signal Controller Integration (Safety & Transition Constraints Enforced)
   │
   ▼
Phase 5: Baseline Controller Integration (Comparative Execution Pipeline Ready)
   │
   ▼
Phase 6: Incident Server + Priority Override (Emergency Preemption Flow Integrated)
   │
   ▼
Phase 7: Dashboard Renderer & Metric Visualizer (End-to-End Visual Demo)
```

---

## 11. Baseline Evaluation & Comparative Methodology

To validate the adaptive system's effectiveness, the prototype must run comparative benchmarking experiments between the JCTRL Adaptive Engine and a standard Fixed-Time Baseline.

```text
                       ┌──────────────────────────────┐
                       │     Scenario Engine Input    │
                       │ (Identical Traffic Seed & Rate)│
                       └──────────────┬───────────────┘
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
┌──────────────────────────────┐              ┌──────────────────────────────┐
│  Fixed-Time Baseline Controller│             │   JCTRL Adaptive Controller  │
│  (Static Phase Intervals)    │              │  (Dynamic Priority Splitting)│
└──────────────┬───────────────┘              └──────────────┬───────────────┘
               │                                             │
               ▼                                             ▼
┌──────────────────────────────┐              ┌──────────────────────────────┐
│  Baseline Metric Metrics     │              │   Adaptive Metric Metrics    │
└──────────────┬───────────────┘              └──────────────┬───────────────┘
               │                                             │
               └──────────────────────┬──────────────────────┘
                                      ▼
                       ┌──────────────────────────────┐
                       │ Quantitative Comparison UI   │
                       └──────────────────────────────┘
```

### 11.1 Benchmark Metrics
The system measures and logs the following KPIs during evaluation runs:
* **Average Vehicle Delay ($D_{	ext{avg}}$):** Mean time spent by vehicles traveling below free-flow speed ($s$).
* **Average Queue Length ($Q_{	ext{avg}}$):** Mean number of stopped vehicles across all approaches per time step.
* **System Throughput ($TP$):** Total count of completed vehicle passages through the junction per unit time ($Vehicles/Hour$).
* **Emergency Response Latency ($T_{	ext{emergency\_clear}}$):** Total seconds required for an emergency vehicle to traverse the managed zone from entry point to exit bar.

---

## 12. Minimum Viable Prototype (MVP) Contingency Plan

If time constraints emerge, the development schedule drops features according to the following priority matrix, safeguarding core execution logic:

```text
Priority Level 1 (CRITICAL — Core Pipeline):
├── Basic Scenario Engine -> Micro-Simulator loop
├── State Estimation -> Decision Engine -> Signal Controller loop
└── Working single-intersection adaptive green timing

Priority Level 2 (HIGH — Comparative Proof):
├── Fixed-time baseline implementation
└── Core metric collection (Queue length, Average delay)

Priority Level 3 (MEDIUM — Emergency Demonstration):
├── Emergency vehicle injection into simulator
└── Signal preemption override logic (Direct priority signal change)

Priority Level 4 (ENHANCEMENT — Visualization & Network):
├── Interactive Dashboard & Visual Renderer
└── Multi-junction JCTRL Server route management

Priority Level 5 (OPTIONAL — Advanced Features):
└── Multi-vehicle priority conflict resolution & advanced analytics export
```

---

## 13. End-to-End Data & Control Flow

### 13.1 Normal Adaptive Control Cycle
```text
[ Scenario Engine ]
       │ TrafficEvent
       ▼
[ Intersection Simulator ] ◄── SignalState ──┐
       │                                     │
       │ Observation                         │
       ▼                                     │
[ State Estimation ]                         │
       │ TrafficState                        │
       ▼                                     │
[ Decision Engine ]                          │
       │ SignalDecision                      │
       ▼                                     │
[ Signal Controller ] ───────────────────────┘
       │
       ▼
[ Dashboard & Renderer ]
```

### 13.2 Preemptive Emergency Priority Cycle
```text
[ Incident Response Client ]
       │ EmergencyRequest
       ▼
[ JCTRL Server ] (Computes graph route J1->J2->J4)
       │ EmergencyPriority
       ▼
[ Decision Engine ] (Sets emergency_override = true)
       │ SignalDecision (Immediate Target Phase Request)
       ▼
[ Signal Controller ] (Executes safe yellow transition -> Forces Target Green)
       │ SignalState (Green locked for Emergency Corridor)
       ▼
[ Intersection Simulator ] (Emergency vehicle passes with 0 stop delay)
```
