"""
UAV Architecture Patterns & Scenarios (Refined)
Reflecting Six-Rotor UAV Avionics: Heterogeneous SoC + 4-Partition MCU
"""

import json
import logging
from typing import Dict, List

# ==============================================================================
# 1. 硬件资源定义 (Hardware Specs)
# ==============================================================================
# SoC: 包含 CPU, NPU (AI Accelerator), ISP (Image Signal Processor)
# MCU: 包含 4个通用分区 (GP1-GP4)
HARDWARE_SPECS = {
    # --- SoC Domain (High Performance) ---
    "SoC_CPU": {
        "mips": 100000, "bw_mbps": 2000, "type": "SoC", "safety_level": "QM",
        "desc": "Main Processor (ASR/ARM)"
    },
    "SoC_NPU": {
        "mips": 500000, "bw_mbps": 5000, "type": "SoC", "safety_level": "QM",
        "desc": "Neural Processing Unit (AI)" # Massive MIPS for specific matrix ops
    },
    "SoC_ISP": {
        "mips": 200000, "bw_mbps": 4000, "type": "SoC", "safety_level": "QM",
        "desc": "Image Signal Processor"
    },
    
    # --- MCU Domain (High Safety, Real-time) ---
    "MCU_GP1": {"mips": 5000, "bw_mbps": 100, "type": "MCU", "safety_level": "ASIL-D"},
    "MCU_GP2": {"mips": 5000, "bw_mbps": 100, "type": "MCU", "safety_level": "ASIL-D"},
    "MCU_GP3": {"mips": 5000, "bw_mbps": 100, "type": "MCU", "safety_level": "ASIL-B"},
    "MCU_GP4": {"mips": 5000, "bw_mbps": 100, "type": "MCU", "safety_level": "ASIL-B"},
}

# ==============================================================================
# 2. 逻辑功能节点 (Logical Function Nodes - Refined)
# ==============================================================================
# 10个核心功能及其典型的资源需求 Profile (Aligned with Data Recorder types)
MOCK_DSM_NODES = [
    # --- MCU Domain Functions (Real-time Control) ---
    {"name": "LF_Motor_Driver", "attributes": {"profile": {"avg_execution_time_ms": 0.05, "cpu_load_factor": 0.05, "avg_power_w": 0.2, "desc": "PWM Output (fcs_pwms)"}}},
    {"name": "LF_ESC_Driver",   "attributes": {"profile": {"avg_execution_time_ms": 0.05, "cpu_load_factor": 0.05, "avg_power_w": 0.2, "desc": "ESC Telemetry (fcs_esc)"}}},
    {"name": "LF_Flight_Algo",  "attributes": {"profile": {"avg_execution_time_ms": 2.0, "cpu_load_factor": 0.35, "nav_rmse": 0.15, "avg_power_w": 1.0, "desc": "Attitude/Pos Control (fcs_datactrl)"}}},
    {"name": "LF_RC_Parser",    "attributes": {"profile": {"avg_execution_time_ms": 0.2, "cpu_load_factor": 0.05, "avg_power_w": 0.1, "desc": "RC Input (fcs_datafutaba)"}}},
    {"name": "LF_INS_Parser",   "attributes": {"profile": {"avg_execution_time_ms": 0.8, "cpu_load_factor": 0.15, "nav_rmse": 0.05, "avg_power_w": 0.5, "desc": "State Estimation (fcs_states)"}}},
    {"name": "LF_MCU_Comm",     "attributes": {"profile": {"avg_execution_time_ms": 0.5, "cpu_load_factor": 0.10, "avg_power_w": 0.2, "desc": "Cross-chip Bridge (fcs_gncbus)"}}},
    
    # --- SoC Domain Functions (Perception & Planning) ---
    {"name": "LF_Radar_Algo",    "attributes": {"profile": {"avg_execution_time_ms": 8.0, "cpu_load_factor": 0.30, "nav_rmse": 0.5, "avg_power_w": 5.0, "desc": "Lidar Processing (lidar_obstacles)"}}},
    {"name": "LF_Camera_Algo",   "attributes": {"profile": {"avg_execution_time_ms": 25.0, "cpu_load_factor": 0.60, "nav_rmse": 0.5, "avg_power_w": 8.0, "desc": "Visual Odometry"}}}, 
    {"name": "LF_Planning_Algo", "attributes": {"profile": {"avg_execution_time_ms": 12.0, "cpu_load_factor": 0.40, "nav_rmse": 0.2, "avg_power_w": 4.0, "desc": "Path Finding (planning_telemetry)"}}},
    {"name": "LF_SoC_Comm",      "attributes": {"profile": {"avg_execution_time_ms": 1.0,  "cpu_load_factor": 0.10, "avg_power_w": 1.5, "desc": "GCS Uplink"}} },
]

MOCK_DSM_EDGES = [
    # Sensor -> Algo
    {"source_name": "LF_INS_Parser", "target_name": "LF_Flight_Algo", "weight": 85}, # High freq state
    {"source_name": "LF_RC_Parser", "target_name": "LF_Flight_Algo", "weight": 40},  # Low freq cmd
    
    # Algo -> Actuator
    {"source_name": "LF_Flight_Algo", "target_name": "LF_Motor_Driver", "weight": 100}, # 400Hz PWM
    {"source_name": "LF_Flight_Algo", "target_name": "LF_ESC_Driver", "weight": 50},   # DShot Telemetry
    
    # Perception -> Planning (SoC Internal)
    {"source_name": "LF_Radar_Algo", "target_name": "LF_Planning_Algo", "weight": 300}, # PointCloud
    {"source_name": "LF_Camera_Algo", "target_name": "LF_Planning_Algo", "weight": 800}, # Image/Feature
    
    # Planning -> Control (Cross-Chip: SoC -> MCU)
    {"source_name": "LF_Planning_Algo", "target_name": "LF_SoC_Comm", "weight": 50},
    {"source_name": "LF_SoC_Comm", "target_name": "LF_MCU_Comm", "weight": 50}, # Physical Link
    {"source_name": "LF_MCU_Comm", "target_name": "LF_Flight_Algo", "weight": 50}, # Waypoints
]

MOCK_DSM_DATA = {"nodes": MOCK_DSM_NODES, "edges": MOCK_DSM_EDGES}


# ==============================================================================
# 3. 架构分配方案 (Allocation Architectures)
# ==============================================================================

class ArchitectureScenarios:
    
    @staticmethod
    def get_scheme_a_baseline() -> Dict[str, str]:
        """
        方案A: 基准方案 (Baseline / CPU Heavy)
        特点: 
        - MCU任务平均分配到 GP1/GP2
        - SoC任务全部挤在 SoC_CPU 上 (没有利用 NPU/ISP)
        预期: SoC CPU 过载，TPS/MOP 分数较低
        """
        return {
            # MCU
            "LF_Motor_Driver": "MCU_GP1", "LF_ESC_Driver": "MCU_GP1",
            "LF_Flight_Algo": "MCU_GP2",  "LF_RC_Parser": "MCU_GP2",
            "LF_INS_Parser": "MCU_GP2",   "LF_MCU_Comm": "MCU_GP1",
            # SoC (All on CPU)
            "LF_Radar_Algo": "SoC_CPU",
            "LF_Planning_Algo": "SoC_CPU",
            "LF_Camera_Algo": "SoC_CPU", # 没有任何加速
            "LF_SoC_Comm": "SoC_CPU"
        }

    @staticmethod
    def get_scheme_b_domain_accelerated() -> Dict[str, str]:
        """
        方案B: 异构加速方案 (Heterogeneous Accelerated)
        特点:
        - 利用 SoC_NPU 跑雷达算法 (Lidar Perception)
        - 利用 SoC_ISP 跑相机算法 (Visual Perception)
        - MCU 使用 4 个分区进行精细化隔离 (Safety Partitioning)
        预期: 性能最佳
        """
        return {
            # MCU Partitions (Safety, Real-time)
            "LF_Flight_Algo": "MCU_GP1",  # [Critical] Flight Control Law
            "LF_Motor_Driver": "MCU_GP1", # [Critical] Fast Loop
            "LF_ESC_Driver": "MCU_GP1",   # [Critical] Telemetry
            
            "LF_RC_Parser": "MCU_GP2",    # [Safety] Manual Override
            "LF_INS_Parser": "MCU_GP2",   # [Safety] State Estimation
            
            "LF_MCU_Comm": "MCU_GP3",     # [Comm] Bridge to SoC/GCS
            # GP4 Reserved for Redundancy or Future
            
            # SoC Domain (Performance)
            "LF_Planning_Algo": "SoC_CPU", # Path Planning (Sequential Logic)
            "LF_Radar_Algo": "SoC_NPU",    # [Accel] PointCloud NN Processing
            "LF_Camera_Algo": "SoC_ISP",   # [Accel] Image Signal Processing
            "LF_SoC_Comm": "SoC_CPU"       # Comm Stack
        }

    @staticmethod
    def get_scheme_c_integrated_central() -> Dict[str, str]:
        """
        方案C: 区域集中式 (Zonal / Integrated)
        特点:
        - 尝试将部分 MCU 非核心功能 (MCU_Comm, INS) 移入 SoC 统一处理
        - (注意: 这可能违反安全约束 Constraint Check)
        """
        return {
            "LF_Flight_Algo": "MCU_GP1", "LF_Motor_Driver": "MCU_GP1",
            "LF_ESC_Driver": "MCU_GP1",  "LF_RC_Parser": "MCU_GP1",
            
            # Moved to SoC (Risk!)
            "LF_INS_Parser": "SoC_CPU", 
            "LF_MCU_Comm": "SoC_CPU", # Merged with SoC Comm
            
            "LF_Radar_Algo": "SoC_NPU",
            "LF_Planning_Algo": "SoC_CPU",
            "LF_Camera_Algo": "SoC_ISP",
            "LF_SoC_Comm": "SoC_CPU"
        }

    @staticmethod
    def get_scheme_d_fallback_safety() -> Dict[str, str]:
        """
        方案D: 降级安全模式 (Fallback Safety)
        特点:
        - 假设 SoC 失效，规划算法降级运行在 MCU_GP4 (性能极低但可用)
        - 去除 雷达/相机 (无法在 MCU 运行)
        """
        return {
            "LF_Flight_Algo": "MCU_GP1", "LF_Motor_Driver": "MCU_GP1", 
            "LF_ESC_Driver": "MCU_GP1", "LF_RC_Parser": "MCU_GP2",
            "LF_INS_Parser": "MCU_GP2", "LF_MCU_Comm": "MCU_GP3",
            
            # SoC Failed, minimal planning fallback
            "LF_Planning_Algo": "MCU_GP4", 
            "LF_SoC_Comm": "MCU_GP3"
            
            # Capabilities Lost: Radar, Camera
        }

    @staticmethod
    def get_all_scenarios() -> Dict[str, Dict[str, str]]:
        return {
            "1. Baseline (CPU Only)": ArchitectureScenarios.get_scheme_a_baseline(),
            "2. Accelerated (NPU/ISP)": ArchitectureScenarios.get_scheme_b_domain_accelerated(),
            "3. Integrated (Mixed Crit)": ArchitectureScenarios.get_scheme_c_integrated_central(),
            "4. Safety Fallback (MCU Only)": ArchitectureScenarios.get_scheme_d_fallback_safety(),
        }

# ==============================================================================
# 4. 执行脚本
# ==============================================================================
if __name__ == "__main__":
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dsm.evaluation_model import ArchitectureEvaluator
    
    # Init Evaluator
    evaluator = ArchitectureEvaluator(MOCK_DSM_DATA, HARDWARE_SPECS)
    
    print(f"{'Scenario':<30} | {'Score':<6} | {'Nav(MOP)':<8} | {'CPU(TPM)':<8} | {'Safety'}")
    print("-" * 80)
    
    for name, allocation in ArchitectureScenarios.get_all_scenarios().items():
        res = evaluator.evaluate_architecture(allocation)
        
        score = res.get("Final_Composite_Score", 0)
        violation = res.get("Constraint_Violation", False)
        
        if violation:
             print(f"{name:<30} | {'FAIL':<6} | {'-':<8} | {'-':<8} | {'DAL VIOLATION'}")
        else:
             print(f"{name:<30} | {score:.4f} | {res['MOP_Nav_Score']:.4f}   | {res['TPM_CPU_Margin']:.4f}   | {res['MOE_Safety_Score']:.4f}")

