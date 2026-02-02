# eVTOL 实验核心机制与数据流架构

## 1. 概述
本文档详细阐述了“数据驱动的 MBSE 架构优化”实验的核心数据处理机制。
它通过数据流图清晰展示了 HIL（硬件在环）测试数据是如何一步步转化为 MOE-MOP-TPM 评价指标的。

---

## 2. 实验数据流架构图

```mermaid
graph TD
    %% 阶段 1: 数据特征提取 (Measurement)
    subgraph "Stage 1: Feature Extraction (Measurement)"
        HIL[HIL Simulation / Flight Test] -->|Raw Logs| CSVs
        
        subgraph "Raw Data (CSV)"
            FCS[fcs_telemetry.csv<br/>(State, Actuator)]
            BUS[bus_traffic.csv<br/>(Packets)]
            TRACE[load_trace.csv<br/>(CPU Load)]
        end
        
        CSVs -->|MappingConfig| GEN[dsm_generator.py]
        
        GEN -->|Calculate Stats| PROFILE[dsm_report.json<br/>(Function Profiles)]
        
        note1[关键提取指标:<br/>- P95 CPU Load<br/>- P95 Jitter<br/>- Baseline RMSE<br/>- Bandwidth]
        GEN -.-> note1
    end

    %% 阶段 2: 架构评估 (Prediction)
    subgraph "Stage 2: Architecture Evaluation (Prediction)"
        PROFILE -->|Input 1: Profiles| EVAL[evaluation_model.py]
        SCHEME[Candidate Allocation<br/>(e.g., FC -> SoC)] -->|Input 2: Scheme| EVAL
        SPECS[Hardware Specs<br/>(Capacity, Safety)] -->|Input 3: Constraints| EVAL
        
        subgraph "Evaluation Layers"
            TPM[Layer 1: TPM<br/>(Technical)] -->|Latency, Load| MOP
            MOP[Layer 2: MOP<br/>(Performance)] -->|RMSE, Stability| MOE
            MOE[Layer 3: MOE<br/>(Effectiveness)] -->|Safety, Reliability| SCORE
        end
        
        EVAL --> TPM
    end

    %% 阶段 3: 优化寻优 (Optimization)
    subgraph "Stage 3: Optimization (Search)"
        SCORE[Composite Fitness Score] -->|Feedback| GA[Genetic Algorithm]
        GA -->|Mutate/Crossover| SCHEME
        CAPELLA[Capella Logic Graph] -->|Topology Constraints| GA
    end

    style HIL fill:#f9f,stroke:#333
    style GEN fill:#bbf,stroke:#333
    style EVAL fill:#bfb,stroke:#333
    style GA fill:#fbb,stroke:#333
```

---

## 3. 详细处理流程

### 第一阶段：特征提取 (测量/Measurement)
*   **输入**: 原始 HIL 日志 (CSV格式)。
    *   `fcs_telemetry.csv`: 包含控制回路状态、位置信息、执行机构输出。
    *   `bus_traffic.csv`: 网络数据包日志。
*   **核心引擎**: `dsm_generator.py`
    *   **映射逻辑**: 通过 `MappingConfig` 将原始数据流关联到 Capella 中的逻辑功能 (Logical Functions)。
    *   **统计计算**:
        *   **负载**: 计算均值 (Mean) 和 P95 CPU 负载。
        *   **时序**: 计算均值抖动 (Jitter) 和 P95 抖动。
        *   **功耗**: 基于 PWM 或电压估算功率。
        *   **性能**: 计算基准导航误差 (Baseline RMSE = Cmd - Act)。
    *   **输出**: `dsm_report.json`
        *   包含每个功能的“画像 (Profile/Fingerprint)”。
        *   例: `{ "LF_Flight_Control": { "cpu_load_p95": 0.15, "nav_rmse": 0.5 } }`

### 第二阶段：架构评估 (预测/Prediction)
*   **输入**:
    1.  `dsm_report.json`: 基准功能画像。
    2.  `Allocation Scheme`: 待评估的候选架构方案 (例如："将飞控分配给 SoC")。
    3.  `HardwareSpecs`: 硬件约束 (算力容量、带宽限制、安全等级)。
*   **核心引擎**: `evaluation_model.py`
    *   **Layer 1: TPM (技术性能层)**
        *   **异构算力折算**: 将基准负载转换为目标硬件负载 (`Load * C_Ratio`)。
        *   **通信开销计算**: 针对跨节点连接计算序列化开销和链路延迟。
        *   *产出*: CPU余量 (Margins), 总线延迟 (Bus Latency)。
    *   **Layer 2: MOP (运行性能层)**
        *   **非线性衰减预测**: 基于总线延迟预测新的 RMSE。
        *   公式: `RMSE_pred = RMSE_base * (1 + exp(k * (Latency - Threshold)))`。
        *   *产出*: 预测后的导航精度得分。
    *   **Layer 3: MOE (效能层)**
        *   **安全检查**: 验证硬约束 (如：DAL A 功能必须在安全核)。
        *   *产出*: 安全评分, 任务可靠性。
*   **输出**: 综合适应度分数 (Composite Fitness Score, 0.0 - 1.0)。

### 第三阶段：优化寻优 (搜索/Search)
*   **输入**: 评价模型接口 + Capella 逻辑拓扑图。
*   **核心引擎**: 遗传算法 (Genetic Algorithm)
    *   **染色体**: 代表分配映射关系的整数数组。
    *   **适应度函数**: 调用 `evaluation_model.evaluate_architecture()`。
    *   **逻辑**: 通过变异 (Mutate) 和交叉 (Crossover) 操作，寻找能使综合分数最大化的分配方案。

---

## 4. 关键算法模型说明

### 3.1 异构算力模型 (Heterogeneous Compute Model)
*   **问题**: SoC (A核) 通常比 MCU (M核) 快得多。
*   **方案**: 引入 `C_RATIO` 常数 (例如 2.5)。
*   **代码逻辑**: `load = base_load * C_RATIO if new_hw == 'MCU' else base_load`。即如果从 SoC 移到 MCU，负载会因为算力变弱而膨胀。

### 3.2 非线性延迟影响 (Non-linear Latency Impact)
*   **问题**: 小延迟无感知，但一旦延迟超过控制周期，无人机会失稳。
*   **方案**: 引入 **指数衰减函数**。
*   **代码逻辑**: `factor = exp(0.1 * (latency - 20ms))` (当延迟 > 20ms 时生效)。

### 3.3 安全硬约束 (Safety Hard Constraints)
*   **问题**: 关键功能 (DAL A) 绝不能跑在非安全硬件 (QM) 上。
*   **方案**: 罚函数 (Penalty Function)。
*   **代码逻辑**: `if DAL(func) == 'A' and Type(hw) != 'Safe': return Score = 0`。

### 3.4 P95 鲁棒性统计 (P95 Robustness)
*   **问题**: 平均值会掩盖偶尔发生的卡顿 (Spikes)。
*   **方案**: 使用 `dsm_generator` 提取的 P95 统计值。
*   **代码逻辑**: `jitter_score = 1 - (p95_jitter / max_jitter_limit)`。

---

## 5. 执行指南
1.  **Run HIL**: 运行仿真，采集原始日志到 `src-python/data/session_xxx/`。
2.  **Generate Profile**: 运行 `dsm_generator.py` 生成 `dsm_report.json`。
3.  **Evaluate**: 运行 `run_architecture_scoring.py` 测试特定方案 (如：对比“集中式”与“分布式”架构的得分)。
