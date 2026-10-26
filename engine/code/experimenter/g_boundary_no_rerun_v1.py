#!/usr/bin/env python3
"""Current-input adapter for the frozen single G parenthesis/gap revision.

The geometry and content condition match prepare_formula_boundary.py. Unlike
that diagnostic script, untriggered ROIs need no recognition responses.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def prepare(source, out):
    source, out = Path(source).resolve(), Path(out).resolve()
    root = Path(__file__).resolve().parents[2]
    assert out.is_relative_to(root)
    out.mkdir(parents=True, exist_ok=False)
    props=json.loads((source/'proposals.json').read_text())
    answers=json.loads((source/'recognition.json').read_text())
    geometry=json.loads((source/'geometry_requests.json').read_text())
    originals={r['proposal']:r for r in geometry if r['kind']=='native'}
    groups={}
    for a in answers:groups.setdefault(a['proposal'],{})[a['kind']]=a
    requests=[];changes=[];fallback=[]
    for pi,p in enumerate(props):
        if not p['triggered']:continue
        g=groups.get(pi,{})
        if not all(k in g for k in ['left','right']):
            fallback.append({'proposal':pi,'reason':'missing_consumed_candidate'});continue
        if g['left']['content'].count('(')<=g['left']['content'].count(')'):continue
        original=originals[pi]
        assert original['bbox']==p['bbox']
        assert hashlib.sha256(Path(original['image']).read_bytes()).hexdigest()==original['encoded_sha256']
        with Image.open(original['image']) as source_image:
            im=source_image.convert('RGB')
        w,h=im.size;ink=np.asarray(im.convert('L'))<170
        edges=np.diff(np.r_[False,ink.mean(axis=0)<.01,False].astype(int))
        gaps=[(int(s),int(t)) for s,t in zip(np.where(edges==1)[0],np.where(edges==-1)[0])
              if s>p['cut']+2 and t<.8*w and t-s>=6]
        if not gaps:continue
        s,t=gaps[0];cut=(s+t)//2
        p['previous_cut']=p['cut'];p['cut']=cut
        p['boundary_revision']='left response has unmatched opening parenthesis; next image whitespace gap'
        x0,y0,x1,y1=p['bbox'];pw,ph=p['page_size'];boundary=x0+(x1-x0)*cut/w
        for kind,box,bb in [('left',(0,0,cut,h),[x0,y0,boundary,y1]),('right',(cut,0,w,h),[boundary,y0,x1,y1])]:
            crop=im.crop(box);path=out/f'p{pi}_{kind}.png';crop.save(path)
            a,b,c,d=bb
            requests.append({'proposal':pi,'kind':kind,'image':str(path),'task':'equation','bbox':bb,'size':list(crop.size),
                'affine_candidate_to_page':[(c-a)*pw/crop.width,0,a*pw,0,(d-b)*ph/crop.height,b*ph],
                'encoded_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        changes.append(pi)
    receipt={'family':'G','rule':'G_SOURCE_GRAMMAR_V4_SINGLE_BOUNDARY_REVISION','changed_proposals':changes,
             'requests':len(requests),'fallback':fallback,'source':str(source),'runtime_GT':False,
             'native_rerun_consumed':False,
             'source_geometry_sha256':hashlib.sha256((source/'geometry_requests.json').read_bytes()).hexdigest(),
             'source_proposals_sha256':hashlib.sha256((source/'proposals.json').read_bytes()).hexdigest(),
             'source_answers_sha256':hashlib.sha256((source/'recognition.json').read_bytes()).hexdigest()}
    for name,obj in [('proposals',props),('requests',requests),('preparation',receipt)]:
        (out/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    return props,requests,receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();_,_,receipt=prepare(a.source,a.out);print(json.dumps(receipt))
