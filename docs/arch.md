# JCTRL — Architecture

## 1. Architecture Overview
```
┌───────────────────────────────┐
│ JCTRL Incident Response Client│
└───────────────┬───────────────┘
                │
      Emergency information
                ▼
┌───────────────────────────────┐
│         JCTRL Server          │
│                               │
│ • Emergency coordination      │
│ • Junction registry           │
│ • Route determination         │
└───────────────┬───────────────┘
                │
        Emergency priority
                ▼
┌───────────────────────────────┐
│         JCTRL System          │
│                               │
│ • Traffic monitoring          │
│ • Simulation / physical ctrl  │
│ • State estimation            │
│ • Decision making             │
│ • Signal control              │
└───────────────────────────────┘
```

The JCTRL System must not depend on the internal implementation of the JCTRL Server, only on the 
information/interface it provides. Likewise, the JCTRL Server must not depend on the internal 
implementation of the Incident Response Client.

## 2. System-Level Components

### JCTRL Incident Response Client
The Incident Response Client is the interface used by emergency responders. It provides 
emergency-related information to the JCTRL Server.

Responsibilities
- Provide current emergency vehicle location.
- Provide incident location.
- Provide destination where applicable.
- Provide status updates where required.

For an ambulance:
```math
Current Location
      +
Incident Location
      +
Destination Hospital
```

For fire trucks/police:
```math
Current Location
      +
Incident Location
```

Output
```
Emergency information sent to the JCTRL Server.
```

Must NOT
- Determine the route.
- Decide signal phases.
- Directly communicate with individual JCTRL Systems.
- Control traffic signals.

### JCTRL Server
The JCTRL Server acts as the central coordinator for emergency traffic management.

Input
```
Emergency information from the Incident Response Client and ERC.
```

Responsibilities
- Maintain information about JCTRL junctions.
- Maintain junction locations.
- Receive emergency-vehicle information.
- Determine the route between source and destination.
- Identify JCTRL systems along the route.
- Send emergency-priority information to relevant JCTRL systems.

Output
```
Emergency-priority information for affected JCTRL Systems.
```

```
Incident Response Client
          ↓
     Emergency Data
          ↓
     JCTRL Server
          ↓
       Routing
          ↓
 ┌────────┼────────┐
 ▼        ▼        ▼
JCTRL A  JCTRL B  JCTRL C
```

Must NOT
- Simulate individual vehicles.
- Control a junction directly.
- Perform local traffic-state estimation.
- Decide local signal timing.

The server tells a junction that emergency priority is required and for whom/where. The JCTRL 
System decides how that priority is safely applied locally.

### JCTRL System
The JCTRL System is the local junction-level controller. It receives traffic information locally 
and emergency-priority information from the JCTRL Server.

Internally:
```
                  JCTRL SYSTEM
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
   Dashboard      Traffic Control   Presentation
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
 Scenario Engine   State Estimation   ...
       │               │
       ▼               ▼
 Intersection      Decision Engine
 Simulator              │
       ▲                ▼
       └──── Signal Controller
```

## 3. JCTRL System Components

#### Dashboard
Commands and system information.

#### Scenario Engine
Generates simulated traffic input.

#### Intersection Simulator
Maintains the simulated junction and vehicle movement.

#### State Estimation
Converts observations into decision-ready traffic state.

#### Decision Engine
Produces signal recommendations.

#### Signal Controller
Safely applies signal decisions.

#### Renderer
Visualizes the simulated junction.

## 4. Data Flow

### Emergency Response Flow
```
Incident Response Client
          │
          │ Emergency information
          ▼
     JCTRL Server
          │
          │ Route + emergency priority
          ▼
     JCTRL System
          │
          ▼
   Signal Controller
```

### Normal Traffic Control Flow
```
Traffic Source
      ↓
Intersection Simulator
      ↓
Observation
      ↓
State Estimation
      ↓
TrafficState
      ↓
Decision Engine
      ↓
SignalDecision
      ↓
Signal Controller
      ↓
SignalState
      ↓
Intersection Simulator
```

### Simulation Control Flow
```
Dashboard
   ↓
Scenario Engine
   ↓
Traffic Events
   ↓
Intersection Simulator
```

And presentation:
```
Intersection Simulator
        │
        ├────────→ Renderer
        │
        └────────→ Dashboard
```

## 5. Data Contracts
```
Scenario Engine
      │
 TrafficEvent
      ▼
Intersection Simulator
      │
 Observation
      ▼
State Estimation
      │
 TrafficState
      ▼
Decision Engine
      │
 SignalDecision
      ▼
Signal Controller
      │
 SignalState
      ▼
Intersection Simulator
```

And separately:
```
JCTRL Server
     │
EmergencyEvent / EmergencyPriority
     ▼
JCTRL System
```

## 6. Dependency Rules

### System-level
```
Incident Response Client
          ↓
     JCTRL Server
          ↓
     JCTRL System
```

No reverse dependencies.

### Inside JCTRL System
```
Scenario Engine
      ↓
Intersection Simulator
      ↓
State Estimation
      ↓
Decision Engine
      ↓
Signal Controller
      ↓
Intersection Simulator
```

Presentation components consume state but don't own/control it.

Specifically:
```
Dashboard ──X──→ Signal Controller internals
Renderer  ──X──→ Simulator internals
Decision Engine ──X──→ SignalState
State Estimation ──X──→ SignalDecision
Scenario Engine ──X──→ SignalState
```

That is the architectural "fence."

## 7. Prototype &rarr; Deployment Mapping
| Prototype                | Deployment                     |
| ------------------------ | ------------------------------ |
| Scenario Engine          | Camera/sensor processing       |
| Intersection Simulator   | Physical junction              |
| State Estimation         | OpenCV/sensor-based estimation |
| Decision Engine          | Trained/adaptive controller    |
| Signal Controller        | Physical signal interface      |
| Renderer                 | Monitoring interface           |
| JCTRL Server             | JCTRL central server           |
| Incident Response Client | Responder mobile application   |

## 8. Extension Points
This is where we explicitly preserve future flexibility.

### Traffic Source
```
Scenario Engine
      ↓
Camera/Sensor Pipeline
```

### Decision Engine
```
Rule-Based
    ↓
    ML
    ↓
    RL
```

### Intersection Representation
```
Software Simulator
      ↓
Physical Junction
```

### Renderer
```
Pygame
  ↓
Web UI
  ↓
Other visualization system
```

---