
import os
import sys
import logging
import json

# Setup paths to ensure we can import modules from src-python
current_dir = os.path.dirname(os.path.abspath(__file__))
# src-python is one level up from dsm/
src_python_dir = os.path.dirname(current_dir)
if src_python_dir not in sys.path:
    sys.path.insert(0, src_python_dir)

from dsm import DSMGenerator
from config import MappingConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BenchmarkVerifier")

def verify_and_generate():
    # 1. Define the session to analyze
    session_id = "session_20260129_134641"
    
    # Note: data_recorder defaults to Log/DSM/ relative to project root usually, 
    # but here we are in src-python/dsm.
    # The workspace structure puts Log/ inside Apollo-GCS-Web/.
    # So if we are in src-python/dsm, we need to go up two levels.
    project_root = os.path.dirname(src_python_dir)
    log_dir = os.path.join(project_root, "Log", "DSM")
    
    logger.info(f"Target Session: {session_id}")
    logger.info(f"Log Directory: {log_dir}")
    
    session_path = os.path.join(log_dir, session_id)
    if not os.path.exists(session_path):
        logger.error(f"Session path not found: {session_path}")
        return

    # 2. Verify CSV existence and basic stats
    csv_files = ["fcs_telemetry.csv", "planning_telemetry.csv", "radar_data.csv", "bus_traffic.csv"]
    for csv in csv_files:
        f_path = os.path.join(session_path, csv)
        if os.path.exists(f_path):
            size = os.path.getsize(f_path)
            logger.info(f"[OK] Found {csv} ({size} bytes)")
        else:
            logger.warning(f"[MISSING] {csv} not found! (Crucial for specific node weights)")

    # 3. Initialize DSM Generator
    logger.info("Initializing DSM Generator with Default Configuration...")
    try:
        # Load default mapping config
        config = MappingConfig() 
        generator = DSMGenerator(config)
        
        # Override log directory to point to the correct absolute path
        generator.log_dir = log_dir
        
    except Exception as e:
        logger.error(f"Failed to initialize generator: {e}")
        return

    # 4. Generate the Benchmark DSM
    logger.info("Generating Benchmark DSM Report...")
    try:
        # Running generation
        # Note: generate_dsm_report calls _load_raw_data internally
        report = generator.generate_dsm_report(
            session_id=session_id,
            base_directory=log_dir  # Pass explicit base dir to avoid path issues
        )
        
        # 5. Output Result
        output_path = report.get("output_path")
        
        # FIX: The key returned by DSMGenerator is "matrix", not "dsm_matrix"
        dsm_matrix = report.get("matrix") 
        
        if dsm_matrix is None:
             logger.error(f"DSM Matrix not found in report result. Keys found: {list(report.keys())}")
             return

        print("\n" + "="*50)
        print(f"BENCHMARK DSM GENERATED SUCCESSFULLY")
        print("="*50)
        print(f"Report Saved to: {output_path}")
        print(f"Matrix Dimensions: {len(dsm_matrix)} x {len(dsm_matrix)} nodes")
        
        # Print a snippet of the matrix for verification
        print("\nMatrix Snippet (Top 3x3):")
        nodes = report.get("nodes", [])
        for i in range(min(3, len(nodes))):
            row = dsm_matrix[i][:3] if i < len(dsm_matrix) else []
            print(f"{nodes[i]['name']}: {row}")
            
    except Exception as e:
        logger.error(f"Error during DSM generation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_and_generate()
