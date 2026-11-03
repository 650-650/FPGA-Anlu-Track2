"""Run eight isolated clock-start/VS regressions, no obsolete mc_en RAM model."""
from pathlib import Path
import importlib.util,json,hashlib
R=Path(__file__).resolve().parents[1];V=R/'validation/latency_startup_v15';V.mkdir(parents=True,exist_ok=True)
s=importlib.util.spec_from_file_location('fixture',R/'tools/verify_latency_startup.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
m.V=V
current=(m.H/'video_out.v').read_text(encoding='utf-8')
a=current.index('    // The input is the inverse');b=current.index('    assign S_video_frame_start',a)
legacy=current[:a]+'''    always @(posedge I_ddr_clk) begin
        S_video_vsync_1d <= I_video_vsync;
        S_video_vsync_2d <= S_video_vsync_1d;
        S_video_vsync_3d <= S_video_vsync_2d;
    end

'''+current[b:]
old=V/'legacy_video_out.v';old.write_text(legacy,encoding='utf-8')
fifo=[m.IP/'w128_d512_fifo/w128_d512_fifo.v',m.IP/'w128_d512_fifo/soft_fifo_al_4057d6b76aa6.v']
results=[]
for fixed in [0,1]:
 for running,high in [(0,0),(1,0),(0,1),(1,1)]:
  name=f"{'fixed' if fixed else 'legacy'}_ddrreset{running}_vs{high}"
  results.append(m.run_sim(name,m.UNIT,[m.H/'video_out.v' if fixed else old,m.H/'frame_latency_monitor.v',m.H/'fusion_controls.v',*fifo],{'DDR_RUN_RESET':running,'VS_HIGH':high,'EXPECT_FAIL':int(not fixed and not running and not high)}))
r={'passed':True,'cases':len(results),'results':results,'scope':__doc__,'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(V/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print('V15_STARTUP_8_PASS')
