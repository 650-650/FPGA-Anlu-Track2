"""Verify actual SYN ERAM INIT contents and native-model reads without running PHY."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import subprocess

HERE = Path(__file__).resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text(encoding="utf-8-sig"))


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def hash_map(values, base):
    for name, expected in values.items():
        path = Path(name.replace("\\", "/"))
        path = path if path.is_absolute() else base / path
        require(path.is_file() and sha(path) == expected, ("STALE_ROM_EVIDENCE", str(path)))


def output_bits(expression, width):
    bits = []
    for token in expression.strip("{}").split(","):
        m = re.fullmatch(r"\\u_isp_top/u_stylize/c1_sketch_ink_rom \[(\d+)(?::(\d+))?\]", token)
        if m:
            hi, lo = int(m[1]), int(m[2] or m[1])
            bits.extend(range(hi, lo - 1, -1))
        else:
            require(re.fullmatch(r"open_n\d+", token), ("UNKNOWN_MAPPED_ROM_OUTPUT", token))
            bits.append(None)
    require(len(bits) == width, ("MAPPED_ROM_PORT_WIDTH", expression, width))
    return list(reversed(bits))


def parse_roms(netlist, table):
    details, wrappers = [], []
    for label, lanes, bases in [("01", [0, 1], [24, 16]), ("23", [2, 3], [8, 0])]:
        marker = "// u_isp_top/u_stylize/sketch_ink_rom_path$u_ink_" + label + "/"
        require(netlist.count(marker) == 1, ("EXPECTED_ONE_MAPPED_ROM", label))
        start = netlist.index("PH1P_PHY_ERAM_V2 #(", netlist.index(marker))
        m = re.match(r"PH1P_PHY_ERAM_V2 #\((.*?)\)\s*\\([^\s]+)\s*\((.*?)\);",
                     netlist[start:], re.S)
        require(m is not None, ("CANNOT_PARSE_MAPPED_ROM", label))
        param_text, instance, ports_text = m.groups()
        params = dict(re.findall(r"\.(\w+)\(([^()]*)\)", param_text))
        ports = dict(re.findall(r"\.(\w+)\((.*?)\)(?:,|$)", ports_text, re.S))
        for key in ["DATA_WIDTH_A", "DATA_WIDTH_B"]:
            require(params.get(key) == '"10"', ("MAPPED_ROM_WORD_MODE", instance, key))
        for key in ["REGMODE_A", "REGMODE_B"]:
            require(params.get(key) == '"NOREG"', ("EXTRA_ROM_OUTPUT_CYCLE", instance, key))
        require(params.get("MODE") == '"DP20K"', ("MAPPED_ROM_MODE", instance))
        require(params.get("INIT_FILE", '""') in ['""', '"NONE"'], ("EXTERNAL_GATE_ROM_INIT", instance))
        for key in ["WEAMUX", "WEBMUX", "RSTAMUX", "RSTBMUX"]:
            require(params.get(key) == '"0"', ("ROM_WRITE_OR_RESET_MUX_CHANGED", instance, key))
        for key in ["CSA0", "CSA1", "CSB0", "CSB1"]:
            require(params.get(key) == '"1"', ("ROM_CS_CONSTANT_CHANGED", instance, key))
        for key in ["CSA2", "CSB2", "OCEAMUX", "OCEBMUX"]:
            require(params.get(key) == '"SIG"', ("ROM_ENABLE_MUX_CHANGED", instance, key))
        require(ports["clka"] == ports["clkb"], ("ROM_READ_CLOCKS_DIFFER", instance))
        for port in ["csa", "csb"]:
            require(ports[port].startswith("{\\u_isp_top/u_stylize/w3_v ,"),
                    ("ROM_C1_ENABLE_CHANGED", instance, port))
        for port, lane in zip(["addra", "addrb"], lanes):
            expected = (r"{\u_isp_top/u_stylize/w3_tag [4:2],\u_isp_top/u_stylize/guides["
                        + str(lane) + r"]$u_guide/O_mag ,3'b111}")
            require(ports[port] == expected, ("ROM_C1_ADDRESS_OR_LANE_CHANGED", instance, port))
        main = extra = 0
        for i in range(64):
            value = re.fullmatch(r"256'h([0-9a-fA-F]+)", params.get(f"INIT_{i:02X}", ""))
            require(value is not None, ("MISSING_GATE_INIT_WORD", instance, i))
            main |= int(value[1], 16) << (256 * i)
        for i in range(16):
            value = re.fullmatch(r"256'h([0-9a-fA-F]+)", params.get(f"INITP_{i:02X}", ""))
            require(value is not None, ("MISSING_GATE_INIT_PARITY_WORD", instance, i))
            extra |= int(value[1], 16) << (256 * i)
        assigns, port_details = [], []
        for port, extra_port, base, out, data, parity in zip(
            ["doa", "dob"], ["doa_extra", "dob_extra"], bases,
            ["qa", "qb"], ["main_a", "main_b"], ["extra_a", "extra_b"]
        ):
            main_map = output_bits(ports[port], 16)
            extra_map = output_bits(ports[extra_port], 4)
            logical_bits = [i for i in main_map + extra_map if i is not None]
            require(sorted(logical_bits) == list(range(base, base + 8)),
                    ("INCOMPLETE_MAPPED_ROM_OUTPUT", instance, port))
            for physical, logical in enumerate(main_map):
                if logical is not None:
                    assigns.append(f" assign {out}[{logical-base}]={data}[{physical}];")
            for physical, logical in enumerate(extra_map):
                if logical is not None:
                    assigns.append(f" assign {out}[{logical-base}]={parity}[{physical}];")
            decoded = []
            for address in range(2048):
                main_word = (main >> (8 * address)) & 255
                extra_word = (extra >> (2 * address)) & 3
                output = 0
                for physical, logical in enumerate(main_map):
                    if logical is not None:
                        output |= ((main_word >> physical) & 1) << (logical-base)
                for physical, logical in enumerate(extra_map):
                    if logical is not None:
                        output |= ((extra_word >> physical) & 1) << (logical-base)
                require(output == table[address],
                        ("GATE_ROM_INIT_MISMATCH", instance, port, address, output, table[address]))
                decoded.append(output)
            port_details.append({"port": port, "entries": 2048,
                                 "decoded_byte_sha256": hashlib.sha256(bytes(decoded)).hexdigest(),
                                 "main_pin_map": main_map, "extra_pin_map": extra_map})
        wrapper = f"""module gate_ink_rom_pair_{label}(input clk,enable,input[10:0]a,b,output[7:0]qa,qb);
 wire[15:0]main_a,main_b;wire[3:0]extra_a,extra_b;
 PH1P_PHY_ERAM_V2 #({param_text})u_phy(
  .addra({{a,3'b111}}),.addrb({{b,3'b111}}),.clka(clk),.clkb(clk),
  .csa({{enable,2'b00}}),.csb({{enable,2'b00}}),
  .dia(16'd0),.dib(16'd0),.dia_extra(4'd0),.dib_extra(4'd0),
  .wea(1'b0),.web(1'b0),.orsta(1'b0),.orstb(1'b0),.ocea(1'b1),.oceb(1'b1),
  .ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0),.pib_rst_redmeet_n(1'b1),
  .fifoctrl_waddr(14'd0),.fifoctrl_raddr(14'd0),.fifoctrl_we(1'b0),.fifoctrl_re(1'b0),
  .addra_casin(14'd0),.addrb_casin(14'd0),.doa(main_a),.dob(main_b),
  .doa_extra(extra_a),.dob_extra(extra_b),.ecc_sbiterr(),.ecc_dbiterr(),
  .addra_casout(),.addrb_casout(),.probe_redmeet_pa(),.probe_redmeet_pb());
""" + "\n".join(assigns) + "\nendmodule\n"
        wrappers.append(wrapper)
        details.append({"instance": instance, "parameters": params, "ports": ports,
                        "read_port_checks": port_details, "unique_addresses": 2048})
    return details, "\n".join(wrappers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=HERE.parents[1])
    parser.add_argument("--check-certificate", action="store_true",
                        help="Read-only check of the completed certificate and every bound file")
    args = parser.parse_args()
    R = args.project_root.resolve()
    V = R / "validation/sketch_rom"
    S = R / "td_project/camera_to_dsi_display_Runs/syn_1"
    result_path = V / "result.json"
    frozen_path = R / "validation/build_input_signature.json"
    if args.check_certificate:
        result = read(result_path)
        require(result.get("pass") is True, "ROM_GATE_CERTIFICATE_NOT_PASS")
        require(result["verifier_sha256"] == sha(HERE), "ROM_GATE_VERIFIER_CHANGED")
        hash_map(result["source_sha256"], R)
        hash_map(result["files_sha256"], R)
        require(result["build_input_signature_sha256"] == sha(frozen_path), "ROM_GATE_FREEZE_CHANGED")
        require(result["gate_db_sha256"] == sha(S / "camera_to_dsi_display_gate.db"), "ROM_GATE_DB_CHANGED")
        require(result["synthesis_console_sha256"] == sha(S / "build_console.log"), "ROM_SYN_LOG_CHANGED")
        print("SKETCH_ROM_GATE_CERTIFICATE_CURRENT", result["native_model_checks"], result_path)
        return
    frozen = read(frozen_path)
    hash_map(frozen["source_sha256"], R)
    started = datetime.datetime.fromisoformat(frozen["started"]).timestamp()
    syn_log = S / "build_console.log"
    log = syn_log.read_text(encoding="utf-8", errors="replace")
    require(syn_log.stat().st_mtime >= started and "FUSION_BUILD_STAGE_PASS" in log,
            "SYN_NOT_FRESH_OR_COMPLETE")
    require(not re.search(r"(?mi)\bERROR\s*:|license checkout failed", log), "SYN_STAGE_ERROR")
    gate_db = S / "camera_to_dsi_display_gate.db"
    require(gate_db.is_file() and gate_db.stat().st_mtime >= started, "NO_FRESH_SYN_GATE_DB")
    gate_hash = sha(gate_db)
    source_file = R / "user_source/hdl_source/isp/stylize_v5_96.v"
    source = source_file.read_text(encoding="utf-8")
    require("$readmem" not in source and "INIT_FILE" not in source, "STYLE_ROM_NOT_EMBEDDED")
    entries = re.findall(r"memory\[(\d+)\]=8'h([0-9a-f]{2});", source)
    require(len(entries) == 2048 and sorted(int(i) for i, _ in entries) == list(range(2048)),
            "INCOMPLETE_EMBEDDED_ROM")
    table = {int(i): int(x, 16) for i, x in entries}
    for address, value in table.items():
        level, mag = address >> 8, address & 255
        floor = {0: 64, 1: 32, 3: 6, 4: 2}.get(level, 12)
        gain = {0: 8, 1: 20, 3: 80, 4: 128}.get(level, 49)
        require(value == min(255, max(0, mag-floor)*gain//16), ("WRONG_SOURCE_ROM_ENTRY", address))
    tb = V / "sketch_rom_gate_tb.sv"
    require(tb.is_file(), ("MISSING_NATIVE_ROM_TESTBENCH", str(tb)))
    V.mkdir(parents=True, exist_ok=True)
    # Open a private project, never the project or files in the main Runs folder.
    original_project = S / "camera_to_dsi_display.prj"
    project = original_project.read_text(encoding="utf-8")
    project = re.sub(r'<Project Version="3" Minor="2"(?: Path="[^"]*")?>',
                     f'<Project Version="3" Minor="2" Path="{V.as_posix()}">', project, count=1)
    project = re.sub(r'<File Path="([^"]+)"',
                     lambda m: '<File Path="' + (S / m[1]).resolve().as_posix() + '"', project)
    private_project = V / "camera_to_dsi_display.prj"
    private_project.write_text(project, encoding="utf-8")
    gate_export = V / "gate_export.v"
    export_tcl = V / "export_gate.tcl"
    export_tcl.write_text(f"""if {{[catch {{
 import_device ph1_35p.db -package PH1P35MDG324 -speed 3
 open_project {{{private_project.as_posix()}}} -noanalyze
 import_db {{{gate_db.as_posix()}}}
 write_verilog {{{gate_export.as_posix()}}}
 puts "SKETCH_ROM_GATE_EXPORT_PASS"
}} result options]}} {{
 puts stderr "SKETCH_ROM_GATE_EXPORT_ERROR: $result"
 if {{[dict exists $options -errorinfo]}} {{puts stderr [dict get $options -errorinfo]}}
 exit 1
}}
exit 0
""", encoding="ascii")
    td = Path(r"D:\anlu\TD_6.2.1_Engineer_6.2.168.116\bin\td_commands_prompt.exe")
    export_log = V / "gate_export.log"
    with export_log.open("w", encoding="utf-8") as output:
        run = subprocess.run([td.as_posix(), export_tcl.as_posix()], cwd=V,
                             stdout=output, stderr=subprocess.STDOUT, text=True, timeout=180)
    require(run.returncode == 0 and "SKETCH_ROM_GATE_EXPORT_PASS" in export_log.read_text(encoding="utf-8"),
            "CANNOT_EXPORT_CURRENT_GATE_DB")
    details, wrapper = parse_roms(gate_export.read_text(encoding="utf-8"), table)
    wrapper_path = V / "gate_rom_pair_models.v"
    wrapper_path.write_text(wrapper, encoding="utf-8")
    (V / "mapped_rom_parameters.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
    vendor = Path(r"D:\anlu\TD_6.2.1_Engineer_6.2.168.116\sim_release\ph1p")
    vendor_files = [vendor / "ph1p_phy_eram_v2.v", vendor / "ph1p_phy_gsr.v"]
    modelsim_do = V / "run_gate_rom.do"
    modelsim_do.write_text("onerror {quit -code 1 -force}\nonbreak {resume}\n"
        "if {![file exists work]} {vlib work}\n"
        "vlog -sv " + " ".join('"' + p.as_posix() + '"' for p in vendor_files + [wrapper_path, tb])
        + "\nvsim -onfinish stop work.sketch_rom_gate_tb work.PH1P_PHY_GSR\n"
        "run -all\nquit -sim\nquit -code 0 -force\n", encoding="ascii")
    native_inputs = vendor_files + [wrapper_path, tb, modelsim_do]
    native_hashes = {str(p): sha(p) for p in native_inputs}
    native_log = V / "gate_rom_modelsim.log"
    vsim = Path(r"D:\anlu\altera\14.1S\modelsim_ase\win32aloem\vsim.exe")
    run = subprocess.run([vsim.as_posix(), "-c", "-do", modelsim_do.as_posix(), "-l", native_log.as_posix()],
                         cwd=V, capture_output=True, text=True, timeout=120)
    (V / "gate_rom_console.log").write_text(run.stdout + run.stderr, encoding="utf-8")
    native_text = native_log.read_text(encoding="utf-8", errors="replace")
    require(run.returncode == 0 and "GATE_PHYSICAL_ROM_PASS checks=8676" in native_text,
            ("NATIVE_ERAM_MODEL_FAILED", native_text[-3500:]))
    require("Errors: 0, Warnings: 0" in native_text
            and not re.search(r"\bFAIL\b|\*\* (?:Error|Fatal):", native_text), "NATIVE_ROM_SIM_FAILURE")
    hash_map(native_hashes, R)
    hash_map(frozen["source_sha256"], R)
    require(sha(gate_db) == gate_hash, "GATE_DB_CHANGED_DURING_ROM_VERIFICATION")
    new_rom_warnings = [line for line in log.splitlines() if "WARNING" in line.upper()
                        and any(name in line for name in ["sketch_ink", "u_ink_01", "u_ink_23"])]
    require(not new_rom_warnings, ("NEW_ROM_SYN_WARNING", new_rom_warnings))
    files = vendor_files + [gate_export, private_project, export_tcl, export_log,
                            wrapper_path, tb, modelsim_do, native_log, V / "mapped_rom_parameters.json",
                            V / "gate_rom_console.log"]
    files_hashes = {p.relative_to(R).as_posix() if p.is_relative_to(R) else str(p): sha(p) for p in files}
    result = {"pass": True, "created": datetime.datetime.now().astimezone().isoformat(),
        "scope": "Current mainline SYN gate.db ROM initialization and official native ERAM model; no PHY run.",
        "source_sha256": frozen["source_sha256"], "style_sha256": sha(source_file),
        "build_input_signature_sha256": sha(frozen_path), "gate_db_sha256": gate_hash,
        "synthesis_console_sha256": sha(syn_log), "verifier_sha256": sha(HERE),
        "ROM_instances": 2, "unique_addresses_checked": 4096,
        "static_port_value_checks": 8192, "native_model_checks": 8676,
        "source_table_byte_sha256": hashlib.sha256(bytes(table[i] for i in range(2048))).hexdigest(),
        "external_ROM_files_used": False, "new_ROM_SYN_warnings": new_rom_warnings,
        "files_sha256": files_hashes, "production_modified": False, "Runs_modified_by_verifier": False,
        "limits": ["Mapped initial values and native functional reads only; not placement, routing, final STA or board acceptance.",
                   "All known binary levels 0..7 checked; arbitrary X/Z address propagation is outside this equivalence claim."]}
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SKETCH_ROM_GATE_PASS", result["unique_addresses_checked"],
          result["static_port_value_checks"], result["native_model_checks"], result_path)


if __name__ == "__main__":
    main()
