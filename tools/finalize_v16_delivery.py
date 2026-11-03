"""Export V16 only after fresh build, current-source tests, and both-input preservation."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import shutil
import copy
import importlib.util
import subprocess
import sys

R = Path(__file__).resolve().parents[1]
O = R / "output"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text(encoding="utf-8-sig"))


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def hashes(values, base=R):
    require(isinstance(values, dict) and values, "MISSING_HASH_BINDING")
    for rel, expected in values.items():
        path = Path(rel.replace("\\", "/"))
        path = path if path.is_absolute() else base / path
        require(path.is_file() and sha(path) == expected,
                ("STALE_SOURCE_OR_REPORT", str(path)))


def current_nested(value):
    """Check every recorded current-source map, including per-scenario maps."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("source_sha256", "sources", "production_sha256", "current_sources"):
                hashes(item)
            elif key in ("sources_still_current", "verifier_still_current", "source_unchanged"):
                require(item is True, ("SOURCE_CHANGED_DURING_TEST", key))
            elif isinstance(item, (list, dict)):
                current_nested(item)
    elif isinstance(value, list):
        for item in value:
            current_nested(item)


def has_current_binding(value):
    if isinstance(value, dict):
        if any(isinstance(value.get(key), dict) and value[key]
               for key in ("source_sha256", "sources", "production_sha256", "current_sources")):
            return True
        return any(has_current_binding(item) for item in value.values()
                   if isinstance(item, (dict, list)))
    return isinstance(value, list) and any(has_current_binding(item) for item in value)


def critical(path):
    return {line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if "CRITICAL-WARNING:" in line}


def project_entries(path):
    entries = []
    text = path.read_text(encoding="utf-8-sig")
    for rel, body in re.findall(r'<File Path="([^"]+)"[^>]*>(.*?)</File>', text, re.S):
        resolved = (path.parent / rel).resolve()
        require(resolved.is_relative_to(R) and resolved.is_file(),
                ("EXTERNAL_OR_MISSING_BUILD_INPUT", str(resolved)))
        attrs = tuple(re.findall(r'<Attr Name="([^"]+)" Val="([^"]*)"', body))
        entries.append((str(resolved), attrs))
    require(entries, ("NO_PROJECT_INPUTS", str(path)))
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", choices=["phy_1", "phy_seed2", "phy_seed3"], default="phy_1")
    parser.add_argument("--check-only", action="store_true",
                        help="Run every delivery gate without writing output")
    args = parser.parse_args()
    P = R / "td_project/camera_to_dsi_display_Runs" / args.run
    inputs_path = R / "validation/integration_inputs.json"
    inputs = read(inputs_path)
    B, T = Path(inputs["baseline"]), Path(inputs["teammate"])
    require(B.name == "07_stylize_flame_fusion_v15_ddr_latency_final", "WRONG_V15_BASELINE")
    hashes(inputs["baseline_source_sha256"], B)
    hashes(inputs["teammate_source_sha256"], T)
    require(sha(B / "output/stylize_flame_fusion_v15_ddr_latency_final.bit")
            == inputs["baseline_bit_sha256"], "V15_BIT_CHANGED")

    frozen_path = R / "validation/build_input_signature.json"
    frozen = read(frozen_path)
    hashes(frozen["source_sha256"])
    expected = {p.relative_to(R).as_posix() for p in (R / "user_source").rglob("*") if p.is_file()}
    expected |= {"td_project/camera_to_dsi_display.al", "td_project/camera_to_dsi_display.sdc",
                 "build.ps1", "tools/prepare_project.py", "tools/build_stage.tcl"}
    require(set(frozen["source_sha256"]) == expected, "INCOMPLETE_BUILD_FREEZE")
    start = datetime.datetime.fromisoformat(frozen["started"]).timestamp()
    physical_start = start
    implementation = None
    if args.run.startswith("phy_seed"):
        selected_seed = int(args.run.removeprefix("phy_seed"))
        implementation = read(R / f"validation/{args.run}_input_signature.json")
        hashes(implementation["source_sha256"])
        require(implementation["source_sha256"] == frozen["source_sha256"]
                and implementation["seed"] == selected_seed, "SEED_SOURCE_OR_SEED_MISMATCH")
        require(implementation["original_build_signature_sha256"] == sha(frozen_path),
                "SEED2_WRONG_BUILD_FREEZE")
        gate = R / "td_project/camera_to_dsi_display_Runs/syn_1/camera_to_dsi_display_gate.db"
        require(implementation["gate_db_sha256"] == sha(gate), "SEED2_GATE_DB_CHANGED")
        hashes(implementation["config_sha256"], P)
        physical_start = datetime.datetime.fromisoformat(implementation["started"]).timestamp()
    expected_entries = project_entries(R / "td_project/camera_to_dsi_display.al")
    build_logs = {}
    for stage, minimum_time in [("syn_1", start), (args.run, physical_start)]:
        folder = R / "td_project/camera_to_dsi_display_Runs" / stage
        require(project_entries(folder / "camera_to_dsi_display.prj") == expected_entries,
                ("RUNTIME_COMPILE_INPUT_MISMATCH", stage))
        logpath = folder / "build_console.log"
        text = logpath.read_text(encoding="utf-8", errors="replace")
        require(logpath.stat().st_mtime >= minimum_time
                and "FUSION_BUILD_STAGE_PASS" in text, ("INCOMPLETE_OR_STALE_BUILD_STAGE", stage))
        require(not re.search(r"(?mi)\bERROR\s*:|license checkout failed", text),
                ("BUILD_STAGE_ERROR", stage))
        if stage.startswith("phy_seed"):
            require(f"SEED{selected_seed}_PLACE_PARAMETER_CONFIRMED {selected_seed}" in text, "SEED_NOT_CONFIRMED")
        baseline_stage = "syn_1" if stage == "syn_1" else "phy_1"
        stage_critical = critical(logpath)
        baseline_critical = critical(B / "td_project/camera_to_dsi_display_Runs"
                                     / baseline_stage / "build_console.log")
        require(not stage_critical - baseline_critical,
                ("REVIEW_NEW_STAGE_CRITICAL_WARNINGS", stage,
                 sorted(stage_critical - baseline_critical)))
        build_logs[stage] = {"path": logpath.relative_to(R).as_posix(), "sha256": sha(logpath),
                             "critical_warnings": sorted(stage_critical)}

    report_names = ["camera_to_dsi_display_phy.ts", "camera_to_dsi_display_phy.area",
                    "camera_to_dsi_display_pr.timing", "camera_to_dsi_display.bit"]
    for name in report_names:
        require((P / name).is_file() and (P / name).stat().st_mtime >= physical_start,
                ("MISSING_OR_STALE_PHYSICAL_OUTPUT", name))
    timing_text = (P / report_names[0]).read_text(encoding="utf-8", errors="replace")
    timing = {}
    for key in ["SWNS", "STNS", "HWNS", "HTNS"]:
        match = re.search(r"\b" + key + r":\s*(-?[\d.]+)ns", timing_text)
        require(match is not None, ("MISSING_FINAL_TIMING_VALUE", key))
        timing[key] = float(match[1])
    require(timing["SWNS"] >= 0 and timing["HWNS"] >= 0
            and timing["STNS"] == timing["HTNS"] == 0, ("TIMING_FAIL", timing))
    old_critical = critical(B / "td_project/camera_to_dsi_display_Runs/phy_1/build_console.log")
    now_critical = critical(P / "build_console.log")
    require(not now_critical - old_critical,
            ("REVIEW_NEW_CRITICAL_WARNINGS", sorted(now_critical - old_critical)))
    reports = {}
    # STYLE=0 controlled-ISP transport fixtures do not elaborate stylize.
    # Reuse their completed traces ONLY after exact current VVP identity is
    # rechecked. Old reports are immutable and retain their original hashes.
    identity_path = R / "tools/verify_v16_transport_model_identity.py"
    identity_spec = importlib.util.spec_from_file_location("v16_transport_identity", identity_path)
    identity_module = importlib.util.module_from_spec(identity_spec)
    identity_spec.loader.exec_module(identity_module)
    identity = identity_module.check_certificate()
    style_rel = "user_source/hdl_source/isp/stylize_v5_96.v"
    require(identity["changed_sources"] == [style_rel], "MODEL_IDENTITY_SOURCE_SCOPE")
    identity_report = R / "validation/transport_model_identity/certificate.json"
    reports["transport_model_identity"] = {
        "path": identity_report.relative_to(R).as_posix(), "sha256": sha(identity_report)
    }
    transport_cases = {
        "full720p_actual_PAXI": "paxi_720p", "overflow_rejected": "paxi_8p_strong_stall",
        "late_returns_rejected": "paxi_8p_late_return",
        "late_return_after_healthy_frames": "paxi_8p_late_healthy_return",
    }

    def report(label, rel, flag="pass", verifier=None):
        path = R / rel
        value = read(path)
        require(value.get(flag) in (True, "PASS"), ("TEST_NOT_PASSED", label, value.get(flag)))
        require(has_current_binding(value), ("TEST_HAS_NO_CURRENT_SOURCE_BINDING", label))
        if label in transport_cases:
            proof = identity["cases"][transport_cases[label]]
            require(proof["old_report_sha256"] == sha(path), "WRONG_CERTIFIED_TRANSPORT_REPORT")
            require(value["source_sha256"][style_rel] == identity["source_sha256_old"][style_rel],
                    "WRONG_OLD_STYLE_BINDING")
            normalized_binding = copy.deepcopy(value)
            normalized_binding["source_sha256"][style_rel] = identity["source_sha256_current"][style_rel]
            # All other original input hashes must still match literally.
            current_nested(normalized_binding)
        else:
            current_nested(value)
        if verifier:
            require(value.get("verifier_sha256") == sha(R / "tools" / verifier),
                    ("STALE_VERIFIER", label))
        reports[label] = {"path": rel, "sha256": sha(path)}
        if label in transport_cases:
            reports[label]["reuse_basis"] = "Exact elaborated VVP identity; no style instance; original trace/report unchanged"
            reports[label]["model_identity_certificate_sha256"] = sha(identity_report)
        return value

    scope = report("source_scope", "validation/v16_scope/result.json",
                   verifier="verify_v16_scope.py")
    require(scope["source_sha256"] == {k: frozen["source_sha256"][k]
                                      for k in expected if k.startswith("user_source/")},
            "SCOPE_NOT_CURRENT_FROZEN_SOURCE")
    hashes(scope["baseline_source_sha256"], B)
    hashes(scope["teammate_source_sha256"], T)
    require(scope["baseline_source_sha256"] == inputs["baseline_source_sha256"]
            and scope["teammate_source_sha256"] == inputs["teammate_source_sha256"],
            "SCOPE_INPUTS_DIFFER_FROM_INTEGRATION_INPUTS")
    for key in ["top_only_levels", "SW2_detection_tracking_alarm_unchanged",
                "camera_crop_pins_clocks_unchanged", "V15_transport_fixes_unchanged",
                "observer_outputs_only_to_HUD", "normal_clear_keeps_middle_level_outside_SW1"]:
        require(scope.get(key) is True, ("SOURCE_SCOPE_GUARD_FAILED", key))

    pixel = report("five_level_pixels", "validation/scene_pixel_equivalence/result.json")
    expected_checks = {"SCENE_STYLE_EQUIVALENCE_PASS": 923241,
                       "SCENE_DISPLAY_EQUIVALENCE_PASS": 26068,
                       "SCENE_STYLE_PRODUCTION_WIDTH_PASS": 326208}
    require(pixel["checks"] == expected_checks and sum(pixel["checks"].values()) == 1275517,
            "PIXEL_EQUIVALENCE_CHECKS_MISMATCH")
    pixel_folder = R / "validation/scene_pixel_equivalence"
    binding_path = pixel_folder / "source_binding.json"
    require(pixel["source_binding_sha256"] == sha(binding_path), "STALE_PIXEL_SOURCE_BINDING")
    binding = read(binding_path)
    hashes(binding["production_sha256"])
    hashes(binding["baseline_input_sha256"])
    hashes(binding["validation_sha256"], pixel_folder)
    require(pixel["production_sha256"] == binding["production_sha256"], "PIXEL_SOURCE_MAP_MISMATCH")
    for name, item in pixel["logs"].items():
        require(sha(pixel_folder / name) == item["sha256"], ("PIXEL_LOG_CHANGED", name))
        require(item["compile_errors"] == item["compile_warnings"] == 0, "PIXEL_COMPILE_FAILURE")

    # The new source-embedded ink tables must also exist in the actual SYN
    # ERAM initialization, with the vendor model's real data/parity mapping.
    rom_check = subprocess.run(
        [sys.executable, str(R / "tools/verify_sketch_rom_gate.py"), "--check-certificate"],
        cwd=R, capture_output=True, text=True)
    require(rom_check.returncode == 0 and "SKETCH_ROM_GATE_CERTIFICATE_CURRENT" in rom_check.stdout,
            ("SKETCH_ROM_GATE_CERTIFICATE_REJECTED", rom_check.stdout, rom_check.stderr))
    rom = report("sketch_ROM_gate", "validation/sketch_rom/result.json",
                 verifier="verify_sketch_rom_gate.py")
    require(rom["source_sha256"] == frozen["source_sha256"]
            and rom["style_sha256"] == frozen["source_sha256"][style_rel]
            and rom["build_input_signature_sha256"] == sha(R / "validation/build_input_signature.json"),
            "ROM_GATE_SOURCE_BINDING_MISMATCH")
    require((rom["ROM_instances"], rom["unique_addresses_checked"],
             rom["static_port_value_checks"], rom["native_model_checks"])
            == (2, 4096, 8192, 8676), "ROM_GATE_COVERAGE_MISMATCH")
    require(not rom["external_ROM_files_used"] and not rom["new_ROM_SYN_warnings"],
            "ROM_GATE_INITIALIZATION_REVIEW_REQUIRED")
    hashes(rom["files_sha256"])

    controls = report("controls_levels", "validation/controls_levels/result.json",
                      verifier="verify_v16_controls.py")
    require({item["top"]: item["checks"] for item in controls["results"]}
            == {"controls_params_tb": 58, "compare_tb": 77726}
            and all(item["pass"] is True for item in controls["results"]), "CONTROLS_CHECKS_MISMATCH")
    require(controls["teammate_TB_sha256"] == sha(T / "validation/controls_params_tb.sv"),
            "TEAMMATE_CONTROLS_TB_CHANGED")
    hud = report("chinese_HUD", "validation/chinese_hud/result.json", "status")
    require(hud["page_cases"] == 71 and hud["style_level_cases"] == 20
            and hud["compared_pixels"] == 16358400
            and hud["control_switch_probes"] == 4096, "CHINESE_HUD_COVERAGE_MISMATCH")
    preserved = report("HUD_preservation", "validation/v16_hud_preservation/result.json",
                       "status", "verify_v16_hud_preservation.py")
    hashes(preserved["baseline_sources"], B)
    require(preserved["fresh_baseline_rtl_cases"] == 51
            and len(preserved["non_sw1_whole_pages_identical"]) == 47
            and len(preserved["sw1_only_first_row_changed"]) == 4
            and len(preserved["level_case_remaining_pixels_identical"]) == 20
            and preserved["allowed_changed_y"] == [552, 583], "HUD_PRESERVATION_SCOPE_MISMATCH")
    require(preserved["baseline_result_sha256"] == sha(B / "validation/chinese_hud/result.json")
            and preserved["new_result_sha256"] == sha(R / "validation/chinese_hud/result.json"),
            "HUD_PRESERVATION_RESULT_CHANGED")

    for label, folder, cases, verifier in [
        ("startup_source_identity", "startup_source_identity", 29, "verify_v16_startup_source.py"),
        ("startup_display_identity", "startup_display_identity", 7, "verify_v16_startup_display.py"),
        ("startup_reset", "startup_reset_v16", 8, "verify_v16_startup_reset.py"),
    ]:
        value = report(label, f"validation/{folder}/result.json", verifier=verifier)
        require(value["cases"] == cases and len(value["results"]) == cases, ("STARTUP_CASE_COUNT", label))
        for item in value["results"]:
            require(item.get("pass", item.get("returncode") == 0) is True,
                    ("STARTUP_SCENARIO_FAILED", label, item))
        if folder == "startup_source_identity":
            require(value["identity_and_timestamp_checks"] > 0, "NO_SOURCE_IDENTITY_CHECKS")
            for item in value["results"]:
                path = (R / "validation" / folder
                        / f"m{item['mode']}_half{item['ddr_half_ps']}_phase{item['phase_ps']}" / "run.log")
                require(sha(path) == item["log_sha256"], ("STARTUP_LOG_CHANGED", str(path)))
    provenance = report("provenance_unit", "validation/latency_provenance_unit/result.json",
                        verifier="verify_latency_provenance.py")
    require(provenance["cases"] == 32 and provenance["checks"] >= 172, "PROVENANCE_COVERAGE")
    require(provenance["testbench_sha256"] == sha(R / "validation/latency_provenance_unit/tb.sv"),
            "PROVENANCE_TB_CHANGED")
    for label, folder, verifier in [
        ("ddr_handshake", "ddr_handshake", "verify_ddr_handshake.py"),
        ("ddr_handshake_stream", "ddr_handshake_stream", "verify_ddr_handshake_stream.py"),
    ]:
        value = report(label, f"validation/{folder}/result.json", "passed", verifier)
        require(len(value.get("cases", value.get("summary", []))) == 9, ("DDR_CASE_COUNT", label))
    for label, folder, lines, fault, strong in [
        ("full720p_actual_PAXI", "paxi_720p", 720, False, False),
        ("overflow_rejected", "paxi_8p_strong_stall", 8, False, True),
        ("late_returns_rejected", "paxi_8p_late_return", 8, True, False),
    ]:
        value = report(label, f"validation/{folder}/result.json", "passed",
                       "verify_latency_paxi_transport.py")
        require(value["returncode"] == 0 and value["width"] == 1280
                and value["height"] == lines and value["source_frames"] == 9
                and value["fault_vs_return"] is fault and value["strong_backpressure"] is strong,
                ("PAXI_SCENARIO_MISMATCH", label))
        require(value["pixel_verified_valid_frames"] >= 5
                and value["event_time_verified_frames"] == value["pixel_verified_valid_frames"],
                ("INCOMPLETE_PAXI_PIXEL_OR_TIME_ORACLE", label))
        require(value["testbench_sha256"] == sha(R / f"validation/{folder}/tb.sv"),
                ("PAXI_TB_CHANGED", label))
        require(value["base_fixture_sha256"] == sha(Path(value["base_fixture"])),
                ("PAXI_BASE_FIXTURE_CHANGED", label))
        log = (R / f"validation/{folder}/run.log").read_text(encoding="utf-8", errors="replace")
        require("PAXI_TRANSPORT_PASS" in log and "VTC_RESULT" in log, ("PAXI_LOG_INCOMPLETE", label))
        if lines == 720:
            require(re.search(r"PAXI_PIXEL_SUMMARY .*output_fifo_overflows=0\b", log)
                    and re.search(r"VTC_RESULT .*under=0\b", log), "FULL720P_FIFO_OR_UNDERFLOW")
    healthy = report("late_return_after_healthy_frames",
                     "validation/paxi_8p_late_healthy_return/result.json", "passed",
                     "verify_latency_paxi_late_healthy.py")
    require(healthy["returncode"] == 0 and healthy["healthy_frames_before_fault"] >= 2
            and healthy["healthy_frames_after_fault"] >= 4, "LATE_HEALTHY_RECOVERY_INCOMPLETE")

    area = (P / "camera_to_dsi_display_phy.area").read_text(encoding="utf-8", errors="replace")
    resources = {}
    for key, pattern, capacity in [
        ("slice", r"^#slice\s+(\d+)", 21216), ("lut6", r"^#lut6\s+(\d+)", 21216),
        ("slice_reg", r"^\s*#slice reg\s+(\d+)", 42432),
        ("eram", r"^#eram\s+(\d+)", 108), ("dsp", r"^#dsp\s+(\d+)", 40),
    ]:
        found = re.search(pattern, area, re.M)
        require(found is not None, ("MISSING_RESOURCE", key))
        used = int(found[1])
        require(used <= capacity, ("RESOURCE_OVERFLOW", key, used, capacity))
        resources[key] = {"used": used, "capacity": capacity, "remaining": capacity - used}
    # Recheck all mutable evidence immediately before the first delivery write.
    hashes(frozen["source_sha256"])
    hashes(inputs["baseline_source_sha256"], B)
    hashes(inputs["teammate_source_sha256"], T)
    identity_module.check_certificate()
    for item in reports.values():
        require(sha(R / item["path"]) == item["sha256"], ("REPORT_CHANGED_DURING_EXPORT", item["path"]))
    name = "stylize_flame_fusion_v16_scene_levels_latency.bit"
    bit = P / "camera_to_dsi_display.bit"
    manifest = {
        "version": "V16", "created": datetime.datetime.now().astimezone().isoformat(),
        "bitstream": name, "bit_sha256": sha(bit), "bit_bytes": bit.stat().st_size,
        "timing_ns": timing, "resources": resources, "implementation_run": args.run,
        "placement_seed": implementation['seed'] if implementation else None,
        "placement_seed_mode": "explicit" if implementation else "tool default; enable_seed=off",
        "baseline": str(B), "teammate": str(T), "baseline_bit_sha256": inputs["baseline_bit_sha256"],
        "source_sha256": scope["source_sha256"], "tests": reports, "build_logs": build_logs,
        "build_input_signature_sha256": sha(frozen_path),
        "integration_inputs_sha256": sha(inputs_path),
        "transport_model_reuse": "Completed original controlled-ISP traces plus exact current elaborated VVP identity certificate; style pixels independently rerun on current source",
        "delivery_verifier_sha256": sha(Path(__file__)),
        "critical_warnings": sorted(now_critical), "added_critical_warnings": [],
        "build_reports": {n: sha(P / n) for n in report_names[:-1]},
        "pixel_equivalence_checks": 1275517,
        "controls_checks": {"five_levels": 58, "V15_cycle_equivalence": 77726},
        "programmed": False, "observed_on_board": False,
        "baseline_hardware_observation": "User observed V15 latency on board; startup required waiting/reset in some trials. This does not establish V16 board acceptance.",
        "changes": [
            "Retain all five teammate levels; exact middle-level V15 pixels and all-level teammate pixels.",
            "Chinese SW1 level row; retain all non-SW1 HUD pages and source/latency paths.",
            "Observer uses camera/actual HDMI Gray generation tags, 2FF and SOF plus two DDR clocks for identity association.",
            "Observer compacts redundant slot source/claim bookkeeping; write_start sticky protection retained.",
            "Two embedded dual-read synchronous ink ROMs replace default sketch arithmetic at the same C1 boundary; actual SYN initialization and vendor ERAM reads verified.",
        ],
        "measurement": "First accepted unpacked RAW group to first final active HDMI transmitter-input pixel of the actual DDR slot generation; publish after whole-frame/read retirement; excludes sensor exposure and monitor response.",
        "limits": [
            "Missing packed SOF that makes the RAW origin queue ambiguous remains fail-closed until reset; no latest-timestamp fallback.",
            "Physical causes of every hardware startup event have not been directly probed.",
            "DDR controller/PHY/memory behavioral fixtures and directed RTL do not establish physical board, visual, persistence or long-run acceptance.",
        ],
    }
    if implementation:
        manifest["implementation_input_signature_sha256"] = sha(R / f"validation/{args.run}_input_signature.json")
    if args.check_only:
        print("V16_STRICT_CHECK_PASS", timing, resources)
        return
    O.mkdir(exist_ok=True)
    shutil.copy2(bit, O / name)
    require(sha(O / name) == manifest["bit_sha256"], "EXPORTED_BIT_COPY_MISMATCH")
    for item in report_names[:-1]:
        shutil.copy2(P / item, O / item)
    (O / "build_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (O / "SHA256.txt").write_text(manifest["bit_sha256"] + "  " + name + "\n", encoding="ascii")
    print("V16_STRICT_DELIVERY_PASS", name, manifest["bit_sha256"], timing, resources)


if __name__ == "__main__":
    main()
