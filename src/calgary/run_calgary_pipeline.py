"""
Edition B pipeline (real City of Calgary 311 data):
    1. clean_calgary.py           profile, validate, clean, quarantine
    2. build_model_calgary.py     star schema -> data/calgary/model/
    3. load_warehouse_calgary.py  SQLite + sql/calgary/*.sql -> data/calgary/sql_output/
    4. insights_calgary.py        docs/calgary/calgary_insights.md
    5. compare_editions.py        simulated vs real comparison (needs Edition A built too)

Download the data first (one time, needs internet):
    python src/calgary/download_calgary_311.py

Then:
    python src/calgary/run_calgary_pipeline.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
steps = [HERE / "clean_calgary.py", HERE / "build_model_calgary.py", HERE / "load_warehouse_calgary.py",
         HERE / "insights_calgary.py", HERE.parent / "compare_editions.py"]

for step in steps:
    print(f"\n{'=' * 70}\n> {step.name}\n{'=' * 70}")
    if subprocess.run([sys.executable, str(step)], cwd=HERE.parents[1]).returncode != 0:
        sys.exit(f"Pipeline failed at {step.name}")
print("\nEdition B complete. Import data/calgary/model/*.csv into Power BI (see powerbi/calgary/).")
