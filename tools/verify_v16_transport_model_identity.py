"""Preserve old PAXI evidence, then certify unchanged elaborated VVP models.

This tool never simulates, edits production, or changes an old report. A final
certificate permits exactly one changed compiled source, stylize_v5_96.v, and
requires byte-identical VVP text after ASLR object-label normalization only.
Quoted strings, file_names, constants, opcodes, events and timing stay intact.
"""
from pathlib import Path
import argparse,collections,datetime,hashlib,json,re,shutil,subprocess,sys

R=Path(__file__).resolve().parents[1]
SNAP=R/'validation/pre_dsp_transport_models'
OUT=R/'validation/transport_model_identity'
STYLE='user_source/hdl_source/isp/stylize_v5_96.v'
CASES=('paxi_720p','paxi_8p_strong_stall','paxi_8p_late_return','paxi_8p_late_healthy_return')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(value,message):
    if not value:raise RuntimeError(message)
def read_json(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save_json(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def rel(p):
    p=Path(p).resolve();require(p.is_relative_to(R),'Input outside V16: '+str(p))
    return p.relative_to(R).as_posix()
def resolve_input(p):return (Path(p) if Path(p).is_absolute() else R/p).resolve()
def preserve(src,dst):
    src=Path(src);dst=Path(dst);dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists():require(sha(dst)==sha(src),'Refusing to overwrite snapshot: '+str(dst))
    else:shutil.copyfile(src,dst)
    require(sha(dst)==sha(src),'Snapshot copy changed: '+str(src))
def scope_evidence(text):
    scopes=[x for x in text.splitlines() if re.search(r'\.scope\s+module,',x)]
    bad=[x for x in scopes if re.search(r'styliz|real_style|style_guide',x,re.I)]
    require(not bad,'A style module is elaborated: '+repr(bad))
    params={m[0]:m[1] for m in re.findall(r'\.param/l "(FULL|STYLE)"[^\n]*?\+C4<([01]+)>;',text)}
    require(params.get('FULL') and int(params['FULL'],2)==1,'Elaborated FULL is not 1')
    require(params.get('STYLE') and int(params['STYLE'],2)==0,'Elaborated STYLE is not 0')
    return {'module_scope_count':len(scopes),'style_module_scopes':bad,'FULL':1,'STYLE':0}

def snapshot():
    manifest=SNAP/'manifest.json'
    if manifest.exists():
        m=read_json(manifest)
        for name,digest in m['source_sha256'].items():require(sha(R/name)==digest,'Source changed since snapshot: '+name)
        verify_snapshot(m)
        print('PRE_DSP_SNAPSHOT_ALREADY_VERIFIED',sha(manifest),flush=True);return
    m={'schema':1,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'root':str(R),'allowed_changed_source':STYLE,'cases':{},'source_sha256':{},'snapshot_artifacts':{},
       'runtime_sha256':{},'snapshot_tool_sha256':sha(Path(__file__))}
    for name in CASES:
        d=R/'validation'/name
        report=read_json(d/'result.json');started=read_json(d/'started.json')
        require(report.get('passed') is True and report.get('returncode',0)==0,'Old test did not pass: '+name)
        require(report.get('sources_still_current') is True,'Old report says source drift: '+name)
        cmd=report.get('compile_command',started.get('compile_command'))
        require(cmd==started['compile_command'],'Compile command disagrees: '+name)
        require('-Platency_video_tb.FULL=1' in cmd and '-Platency_video_tb.STYLE=0' in cmd,'Unexpected elaboration args: '+name)
        oi=cmd.index('-o')+1;old_binary=resolve_input(cmd[oi]);require(old_binary==d/'sim.vvp','Unexpected output path: '+str(old_binary))
        inputs=[resolve_input(x) for x in cmd if x.lower().endswith(('.v','.sv'))]
        require(d/'tb.sv' in inputs,'Missing real fixture: '+name)
        expected={}
        for source_map in [report['source_sha256'],started.get('source_sha256',{})]:
            for p,digest in source_map.items():
                rp=rel(resolve_input(p));require(rp not in expected or expected[rp]==digest,'Conflicting old source hashes: '+rp)
                expected[rp]=digest
        expected[rel(d/'tb.sv')]=started.get('testbench_sha256',expected.get(rel(d/'tb.sv')))
        for p in inputs:
            rp=rel(p);require(rp in expected and expected[rp]==sha(p),'Compiled input not bound to old report: '+rp)
        for rp,digest in expected.items():
            require(digest==sha(R/rp),'Source already drifted before snapshot: '+rp)
            require(rp not in m['source_sha256'] or m['source_sha256'][rp]==digest,'Cross-case source disagreement: '+rp)
            m['source_sha256'][rp]=digest
            preserve(R/rp,SNAP/'sources'/rp)
        artifacts={}
        for filename in ('result.json','started.json','compile.log','run.log','tb.sv','sim.vvp','ddr2_video_protocol_stub.sv'):
            p=d/filename
            if p.exists():
                dest=SNAP/'cases'/name/filename;preserve(p,dest)
                sr=dest.relative_to(SNAP).as_posix();m['snapshot_artifacts'][sr]=sha(dest)
                artifacts[filename]={'original_path':rel(p),'snapshot_path':sr,'sha256':sha(dest)}
        raw=old_binary.read_bytes().decode('utf-8');scopes=scope_evidence(raw)
        compiler=Path(shutil.which(cmd[0]) or cmd[0]).resolve();require(compiler.exists(),'Compiler missing')
        for dependency in [compiler,compiler.with_name('vvp.exe'),*[Path(p) for p in re.findall(r'^:vpi_module "([^"]+)";',raw,re.M)]]:
            require(dependency.is_file(),'Runtime dependency missing: '+str(dependency));m['runtime_sha256'][str(dependency)]=sha(dependency)
        m['cases'][name]={'compile_command':cmd,'output_argument_index':oi,'compiled_inputs':[rel(p) for p in inputs],
                          'artifacts':artifacts,'elaboration':scopes,'old_result_passed':True}
    require(STYLE in m['source_sha256'],'Style source absent from old input list')
    preserve(R/STYLE,SNAP/'old_stylize_v5_96.v')
    m['snapshot_artifacts']['old_stylize_v5_96.v']=sha(SNAP/'old_stylize_v5_96.v')
    m['source_snapshots_sha256']={p:sha(SNAP/'sources'/p) for p in m['source_sha256']}
    verify_snapshot(m);save_json(manifest,m)
    print('PRE_DSP_SNAPSHOT_COMPLETE cases=4 style_sha256='+m['source_sha256'][STYLE]+' manifest_sha256='+sha(manifest),flush=True)

def verify_snapshot(m):
    for p,digest in m['snapshot_artifacts'].items():require(sha(SNAP/p)==digest,'Snapshot artifact changed: '+p)
    for p,digest in m.get('source_snapshots_sha256',m['source_sha256']).items():require(sha(SNAP/'sources'/p)==digest,'Snapshot source changed: '+p)

# Icarus pointer-derived object labels only. Short deterministic labels such as
# T_0 and E_1 are intentionally untouched. Array/index suffixes stay untouched.
OBJECT=re.compile(r'(?<![A-Za-z0-9_$])(?P<prefix>[A-Za-z]+_?)(?P<address>[0-9a-fA-F]{12,16})(?P<suffix>(?:_[0-9]+)*)(?![A-Za-z0-9_$])')
QUOTED=re.compile(r'"(?:\\.|[^"\\])*"')
def normalize_vvp(text):
    mapping={};prefixes=collections.Counter();parts=[];last=0
    def replace(m):
        prefix=m['prefix'];address=m['address'];key=prefix+address
        # Prefixes must be known object namespaces, not arbitrary source names.
        require(prefix in {'S_','P_','L_','v','o','E_','A_','F_','W_','DLY_','LS_','RS_','UF_','EV_','T_'},'Unknown pointer-label namespace: '+prefix)
        if key not in mapping:mapping[key]=len(mapping)+1;prefixes[prefix]+=1
        return prefix+'@'+str(mapping[key]).zfill(8)+(m['suffix'] or '')
    for q in QUOTED.finditer(text):
        parts.append(OBJECT.sub(replace,text[last:q.start()]));parts.append(q.group());last=q.end()
    parts.append(OBJECT.sub(replace,text[last:]))
    return ''.join(parts),{'unique_object_bases':len(mapping),'namespaces':dict(prefixes)}

def normalizer_checks():
    a='S_0000025120bca090 .scope module, "file_names S_0000025120bca090";\r\nv0000025120acc340_0 .var "x", 1 0;\r\n %load/vec4 v0000025120acc340_0; C4<01>; %delay 10;\r\nLS_0000025120cb3a80_0_0 .concat [ 1 16 1 32], v0000025120acc340_0;\r\n'
    b=a.replace('S_0000025120bca090 .scope','S_0000000000abcdef .scope').replace('v0000025120acc340','v0000000000fedcba').replace('LS_0000025120cb3a80','LS_0000000000aabbcc')
    original=normalize_vvp(a)[0]
    checks={'ASLR_labels_only_equal':original==normalize_vvp(b)[0]}
    mutations={'opcode':('%load/vec4','%store/vec4'),'constant':('C4<01>','C4<10>'),
               'delay':('%delay 10','%delay 11'),'quoted_text':('file_names S_0000025120bca090','file_names S_0000000000abcdef'),
               'array_suffix':('acc340_0','acc340_1'),'concat_double_suffix':('cb3a80_0_0','cb3a80_0_1'),'line_endings':('\r\n','\n')}
    for key,(old,new) in mutations.items():checks[key+'_change_rejected']=original!=normalize_vvp(a.replace(old,new))[0]
    require(all(checks.values()),'Normalizer changed more than object addresses: '+repr(checks))
    return checks

def certify():
    checks=normalizer_checks()
    m=read_json(SNAP/'manifest.json');verify_snapshot(m)
    for p,digest in m['runtime_sha256'].items():require(sha(p)==digest,'Compiler/runtime changed: '+p)
    current={p:sha(R/p) for p in m['source_sha256']}
    changed=[p for p in current if current[p]!=m['source_sha256'][p]]
    require(changed==[STYLE],'Permitted source drift is exactly the style file; got '+repr(changed))
    OUT.mkdir(parents=True,exist_ok=True)
    cert={'schema':1,'passed':False,'method':'Exact VVP text after first-occurrence ASLR object-label alpha-renaming only',
          'scope':'Reuse only the four controlled-ISP STYLE=0 transport models; no style-pixel or board acceptance claim.',
          'snapshot_manifest_sha256':sha(SNAP/'manifest.json'),'source_sha256_old':m['source_sha256'],
          'source_sha256_current':current,'changed_sources':changed,'verifier_sha256':sha(Path(__file__)),
          'simulations_executed':0,'normalizer_self_checks':checks,'cases':{}}
    save_json(OUT/'certificate.json',cert)
    try:
        for name,item in m['cases'].items():
            for filename,a in item['artifacts'].items():require(sha(R/a['original_path'])==a['sha256'],'Original evidence changed: '+a['original_path'])
            d=OUT/name;d.mkdir(parents=True,exist_ok=True);new_binary=d/'sim.vvp'
            cmd=item['compile_command'][:];cmd[item['output_argument_index']]=str(new_binary)
            p=subprocess.run(cmd,capture_output=True,text=True,cwd=R)
            (d/'compile.log').write_text(p.stdout+p.stderr,encoding='utf-8');require(p.returncode==0,'Recompile failed: '+name)
            old=SNAP/item['artifacts']['sim.vvp']['snapshot_path']
            old_raw=old.read_bytes().decode('utf-8');new_raw=new_binary.read_bytes().decode('utf-8')
            old_scope=scope_evidence(old_raw);new_scope=scope_evidence(new_raw)
            before,before_stats=normalize_vvp(old_raw);after,after_stats=normalize_vvp(new_raw)
            # No sorting, line removal, filename replacement or opcode rewrite.
            (d/'old.normalized.vvp').write_bytes(before.encode('utf-8'))
            (d/'new.normalized.vvp').write_bytes(after.encode('utf-8'))
            same=before==after
            case={'passed':same,'old_report_sha256':item['artifacts']['result.json']['sha256'],
                  'old_log_sha256':item['artifacts']['run.log']['sha256'],'old_binary_sha256':sha(old),'new_binary_sha256':sha(new_binary),
                  'old_normalized_sha256':hashlib.sha256(before.encode()).hexdigest(),'new_normalized_sha256':hashlib.sha256(after.encode()).hexdigest(),
                  'old_labels':before_stats,'new_labels':after_stats,'old_elaboration':old_scope,'new_elaboration':new_scope,
                  'compile_command':cmd,'old_report_path':item['artifacts']['result.json']['original_path'],
                  'new_binary_path':rel(new_binary)}
            cert['cases'][name]=case;save_json(OUT/'certificate.json',cert)
            if not same:
                import difflib
                diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='old ASLR-normalized',tofile='new ASLR-normalized'))
                (d/'difference.diff').write_text(diff,encoding='utf-8')
                raise RuntimeError('Normalized VVP differs; reuse refused: '+name)
            print('TRANSPORT_MODEL_IDENTICAL',name,case['new_normalized_sha256'],flush=True)
        require(current=={p:sha(R/p) for p in current},'Source changed during proof')
        verify_snapshot(m);cert['passed']=True;save_json(OUT/'certificate.json',cert)
        print('TRANSPORT_MODEL_IDENTITY_CERTIFIED cases=4 simulations=0 '+str(OUT/'certificate.json'),flush=True)
    except Exception as exc:
        cert['error']=str(exc);save_json(OUT/'certificate.json',cert);raise

def check_certificate():
    """Exporter entry point. Recheck evidence/source/binary bindings, no compile."""
    m=read_json(SNAP/'manifest.json');verify_snapshot(m)
    c=read_json(OUT/'certificate.json')
    require(c.get('passed') is True and c.get('simulations_executed')==0,'Certificate did not pass')
    require(c['snapshot_manifest_sha256']==sha(SNAP/'manifest.json'),'Wrong snapshot manifest')
    require(c['verifier_sha256']==sha(Path(__file__)),'Verifier changed since certification')
    require(c['source_sha256_old']==m['source_sha256'],'Old source binding changed')
    require(c['source_sha256_current']=={p:sha(R/p) for p in m['source_sha256']},'Current source binding changed')
    require(c['changed_sources']==[STYLE],'Wrong allowed source drift')
    require(c['normalizer_self_checks']==normalizer_checks(),'Normalizer self checks changed')
    require(set(c['cases'])==set(CASES),'Missing certified cases')
    for p,digest in m['runtime_sha256'].items():require(sha(p)==digest,'Compiler/runtime changed: '+p)
    for name,item in m['cases'].items():
        proof=c['cases'][name]
        require(proof['passed'] is True,'Failed case: '+name)
        for filename,a in item['artifacts'].items():require(sha(R/a['original_path'])==a['sha256'],'Original evidence changed: '+a['original_path'])
        old=SNAP/item['artifacts']['sim.vvp']['snapshot_path'];new=R/proof['new_binary_path']
        require(sha(old)==proof['old_binary_sha256'] and sha(new)==proof['new_binary_sha256'],'Binary binding changed: '+name)
        oldraw=old.read_bytes().decode('utf-8');newraw=new.read_bytes().decode('utf-8')
        scope_evidence(oldraw);scope_evidence(newraw)
        before,bs=normalize_vvp(oldraw);after,ns=normalize_vvp(newraw)
        require(before==after,'Model text no longer identical: '+name)
        require(hashlib.sha256(before.encode()).hexdigest()==proof['old_normalized_sha256']==proof['new_normalized_sha256'],'Normalized model hash mismatch: '+name)
        require(bs==proof['old_labels'] and ns==proof['new_labels'],'Object-label accounting changed: '+name)
        require(proof['old_report_sha256']==item['artifacts']['result.json']['sha256'] and proof['old_log_sha256']==item['artifacts']['run.log']['sha256'],'Old report/log binding changed: '+name)
        expected=item['compile_command'][:];expected[item['output_argument_index']]=str(new)
        require(expected==proof['compile_command'],'Compile args changed beyond output path: '+name)
    print('TRANSPORT_MODEL_CERTIFICATE_CURRENT cases=4 simulations=0',flush=True)
    return c

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);group=ap.add_mutually_exclusive_group();group.add_argument('--snapshot-only',action='store_true');group.add_argument('--check-certificate',action='store_true');args=ap.parse_args()
    try:
        if args.snapshot_only:snapshot()
        elif args.check_certificate:check_certificate()
        else:certify()
    except Exception as exc:
        if not args.snapshot_only and not args.check_certificate:
            p=OUT/'certificate.json';failed=read_json(p) if p.exists() else {'schema':1}
            failed.update(passed=False,error=str(exc));save_json(p,failed)
        print('TRANSPORT_MODEL_IDENTITY_REFUSED',str(exc),file=sys.stderr);raise SystemExit(1)
