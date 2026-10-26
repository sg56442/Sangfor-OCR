"""Final-only fresh brace wrapper with complete dependency admission before HTTP."""
import argparse,subprocess,sys,time
from phase2_final_runtime_v1 import ROOT,load,save,sha,verify_hashes
from phase2_final_brace_v1 import binding,TRANSPORT

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['inputs','pages','out','gpu','final-validation-admission','final-validation-sha256']:ap.add_argument('--'+name,required=True)
    ap.add_argument('--budget',type=int,default=8);ap.add_argument('--check-time-only',action='store_true');a=ap.parse_args()
    from pathlib import Path
    source,pages,out=map(lambda s:Path(s).resolve(),[a.inputs,a.pages,a.out]);assert out.parent==ROOT/'runs'
    assert a.gpu in ['0','1','3'] and 0<=a.budget<=8
    b=binding(source,pages,out,a.gpu,a.budget)
    from phase2_final_time_gate_v1 import deadline
    end=deadline(ROOT,__file__,b,a.final_validation_admission,a.final_validation_sha256)
    permit=load(a.final_validation_admission);verify_hashes(permit['source_hashes']);verify_hashes(permit['dependency_hashes'])
    assert all(permit['source_hashes'].get(p)==h for p,h in permit['dependency_hashes'].items())
    if a.check_time_only:print(dict(status='TIME_ADMISSION_PASS',deadline=end.isoformat(),HTTP=0));return
    began=time.monotonic();assert not out.exists();out.mkdir();save(out/'runtime_inputs.json',dict(inputs=str(source)))
    save(out/'runtime_admission.json',dict(time_binding=b,permit_sha256=sha(a.final_validation_admission)))
    subprocess.run([sys.executable,'-B',str(ROOT/'code/experimenter/brace_production_0136_v5.py'),'--inputs',str(source),'--pages',str(pages),'--out',str(out),'--gpu',a.gpu,'--budget',str(a.budget)],check=True)
    deps=load(out/'dependencies.json')['files'];assert deps==permit['dependency_hashes'];verify_hashes(deps)
    cmd=[sys.executable,'-B',str(ROOT/TRANSPORT),str(out),a.gpu,'--final-validation-admission',a.final_validation_admission,'--final-validation-sha256',a.final_validation_sha256]
    result=subprocess.run(cmd)
    if not (out/'responses.json').exists():save(out/'responses.json',[])
    from panel_hidden_0110_v2 import restricted
    subprocess.run(['unshare','--net',*restricted(out,[sys.executable,'-B',str(ROOT/'code/experimenter/brace_compose_0136_v4.py'),str(out)])],check=True)
    save(out/'runtime_completion.json',dict(observation_returncode=result.returncode,budget=a.budget,selected_output=str(out/'selected_predictions'),
        fallback_on_failed_or_missing_response=True,wall_seconds=time.monotonic()-began))
    result.check_returncode()

if __name__=='__main__':main()
