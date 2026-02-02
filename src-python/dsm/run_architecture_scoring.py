
import json
import os
import sys

# Ensure dsm module is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
# src-python is one level up
src_python_dir = os.path.dirname(current_dir)
if src_python_dir not in sys.path:
    sys.path.insert(0, src_python_dir)

from dsm.evaluation_model import ArchitectureEvaluator

# DSM Report Path - Assume generated previously 
# (You may need to update the date/time string if a new report was generated)
DSM_REPORT_PATH = os.path.join(src_python_dir, "data/session_20260129_134641/dsm_report_20260129_150758.json")

def run_evaluation():
    # 2. Load DSM Report
    # Check if distinct path exists, if not search
    target_path = DSM_REPORT_PATH
    if not os.path.exists(target_path):
        data_dir = os.path.join(src_python_dir, "data")
        found = False
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                if "dsm_report" in file and file.endswith(".json"):
                    target_path = os.path.join(root, file)
                    found = True
                    break
            if found: break
        
        if not found:
            print(f"Error: No DSM report found in {data_dir}")
            return
    
    print(f"Loading DSM Data from: {target_path}")
    with open(target_path, "r", encoding="utf-8") as f:
        dsm_data = json.load(f)

    # 3. Define Schemes (Allocation)
    
    # Scheme A: Centralized (MCU Bound)
    # Low Capacity HW
    scheme_centralized_mcu = {
        "LF_Perception": "MCU_Core_1",       
        "LF_Path_Planning": "MCU_Core_1",
        "LF_RC_Parser": "MCU_Core_1",
        "LF_INS_Parser": "MCU_Core_1",
        "LF_Flight_Control": "MCU_Core_1",
        "LF_Motor_Driver": "MCU_Core_1",
        "LF_Communication": "MCU_Core_1",
        "LF_SoC_Adapter": "MCU_Core_1"
    }

    # Scheme B: Distributed (MDC610 Real)
    # High Capacity SoC + Real-time MCU
    scheme_distributed = {
        "LF_Perception": "SoC_Partition_A",  
        "LF_Path_Planning": "SoC_Partition_A", 
        "LF_Communication": "SoC_Partition_A",
        "LF_RC_Parser": "MCU_Core_2",        
        "LF_INS_Parser": "MCU_Core_2",       
        "LF_Flight_Control": "MCU_Core_1",   
        "LF_SoC_Adapter": "MCU_Core_1",
        "LF_Motor_Driver": "MCU_Core_1"      
    }
    
    # 4. Hardware Specs (Capacity)
    hardware_specs = {
        "SoC_Partition_A": {"mips": 100000, "bw_mbps": 1000}, # Powerful
        "MCU_Core_1": {"mips": 5000, "bw_mbps": 100},       # Limited RTOS
        "MCU_Core_2": {"mips": 5000, "bw_mbps": 100}
    }
    
    evaluator = ArchitectureEvaluator(dsm_data, hardware_specs)

    # 5. Evaluate
    results_a = evaluator.evaluate_architecture(scheme_centralized_mcu)
    results_b = evaluator.evaluate_architecture(scheme_distributed)

    # 6. Report
    print_comparative_report(results_a, results_b)

def print_comparative_report(res_a, res_b):
    print("\n" + "="*80)
    print(f"{'METRIC':<30} | {'SCHEME A (Centralized)':<25} | {'SCHEME B (Distributed)':<25}")
    print("-" * 80)
    
    metrics = [
        ("Final Composite Score", "Final_Composite_Score"),
        ("--- MOE (Effectiveness) ---", None),
        ("Safety Score (Safety)", "MOE_Safety_Score"),
        ("Mission Reliability", "MOE_Mission_Reliability"),
        ("--- MOP (Performance) ---", None),
        ("Nav Score (Accuracy)", "MOP_Nav_Score"),
        ("Predicted RMSE (m)", "MOP_Nav_RMSE_Predicted"),
        ("--- TPM (Technical) ---", None),
        ("CPU Margin", "TPM_CPU_Margin"),
        ("Est Power (W)", "TPM_Power_Total"),
        ("Latency Penalty (ms)", "TPM_Latency_Overhead")
    ]
    
    for label, key in metrics:
        if key is None:
            print(f"{label}")
            continue
            
        val_a = res_a.get(key, "N/A")
        val_b = res_b.get(key, "N/A")
        
        # Format numbers if possible
        if isinstance(val_a, (int, float)): val_a = f"{val_a:.4f}"
        if isinstance(val_b, (int, float)): val_b = f"{val_b:.4f}"
            
        print(f"{label:<30} | {val_a:<25} | {val_b:<25}")
    print("="*80)

if __name__ == "__main__":
    run_evaluation()
