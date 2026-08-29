# JCTRL - Junction Control

## 1. Overview
JCTRL (Junction Control) is an adaptive traffic signal control system designed to dynamically 
manage traffic at road junctions based on real-time traffic conditions.

The system monitors traffic volume, queue length, waiting time, vehicle type, and emergency-vehicle 
presence to dynamically determine signal phases and their durations.

The system is designed to reduce unnecessary waiting, improve traffic flow, prioritize congested 
approaches, and provide priority to emergency vehicles.

## 2. Baseline Traffic Signal Model
The baseline system uses a fixed-time traffic signal model.

For example:
```
Green  → 30 sec
Yellow → 5 sec
Red    → 105 sec

Total cycle → 140 sec
```

The exact timing may vary depending on the junction configuration.

### 2.1 Problems with the Baseline Model
The fixed-time model has the following limitations:
- Signal timing does not adapt to changing traffic conditions.
- Heavy congestion during peak periods can result in excessive waiting times.
- The system cannot reliably prioritize approaches with higher traffic volume.
- Emergency vehicles cannot receive dedicated priority.
- Opposing straight-moving traffic is unnecessarily prevented from moving simultaneously when the 
junction configuration allows it.

## 3. How JCTRL Works
JCTRL replaces fixed-time operation with adaptive signal control.

The system continuously receives information about the current traffic conditions and uses it to 
determine how the available green time should be allocated.

The major inputs to the control system are:
- Traffic volume
- Queue length
- Vehicle waiting time
- Vehicle type
- Emergency-vehicle presence
- Current signal phase

These inputs are used by the decision system to determine the appropriate signal phase and timing.

The overall control loop is:
```
Traffic Monitoring
       ↓
Traffic State
       ↓
Decision Engine
       ↓
Signal Decision
       ↓
Signal Controller
       ↓
Updated Traffic Conditions
       ↓
Traffic Monitoring
```

For the prototype, traffic monitoring is simulated. In deployment, the monitoring layer can be 
replaced by cameras and sensors.

## 4. Signal Phase Timing & Control

### 4.1 Signal Phases
For a basic four-way junction, JCTRL operates using two primary movement phases:

Phase NS — North-South
North &rarr; South: GREEN

East &larr; West: RED

> Both opposite directions are allowed to proceed simultaneously.

Phase EW — East-West
North &rarr; South: RED

East &larr; West: GREEN

> Both opposite directions are allowed to proceed simultaneously.

Transitions between phases include a yellow/clearance period.

```
NS GREEN
   ↓
NS YELLOW
   ↓
ALL-RED / CLEARANCE (if required)
   ↓
EW GREEN
   ↓
EW YELLOW
   ↓
...
```

### 4.2 Adaptive Green-Time Allocation
Instead of assigning a fixed green duration to every phase, JCTRL determines the priority of each 
phase using the current traffic state.

A phase with:
- higher traffic volume,
- longer queues,
- greater accumulated waiting time,

should receive greater priority.

Conceptually:
```
             Traffic State
                  │
        ┌─────────┼─────────┐
        ↓         ↓         ↓
     Volume     Queue     Waiting
        │         │         │
        └─────────┼─────────┘
                  ↓
          Phase Priority
                  ↓
           Green Duration
```

A simple conceptual priority score can be:

```math
Priority = w1 × traffic_volume + w2 × queue_length + w3 × waiting_time
```

where w1, w2, and w3 are configurable weights.

Important: this doesn't mean we have committed to this exact mathematical formula for the final 
implementation. It's a clean control model for the prototype.

### 4.3 Timing Constraints
Adaptive control should not mean:

> "AI can randomly change the signal whenever it wants."

The Signal Controller must enforce safety constraints.

For example:
- minimum green time
- maximum green time
- yellow duration
- clearance interval

Therefore:
```
Decision Engine
      ↓
"Give NS green for 45 sec"
      ↓
Signal Controller
      ↓
Check constraints
      ↓
Apply valid transition
```

Decision Engine recommends. Signal Controller enforces.

### 4.4 Emergency Vehicle Priority
Emergency vehicles have higher priority than normal traffic. When an emergency vehicle is 
approaching the junction, JCTRL may override normal adaptive operation to provide a suitable green 
phase.

Conceptually:
```
Normal Traffic
      ↓
Adaptive Control

Emergency Detected
      ↓
Emergency Priority
      ↓
Prepare required approach
      ↓
Green
      ↓
Emergency Vehicle Passes
      ↓
Resume Adaptive Control
```

The controller should avoid abruptly switching signals. A valid transition through yellow/clearance 
should be performed where necessary.

## 5. Emergency Vehicle Handling
JCTRL supports emergency-vehicle prioritization through coordination between the Incident Response 
Client, JCTRL Server, and individual JCTRL systems.

### 5.1 Ambulance
When an emergency service is requested:
```
Emergency Response Center
          ↓
Incident information
          ↓
JCTRL Server
```

For an ambulance, the route consists of:
```
Source
  ↓
Incident Location
  ↓
Hospital
```

The ambulance driver can update the destination hospital through the Incident Response Client. The 
JCTRL Server determines the required route and communicates with the JCTRL systems along that route.
Each affected JCTRL prepares the junction for the approaching emergency vehicle.

### 5.2 Fire Trucks and Police Vehicles
For emergency vehicles such as fire trucks and police vehicles, a hospital destination is not 
required.

The route can be represented as:
```
Current Vehicle Location
          ↓
Incident Location
```

The JCTRL Server communicates the required route to the relevant junctions.

### 5.3 Multiple Emergency Vehicles
When multiple emergency vehicles approach a junction from different directions, JCTRL prioritizes 
them according to:
- Distance from the junction
- Arrival order

The system continues to account for the other emergency vehicles while servicing the 
highest-priority vehicle.

Conceptually:
```
Emergency Vehicle A → 200m
Emergency Vehicle B → 500m
Emergency Vehicle C → 800m
```

Priority: A → B → C

### 5.4 Emergency Vehicles on All Approaches
If emergency vehicles are approaching from all approaches, JCTRL prioritizes the emergency vehicle 
closest to the junction. After that vehicle has passed, the remaining emergency vehicles are 
handled according to their priority/arrival order.

## 6. Implementation Architecture

### 6.1 JCTRL System
Each physical junction contains a JCTRL system consisting of:
- Raspberry Pi or equivalent edge-computing device
- Cameras
- Traffic sensors where required
- Signal-controller interface

Cameras capture traffic at the junction. The captured video is processed using OpenCV to detect 
vehicles and classify relevant vehicle types.

The system derives traffic information such as:
- Vehicle count
- Vehicle type
- Traffic density
- Queue length
- Waiting time

This information is provided to the traffic-control system. The JCTRL system also receives 
emergency-priority information from the JCTRL Server.

### 6.2 JCTRL Server
The JCTRL Server provides coordination between emergency-response information and individual 
junction controllers.

It is responsible for:
- Maintaining information about deployed JCTRL junctions
- Receiving emergency-response information
- Maintaining junction locations
- Determining the emergency-vehicle route
- Identifying JCTRL systems along the route
- Sending emergency-priority information to those junctions

Conceptually:
```
ERC / Incident Client
          ↓
     JCTRL Server
          ↓
   Route determination
          ↓
 ┌────────┼────────┐
 ↓        ↓        ↓
JCTRL-1 JCTRL-2 JCTRL-3
```

### 6.3 Incident Response Client
The Incident Response Client is a mobile application intended for emergency responders such as:
- Ambulance operators
- Fire-truck operators
- Police officers

The client communicates emergency-vehicle information to the JCTRL Server. For an ambulance, this 
may include:
- Current location
- Incident location
- Destination hospital

For other emergency vehicles:
- Current location
- Incident location

The JCTRL Server uses this information to coordinate signal priority along the required route.

## 7. Prototype vs Deployment
| Component         | Prototype                  | Deployment                  |
| ----------------- | -------------------------- | --------------------------- |
| Traffic input     | Scenario Engine            | Cameras + sensors           |
| Vehicle detection | Simulated                  | OpenCV / vision pipeline    |
| Intersection      | Software simulator         | Physical junction           |
| State estimation  | Simulation observations    | Sensor/camera observations  |
| Decision Engine   | Prototype controller/model | Trained/validated model     |
| Signal Controller | Simulated                  | Physical signal interface   |
| Emergency input   | Simulated events           | ERC / Incident Client       |
| JCTRL Server      | Prototype/future           | Central coordination server |

---