"""
eVTOL Architecture Evaluation Model (MOE-MOP-TPM)
Refactored to align with Experimental Research Scheme.

Hierarchical Metrics:
1. MOE (Measures of Effectiveness): Top-level Operational Success (Safety, Mission Reliability).
2. MOP (Measures of Performance): System functions performance (Navigation Accuracy, Control Stability).
3. TPM (Technical Performance Measures): Physical resource usage (CPU, Bandwidth, Power).

Formula Bridge:
- TPM -> MOP: Latency impacts Control Stability outcomes.
- MOP -> MOE: Stability failures impact Safety MOE.
"""

import numpy as np
import logging
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)

class ArchitectureEvaluator:
    """
    Hierarchical Architecture Evaluator
    """
    
    def __init__(self, dsm_report_data: Dict[str, Any], hardware_specs: Dict[str, Any] = None):
        """
        Args:
            dsm_report_data: Json dict from dsm_generator (nodes have 'attributes.profile')
            hardware_specs: Hardware capacities (e.g. {"SoC_A": {"mips": 10000}})
        """
        self.data = dsm_report_data
        self.nodes = {n['name']: n for n in self.data.get('nodes', [])}
        self.edges = self.data.get('edges', [])
        
        # Default Hardware Specs (Capacity definitions)
        # 1.0 represents 100% capacity of a standard unit
        self.hardware = hardware_specs or {
            "SoC_Partition_A": {"mips": 50000, "bw_mbps": 1000, "type": "SoC", "safety_level": "QM"},
            "MCU_Core_1": {"mips": 5000, "bw_mbps": 100, "type": "MCU", "safety_level": "ASIL-D"},
            "MCU_Core_2": {"mips": 5000, "bw_mbps": 100, "type": "MCU", "safety_level": "ASIL-B"},
        }
        
        # Heterogeneous Constants
        self.C_RATIO = 2.5 # SoC is 2.5x faster than MCU for same code
        self.U_SOMEIP = 0.05 # 5% CPU load per Mbps for serialization
        self.T_OVERHEAD = 2.0 # 2ms fixed overhead for cross-chip
        self.T_THRESHOLD = 20.0 # 20ms stability threshold

    def evaluate_architecture(self, allocation_map: Dict[str, str]) -> Dict[str, Any]:
        """
        Main entry point.
        Args:
            allocation_map: { "Logical_Function_Name": "Hardware_Component_Name" }
        Returns:
            Flat dictionary of all metrics for reporting.
        """
        # Hard Constraints Check (MOE Pre-check)
        penalty = self._check_constraints(allocation_map)
        if penalty > 0:
             return {"Constraint_Violation": True, "Final_Composite_Score": 0.0}

        # 1. TPM Evaluation (Resource Usage)
        tpm_scores, system_state = self._evaluate_tpm(allocation_map)
        
        # 2. MOP Evaluation (Functional Performance)
        # Passes system_state (calculated latencies) to affect performance prediction
        mop_scores = self._evaluate_mop(allocation_map, system_state)
        
        # 3. MOE Evaluation (Operational Success)
        moe_scores = self._evaluate_moe(mop_scores, tpm_scores)
        
        # Aggregate Results
        results = {
            "meta_architecture_type": self._detect_arch_type(allocation_map),
            "Constraint_Violation": False,
            **tpm_scores,
            **mop_scores,
            **moe_scores
        }
        
        # Calculate final composite score (Weighted Sum)
        results["Final_Composite_Score"] = (
            0.4 * moe_scores["MOE_Safety_Score"] + 
            0.3 * mop_scores["MOP_Nav_Score"] + 
            0.3 * tpm_scores["TPM_CPU_Margin"]
        )
        
        return results

    def _check_constraints(self, allocation: Dict[str, str]) -> float:
        """
        [MOE] Hard Constraint Check
        Rule: DAL A functions must be on MCU or Safety Partition
        """
        # Mock DAL definition (In real app, load from config)
        DAL_MAP = {
            "LF_Flight_Control": "A",
            "LF_Perception": "C", 
            "LF_Communication": "D"
        }
        
        for func, dal in DAL_MAP.items():
            if func in allocation:
                hw = allocation[func]
                hw_type = self.hardware[hw].get('type', 'Unknown')
                safety_level = self.hardware[hw].get('safety_level', 'QM')
                
                # Rule: DAL A cannot run on QM hardware (SoC) unless isolated (Simplified)
                if dal == 'A' and safety_level == 'QM':
                    logger.warning(f"Constraint Failed: {func} (DAL A) assigned to {hw} (QM)")
                    return 1.0 # Violation
        return 0.0

    def _evaluate_tpm(self, allocation: Dict[str, str]) -> Tuple[Dict, Dict]:
        """
        Step 1: Calculate Technical Performance Measures (Physical Layer)
        metrics: CPU Load, Bus Usage, Power Consumption
        """
        hw_loads = {hw: {"cpu_used": 0.0, "pwr_used": 0.0} for hw in self.hardware}
        bus_loads = {"internal": 0.0, "external": 0.0}
        
        # A. Accumulate Loads (Node Cost)
        for func_name, hw_node in allocation.items():
            if func_name not in self.nodes: continue
            
            node_profile = self.nodes[func_name]['attributes'].get('profile', {})
            
            # Base Load
            base_load = node_profile.get('cpu_load_factor', 0.01) * 1000 # Scaling factor
            
            # Apply Heterogeneous Compute Equivalence
            # If function is moved to MCU (slower), load increases
            hw_type = self.hardware[hw_node].get('type', 'SoC')
            current_load = base_load
            if hw_type == 'MCU':
                 current_load = base_load * self.C_RATIO
            
            if hw_node in hw_loads:
                hw_loads[hw_node]['cpu_used'] += current_load
            
            # Power (Watts)
            pwr_demand = node_profile.get('avg_power_w', 0.0)
            if hw_node in hw_loads:
                hw_loads[hw_node]['pwr_used'] += pwr_demand

        # B. Communication Cost (Edge Cost)
        total_latency_penalty = 0.0
        
        for edge in self.edges:
            src, tgt = edge['source_name'], edge['target_name']
            if src in allocation and tgt in allocation:
                # Check locality
                hw_src = allocation[src]
                hw_tgt = allocation[tgt]
                
                if hw_src != hw_tgt:
                    # L3 Cross-Node Communication
                    # 1. Latency Penalty
                    total_latency_penalty += self.T_OVERHEAD
                    
                    # 2. Protocol Overhead (Serialization CPU Load)
                    # We penalize both source and target CPU
                    weight_kb = edge.get('weight', 0) # Assuming weight is KB or similar
                    overhead_cpu = weight_kb * self.U_SOMEIP
                    
                    if hw_src in hw_loads: hw_loads[hw_src]['cpu_used'] += overhead_cpu
                    if hw_tgt in hw_loads: hw_loads[hw_tgt]['cpu_used'] += overhead_cpu

        # C. Calculate Margins (Score = 1 - Load/Capacity)
        scores = []
        for hw, load in hw_loads.items():
            capacity = self.hardware[hw]['mips']
            usage_ratio = load['cpu_used'] / capacity if capacity > 0 else 0
            margin = max(0, 1.0 - usage_ratio)
            scores.append(margin)
            
        avg_margin = float(np.mean(scores)) if scores else 0.0
        
        # Return Scores and State for next layer
        tpm_results = {
            "TPM_CPU_Margin": round(avg_margin, 4),
            "TPM_Power_Total": round(sum(l['pwr_used'] for l in hw_loads.values()), 2),
            "TPM_Latency_Overhead": total_latency_penalty
        }
        
        system_state = {
            "latency_penalty": total_latency_penalty,
            "hw_loads": hw_loads
        }
        
        return tpm_results, system_state

    def _evaluate_mop(self, allocation: Dict[str, str], system_state: Dict) -> Dict:
        """
        Step 2: Calculate Measures of Performance (Functional Layer)
        metrics: RMSE (Navigation Accuracy), Stability Factor
        """
        # Retrieve Baseline MOPs from Data (HIL Data)
        baseline_rmse = 0.0
        for name, node in self.nodes.items():
            profile = node['attributes'].get('profile', {})
            if 'nav_rmse' in profile:
                baseline_rmse = max(baseline_rmse, profile['nav_rmse'])
                
        # Apply degradation model based on TPM (Latency)
        latency_val = system_state['latency_penalty']
        
        # Non-linear Decay Formula
        if latency_val < self.T_THRESHOLD:
             degradation_factor = latency_val / self.T_THRESHOLD # Linear small impact
        else:
             # Exponential crash
             degradation_factor = np.exp(0.1 * (latency_val - self.T_THRESHOLD))
             
        predicted_rmse = baseline_rmse * (1 + degradation_factor)
        
        # Score calculation (Normalize: 0RMSE = 1.0, HighRMSE = 0.0)
        limit_rmse = 5.0
        mop_nav_score = max(0, 1.0 - (predicted_rmse / limit_rmse))
        
        return {
            "MOP_Nav_RMSE_Baseline": round(baseline_rmse, 4),
            "MOP_Nav_RMSE_Predicted": round(predicted_rmse, 4),
            "MOP_Nav_Score": round(mop_nav_score, 4)
        }

    def _evaluate_moe(self, mop_scores: Dict, tpm_scores: Dict) -> Dict:
        """
        Step 3: Measures of Effectiveness (Operational Layer)
        metrics: Reliability, Safety
        """
        # Reliability is impacted by Thermal Stress (TPM Power) and Accuracy (MOP RMSE)
        
        # 1. Safety Score
        # If RMSE > Threshold, Safety Plummets
        rmse = mop_scores.get("MOP_Nav_RMSE_Predicted", 0)
        safety_score = 1.0 if rmse < 3.0 else (0.5 if rmse < 5.0 else 0.1)
        
        # 2. Power Efficiency impact
        power_penalty = max(0, tpm_scores.get("TPM_Power_Total", 0) / 2000.0) # Assume 2000W budget
        mission_score = max(0, 1.0 - power_penalty)
        
        return {
            "MOE_Safety_Score": safety_score,
            "MOE_Mission_Reliability": round(mission_score, 4)
        }

    def _detect_arch_type(self, allocation: Dict) -> str:
        """Helper to label the architecture being tested"""
        # If all functions on one HW -> Centralized
        unique_hw = set(allocation.values())
        if len(unique_hw) == 1:
            return "Centralized"
        return "Distributed"
