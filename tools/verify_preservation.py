from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name("verify_v7_preservation.py")),run_name="__main__")
