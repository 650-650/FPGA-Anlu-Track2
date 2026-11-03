"""The real display generation token also tolerates a phantom startup event."""
from pathlib import Path
import json,importlib.util,hashlib
R=Path(__file__).resolve().parents[1];V=R/'validation/startup_reset_v16';V.mkdir(parents=True,exist_ok=True)
s=importlib.util.spec_from_file_location('fixture',R/'tools/verify_latency_startup.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.V=V
current=(m.H/'video_out.v').read_text(encoding='utf-8');a=current.index('    // The input is the inverse');b=current.index('    assign S_video_frame_start',a)
legacy=current[:a]+'''    always @(posedge I_ddr_clk) begin
        S_video_vsync_1d <= I_video_vsync;
        S_video_vsync_2d <= S_video_vsync_1d;
        S_video_vsync_3d <= S_video_vsync_2d;
    end

'''+current[b:]
old=V/'legacy_video_out.v';old.write_text(legacy,encoding='utf-8')
fifo=[m.IP/'w128_d512_fifo/w128_d512_fifo.v',m.IP/'w128_d512_fifo/soft_fifo_al_4057d6b76aa6.v'];results=[]
for fixed in [0,1]:
 for running,high in [(0,0),(1,0),(0,1),(1,1)]:
  results.append(m.run_sim(f'fixed{fixed}_ddrreset{running}_vs{high}',m.UNIT,[m.H/'video_out.v' if fixed else old,m.H/'frame_latency_monitor.v',m.H/'fusion_controls.v',*fifo],{'DDR_RUN_RESET':running,'VS_HIGH':high,'EXPECT_FAIL':0}))
r={'pass':True,'cases':8,'results':results,'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'scope':'All eight cases must now recover, including the historical legacy phantom-SOF negative fixture. Production video_out remains the accepted reset version.'}
(V/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print('V16_STARTUP_RESET_8_PASS')
