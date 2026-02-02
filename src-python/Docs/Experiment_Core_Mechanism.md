# eVTOL Core Experiment Mechanism & Data Flow

## 1. Overview
This document outlines the core data processing mechanism for the "Data-Driven MBSE Architecture Optimization" experiment.
It connects the HIL (Hardware-in-the-Loop) data collection with the MOE-MOP-TPM evaluation framework.

---

## 2. Data Flow Architecture

### Stage 1: Feature Extraction (Measurement)
*   **Input**: Raw HIL Logs (CSV)
    *   `fcs_telemetry.csv` (Control loop state, position, actuator outputs)
    *   `bus_traffic.csv` (Network packet logs)
    *   `load_trace.csv` (Simulated or Real CPU load logs)
*   **Engine**: `dsm_generator.py`
    *   **Logic**:
        1.  **Map**: Associate raw data streams to Logical Functions via `MappingConfig`.
        2.  **Stats**: key metrics:
            *   **Load**: Mean & P95 CPU Load.
            *   **Timing**: Mean Jitter & P95 Jitter.
            *   **Power**: Estimate power from Actuator PWM/Voltage.
            *   **Performance**: Calculate Baseline RMSE (Cmd vs Act).
    *   **Output**: `dsm_report.json`
        *   Contains the "Profile" (fingerprint) of each function:
            *   `{ "LF_Function": { "cpu_load_p95": 0.15, "nav_rmse": 0.5, "bandwidth": 1024 } }`

### Stage 2: Architecture Evaluation (Prediction)
*   **Input**: 
    1.  `dsm_report.json` (Baseline Profiles)
    2.  `Allocation Scheme` (Candidate Architecture: "Function A -> SoC")
    3.  `HardwareSpecs` (Constraints: Capacity, Bandwidth, Safety Level)
*   **Engine**: `evaluation_model.py`
    *   **Layer 1: TPM (Technical Performance)**
        *   **Compute Equivalence**: Convert Load to Target HW Load (`Load * C_Ratio`).
        *   **Comm Overhead**: Calculate Serialization & Latency penalties for cross-node edges.
        *   *Result*: CPU Margins, Bus Latency.
    *   **Layer 2: MOP (Operational Performance)**
        *   **Non-linear Degradation**: Predict new RMSE based on Bus Latency.
        *   Formula: `RMSE_pred = RMSE_base * (1 + exp(k * (Latency - Threshold)))`.
        *   *Result*: Predicted Navigation Accuracy Score.
    *   **Layer 3: MOE (Effectiveness)**
        *   **Safety Check**: Verify Hard Constraints (DAL A on Safety Node).
        *   *Result*: Safety Score, Mission Reliability.
*   **Output**: Composite Fitness Score (0.0 - 1.0)

### Stage 3: Optimization (Search)
*   **Input**: Evaluation Model + Capella Logic Graph
*   **Engine**: Genetic Algorithm (Future Work / In-Progress)
    *   **Chromosome**: Integer array representing allocation mapping.
    *   **Fitness Function**: Calls `evaluation_model.evaluate_architecture()`.
    *   **Logic**: Mutate/Crossover allocation maps to maximize Composite Score.

---

## 3. Key Algorithmic Models

### 3.1 Heterogeneous Compute Model
*   **Problem**: SoC is faster than MCU.
*   **Solution**: `C_RATIO` constant (e.g., 2.5).
*   **Code**: `load = base_load * C_RATIO if new_hw == 'MCU' else base_load`

### 3.2 Non-linear Latency Impact
*   **Problem**: Small latency is fine; large latency crashes the drone.
*   **Solution**: Exponential decay function.
*   **Code**: `factor = exp(0.1 * (latency - 20ms))` if latency > 20ms.

### 3.3 Safety Hard Constraints
*   **Problem**: Critical functions on non-safe hardware.
*   **Solution**: Penalty function.
*   **Code**: `if DAL(func) == 'A' and Type(hw) != 'Safe': return Score = 0`.

### 3.4 P95 Robustness
*   **Problem**: Averages hide spikes.
*   **Solution**: Use P95 stats from `dsm_generator`.
*   **Code**: `jitter_score = 1 - (p95_jitter / max_jitter_limit)`.

---

## 4. Execution Guide
1.  **Run HIL**: Collect logs to `src-python/data/session_xxx/`.
2.  **Generate Profile**: Run `dsm_generator.py` to create `dsm_report.json`.
3.  **Evaluate**: Run `run_architecture_scoring.py` to test specific schemes (Centralized vs Distributed).
