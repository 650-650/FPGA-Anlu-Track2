"""Execute the exporter's unmodified evidence gates, without build gates or output.

This does not export a bitstream or fabricate a build result. The final exporter
must still run every physical/freshness/timing gate after implementation ends.
"""
from pathlib import Path
import ast,importlib.util,json
R=Path(__file__).resolve().parents[1];p=R/'tools/finalize_v16_delivery.py'
s=importlib.util.spec_from_file_location('strict_exporter',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
tree=ast.parse(p.read_text(encoding='utf-8'));main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
def assign_name(node,name):return isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets)
start=next(i for i,n in enumerate(main.body) if assign_name(n,'reports'))
end=next(i for i,n in enumerate(main.body) if assign_name(n,'area'))
inputs=json.loads((R/'validation/integration_inputs.json').read_text(encoding='utf-8'))
frozen=json.loads((R/'validation/build_input_signature.json').read_text(encoding='utf-8'))
env=m.__dict__.copy();env.update(B=Path(inputs['baseline']),T=Path(inputs['teammate']),inputs=inputs,frozen=frozen,expected=set(frozen['source_sha256']))
exec(compile(ast.Module(body=main.body[start:end],type_ignores=[]),str(p)+'::evidence-only','exec'),env,env)
print('EVIDENCE_GATES_PASS_BUILD_NOT_EVALUATED',len(env['reports']))
