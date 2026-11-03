from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name("finalize_v7_delivery.py")),run_name="__main__")
