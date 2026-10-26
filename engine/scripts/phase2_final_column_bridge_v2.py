"""Zero-call source column continuation: permits and independent complete reconstruction."""
import hashlib
import json
from pathlib import Path
import sys
import time
from PIL import Image
from phase2_final_runtime_v1 import ROOT, PYTHON, inside, load, save, sha, now, verify_hashes
sys.path.insert(0,str(ROOT/'code/experimenter'))
from column_bridge_0147_v2 import proposals, apply
from column_bridge_runtime_0147_v3 import ENTRIES, admit

RUNNER='code/experimenter/column_bridge_runtime_0147_v3.py'
DEPENDENCIES='code/experimenter/column_bridge_frozen_0147_v3.json'


def input_binding(source,pages):
    source=Path(source).resolve();rows=sorted(load(pages),key=lambda r:r['id']);locked={};items=[]
    assert len(rows)==len({p['id'] for p in rows})==1651
    for row in rows:
        rp=source/'raw'/(row['id']+'.json');mp=source/'markdown'/(row['id']+'.md');im=Path(row['image'])
        for p in [rp,mp,im]:locked[str(p)]=sha(p)
        items.append((rp.name,locked[str(rp)],locked[str(mp)],locked[str(im)]))
    return locked,hashlib.sha256(json.dumps(items).encode()).hexdigest()


def prepare(plan,frozen,track,source):
    started=time.monotonic();assert track in ['A','B'] and frozen['column_bridge_runner']==RUNNER
    out=inside(plan['output']);folder=inside(plan['column_bridge_'+track+'_output']);assert not folder.exists()
    source=Path(source).resolve();pages=inside(frozen['pages']);_,digest=input_binding(source,pages)
    dirs={str(Path(p['image']).parent) for p in load(pages)};assert len(dirs)==1
    b=dict(inputs=str(source),pages=dirs.pop(),out=str(folder),budget=0,retry=0,model_calls=0,
        input_sha256=digest,dependency_lock_sha256=sha(ROOT/DEPENDENCIES))
    assert set(b)=={'inputs','pages','out','budget','retry','model_calls','input_sha256','dependency_lock_sha256'}
    active=load(ROOT/'control/final_validation_plan.json');phase=load(ROOT/'control/phase2_plan.json')
    assert active['runtime_freeze']==plan['freeze'] and active['runtime_freeze_sha256']==plan['freeze_sha256']
    hashes={str(ROOT/'code/experimenter'/p):sha(ROOT/'code/experimenter'/p) for p in ENTRIES}
    assert all(frozen['source_hashes'].get(p)==h for p,h in hashes.items())
    folder.mkdir()
    permit=folder/'permit.json';cfg=folder/'config.json'
    assert not permit.exists() and not cfg.exists()
    save(permit,dict(mode='final_validation',approved=True,approved_by='RSI',phase=phase['phase'],
        run_binding=b,source_hashes=hashes,campaign_deadline=phase['deadline_at'],not_before=active['start_at'],
        active_freeze=active['runtime_freeze'],active_freeze_sha256=active['runtime_freeze_sha256']))
    config=dict(binding=b,permit=str(permit),permit_sha256=sha(permit),dependency_lock=str(ROOT/DEPENDENCIES))
    admit(config,b);save(cfg,config);save(folder/'runtime_inputs.json',dict(inputs=str(source)))
    save(out/(track+'_column_bridge_prepare.json'),dict(at=now(),seconds=time.monotonic()-started,config_sha256=sha(cfg)))
    return ['unshare','--net',PYTHON,'-B','code/experimenter/panel_hidden_0110_v2.py',str(folder),
        PYTHON,'-B',RUNNER,'--config',str(cfg)]


def verify(folder,source,pages,*,plan=None,frozen=None,track=None):
    started=time.monotonic();folder,source,pages=map(lambda p:Path(p).resolve(),[folder,source,pages])
    receipt=load(folder/'receipt.json');locked,digest=input_binding(source,pages)
    assert receipt['pages']==1651 and receipt['HTTP']==receipt['GPU_seconds']==receipt['prompt_tokens']==receipt['completion_tokens']==0
    assert receipt['bindings']==locked and receipt['input_sha256']==digest
    verify_hashes(receipt['source_hashes']);verify_hashes(load(ROOT/DEPENDENCIES)['files'])
    if frozen is not None:
        assert plan is not None and track in ['A','B']
        assert folder==inside(plan['column_bridge_'+track+'_output'])
        cfg=load(folder/'config.json');permit=load(cfg['permit'])
        assert sha(cfg['permit'])==cfg['permit_sha256'] and permit['run_binding']==cfg['binding']
        assert cfg['binding']['inputs']==str(source) and cfg['binding']['out']==str(folder) and cfg['binding']['input_sha256']==digest
        assert permit['active_freeze_sha256']==plan['freeze_sha256']
        assert all(frozen['source_hashes'].get(p)==h for p,h in receipt['source_hashes'].items())
    rows=[];changed=[];groups=0
    for page in sorted(load(pages),key=lambda p:p['id']):
        rp=source/'raw'/(page['id']+'.json');mp=source/'markdown'/(page['id']+'.md');rb,mb=rp.read_bytes(),mp.read_bytes()
        raw=json.loads(rb);md=mb.decode();original=raw['blocks'];did=False
        with Image.open(page['image']) as im:qs=proposals(raw['blocks'],im)
        if qs:
            row=dict(raw=str(rp),source=page['image'],proposals=qs,outcomes=[]);rows.append(row)
            for q in qs:
                result,why=apply(raw,md,q);row['outcomes'].append(dict(accepted=result is not None,reason=why))
                if result:raw,md=result;did=True;groups+=1
        nr=json.dumps(raw,ensure_ascii=False,indent=2).encode() if did else rb
        nm=md.encode() if did else mb
        assert sorted(json.dumps(b,sort_keys=True,ensure_ascii=False) for b in original)==sorted(json.dumps(b,sort_keys=True,ensure_ascii=False) for b in raw['blocks'])
        if (nr,nm)!=(rb,mb):changed.append(page['id'])
        for variant in ['generator','selected']:
            for sub,path,expected in [('raw',rp,nr),('markdown',mp,nm)]:
                target=folder/(variant+'_predictions')/sub/path.name
                assert target.is_file() and not target.is_symlink() and target.read_bytes()==expected
    assert rows==receipt['rows'] and len(rows)==receipt['triggered'] and groups==receipt['applied']
    for v in ['generator','selected']:
        assert all(len(list((folder/(v+'_predictions')/sub).iterdir()))==1651 for sub in ['raw','markdown'])
    return dict(pages=1651,changed_pages=changed,groups=groups,HTTP=0,
        runtime_seconds=receipt['seconds'],verification_seconds=time.monotonic()-started,receipt_sha256=sha(folder/'receipt.json'))


if __name__=='__main__':
    pages=inside(load(ROOT/'control/freezes/phase2_AB_skew_final_v25.json')['pages']);results={}
    for label in ['A_first','A_second','B_first','B_second']:
        folder=ROOT/f'runs/column_bridge_v25_{label}_0147_v3';source=load(folder/'runtime_inputs.json')['inputs']
        results[label]=verify(folder,source,pages)
    out=ROOT/'reports/rsi_phase2_column_bridge_runtime_verified_v2.json';assert not out.exists()
    save(out,dict(status='PASS_FOUR_COMPLETE_SOURCE_AND_OUTPUT_RECONSTRUCTIONS',at=now(),results=results,verifier_sha256=sha(Path(__file__))))
    print(results)
