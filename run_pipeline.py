"""
Runs the full pipeline end to end:
    1. generate raw source extracts      (src/generate_data.py)
    2. validate, clean, quarantine        (src/clean_data.py)
    3. build the star schema             (src/build_model.py)
    4. load SQLite warehouse + run SQL   (src/load_warehouse.py)

Usage:
    python run_pipeline.py            # full rebuild (regenerates raw data)
    python run_pipeline.py --skip-generate
"""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).parent / "src"
steps = ["generate_data.py", "clean_data.py", "build_model.py", "load_warehouse.py"]
if "--skip-generate" in sys.argv:
    steps = steps[1:]

for step in steps:
    print(f"\n{'=' * 70}\n> {step}\n{'=' * 70}")
    result = subprocess.run([sys.executable, str(SRC / step)], cwd=SRC.parent)
    if result.returncode != 0:
        sys.exit(f"Pipeline failed at {step}")
print("\nPipeline complete. Import data/model/*.csv into Power BI (see powerbi/POWER_BI_BUILD_GUIDE.md).")
