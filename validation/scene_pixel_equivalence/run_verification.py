"""Re-run or collect the V16 dual-reference pixel tests. No TD or board access."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VSIM = Path(r"D:\anlu\altera\14.1S\modelsim_ase\win32aloem\vsim.exe")
parser = argparse.ArgumentParser()
parser.add_argument("--collect", action="store_true", help="Validate existing completed logs without re-running")
args = parser.parse_args()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

binding_path = HERE / "source_binding.json"
binding = json.loads(binding_path.read_text(encoding="utf-8"))
def verify_binding():
    for rel, expected in binding["production_sha256"].items():
        assert sha(ROOT / rel) == expected, "Production changed: " + rel
    for full, expected in binding["baseline_input_sha256"].items():
        assert sha(Path(full)) == expected, "Reference changed: " + full
    for name, expected in binding["validation_sha256"].items():
        assert sha(HERE / name) == expected, "Test input changed: " + name
verify_binding()

jobs = [
    ("run_scene_pixels.do", "scene_pixels_modelsim.log", ["SCENE_STYLE_EQUIVALENCE_PASS", "SCENE_DISPLAY_EQUIVALENCE_PASS"]),
    ("run_scene_production_width.do", "scene_production_width_modelsim.log", ["SCENE_STYLE_PRODUCTION_WIDTH_PASS"]),
]
checks = {}
logs = {}
for dofile, logname, markers in jobs:
    if not args.collect:
        proc = subprocess.run([str(VSIM), "-c", "-do", dofile, "-l", logname], cwd=HERE,
                              capture_output=True, text=True, timeout=600)
        (HERE / (Path(logname).stem + "_console.txt")).write_text(proc.stdout + proc.stderr, encoding="utf-8")
        assert proc.returncode == 0, "ModelSim returned " + str(proc.returncode)
    logpath = HERE / logname
    log = logpath.read_text(encoding="utf-8", errors="replace")
    assert not re.search(r"\bFAIL\b|\*\* (?:Error|Fatal):", log), "Failure in " + logname
    assert "Errors: 0, Warnings: 0" in log, "Compilation did not finish cleanly"
    for marker in markers:
        found = re.search(re.escape(marker) + r" checks=(\d+)", log)
        assert found, "Missing completion marker " + marker
        checks[marker] = int(found[1])
    warning_codes = re.findall(r"\*\* Warning: \(vsim-(\d+)\)", log)
    assert set(warning_codes).issubset({"3017", "3722"}), "Unexpected runtime warnings"
    logs[logname] = {"sha256": sha(logpath), "compile_errors": 0, "compile_warnings": 0,
                     "runtime_warning_count": len(warning_codes),
                     "runtime_warning_note": "Inherited unconnected passive pre_* outputs on first/second style windows, also present in the V15 reference"}
verify_binding()
result = {"pass": True, "created": datetime.datetime.now().astimezone().isoformat(),
          "checks": checks, "logs": logs, "production_sha256": binding["production_sha256"],
          "source_binding_sha256": sha(binding_path),
          "coverage": {"small_frames": "128x48, 6 synthetic scenes, 4 styles, 5 levels, 2 frames each",
                       "production_line_width": "1280x12, grey ramp, 4 styles, 5 levels, 2 frames each",
                       "display": "256 grey codes, 9x9x9 RGB samples, overlay/bypass/cartoon protection",
                       "equivalence": "Exact cycle: all levels equal teammate; middle level equals unchanged V15; valid/SOF/EOL preserved; frame level lock"},
          "boundaries": ["Directed RTL pixel tests, not MIPI/DDR/HDMI full-system tests", "No TD build, timing closure, programming or board observations performed by this runner"]}
(HERE / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"pass": True, "checks": checks, "result": str(HERE / "result.json")}, ensure_ascii=False))
