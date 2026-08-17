# BatteryIQ: Intelligent Battery Management System for Software-Defined Electric Vehicles

## Team Members

| S. No. | University ID | Name |
|---|---|---|
| 1 | 2420030099 | BANDI SRIHITHA |
| 2 | 2420030171 | R.L.S. GIRIDHAR |
| 3 | 2420030172 | P. SATWIKA REDDY |

**Supervisor/Guide:** Dr. Srikanth Cherukuvada

---

## Project Abstract

Electric Vehicles (EVs) are increasingly being adopted as a sustainable alternative to conventional vehicles, with rechargeable battery packs serving as the primary source of energy. The safety, performance, reliability, and lifetime of an EV largely depend on effective battery management. A Battery Management System (BMS) continuously monitors important battery parameters such as voltage, current, temperature, State of Charge (SOC), and State of Health (SOH) to identify abnormal conditions and maintain safe operation.

Conventional BMS mechanisms mainly depend on predefined thresholds and fixed decision strategies. These approaches may have limitations in detecting early battery abnormalities and adapting to changing operating conditions. The emergence of Software-Defined Vehicles also requires flexible and intelligent BMS architectures in which battery-management decisions can be controlled through software.

The proposed project, **BatteryIQ**, introduces an Intelligent Battery Management System for Software-Defined Electric Vehicles. The system uses Embedded C, FreeRTOS, CAN Bus, TensorFlow Lite, Python, IoT, and Docker.

The proposed system introduces three key mechanisms: **Event-Triggered AI Inference**, where AI is activated only when suspicious battery behaviour is detected; a **Two-Level Battery Decision System**, which combines fast screening with AI verification; and a **Software-Defined Risk Policy**, which converts the detected battery risk into configurable actions such as normal operation, warning, charging restriction, or protection.

The proposed system aims to improve battery anomaly detection, reduce unnecessary computational workload, and provide flexible and intelligent battery-management decisions for Software-Defined Electric Vehicles.

---

## Setup Instructions

### Requirements

- Python 3.x
- TensorFlow / TensorFlow Lite
- Embedded C development environment
- FreeRTOS
- CAN Bus communication tools
- Docker
- IoT monitoring tools

### Setup

1. Clone the repository.
2. Install the required Python dependencies.
3. Set up the AI model development environment.
4. Prepare the battery data/dataset.
5. Configure the preprocessing and feature-processing modules.
6. Configure the TensorFlow Lite model.
7. Configure the FreeRTOS tasks.
8. Configure the CAN Bus communication environment.
9. Configure IoT monitoring if required.

---

## Execution Instructions

1. Provide battery parameters such as:
   - Voltage
   - Current
   - Temperature
   - SOC
   - SOH

2. Perform data preprocessing and normalization.

3. Start the FreeRTOS-based monitoring tasks.

4. The **Level-1 Fast Screening** continuously monitors battery behaviour.

5. If the battery condition is normal, the system continues monitoring.

6. If suspicious behaviour is detected, the **Event-Triggered AI** activates the TensorFlow Lite model.

7. The AI model verifies the detected abnormal condition.

8. The screening and AI results are combined to determine the battery risk level.

9. The **Software-Defined Risk Policy** selects the appropriate action.

10. Battery status, risk information, alerts, and control decisions can be communicated through **CAN Bus**.

---

## Current Project Status

- Project problem definition completed.
- Research gap identified.
- Related research papers reviewed.
- Project objectives finalized.
- Three key project novelties finalized:
  - Event-Triggered AI Inference
  - Two-Level Battery Decision System
  - Software-Defined Risk Policy
- System architecture designed.
- Technology stack identified.
- AI integration approach planned.
- FreeRTOS task structure planned.
- CAN Bus communication approach planned.
- Performance and validation parameters identified.
- Implementation and experimental validation are in progress.
