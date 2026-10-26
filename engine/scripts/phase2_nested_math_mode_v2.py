"""Separate source-isolated full-width invalid unpaired nested math mode openers, without inference."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import cv2
import numpy as np
from lxml import html
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'code/experimenter'), str(ROOT/'code/runtime')]
def load(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def groups(values):
    result = []
    for v in values:
        v = int(v)
        if result and v == result[-1][-1]+1:
            result[-1].append(v)
        else:
            result.append([v])
    return [(g[0],g[-1]+1) for g in result]


def lexical(content):
    if content.count('\\[') != 1 or content.count('\\]') != 1:
        return None
    match = re.fullmatch(r'(\s*\\\[\s*)(\\\()(.*)(\\\]\s*)',content,re.S)
    if not match or content.count('\\(') != 1 or '\\)' in content:
        return None
    body=match[3]
    if not body.strip():return None
    depth=0
    for token in re.findall(r'\\.|[{}]',body):
        depth += (token=='{')-(token=='}')
        if depth<0:return None
    if depth:return None
    return dict(span=[match.start(2),match.end(2)])


def transform(raw,md,image):
    result=copy.deepcopy(raw);edits=[];audit=[]
    for i,b in enumerate(result['blocks']):
        old=b.get('content') or ''
        change=lexical(old) if b['type']=='equation' else None
        if not change:continue
        canonical=old.replace('\r\n','\n')
        variants=set([old,canonical,canonical.replace('\n','\r\n')])
        matches=[(pos,value) for value in variants for pos in
                 (m.start() for m in re.finditer(re.escape(value),md))]
        unique=len(matches)==1
        audit.append(dict(owner=i,unique_md=unique,rule='unpaired_nested_inline_opener_inside_complete_display'))
        if not unique:continue
        position,bound=matches[0]
        assert bound.replace('\r\n','\n')==canonical
        md_change=lexical(bound)
        assert md_change is not None
        a,z=change['span'];new=old[:a]+old[z:]
        ma,mz=md_change['span']
        assert old[a:z]==bound[ma:mz]=='\\('
        b['content']=new
        md=md[:position+ma]+md[position+mz:]
        edits.append(dict(owner=i,removed_markup='\\(',span=[a,z],before=old,after=new,character_recovery=0))
    return result,md,edits,audit


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',required=True)
    ap.add_argument('--pages',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--hidden',action='store_true')
    args = ap.parse_args()
    source,out,pages = map(lambda p:Path(p).resolve(),[args.input,args.out,args.pages])
    assert source.is_relative_to(ROOT) and out.is_relative_to(ROOT)
    if not args.hidden:
        assert not out.exists()
        out.mkdir(parents=True)
        (out/'pages.json').write_bytes(pages.read_bytes())
        (out/'runtime_inputs.json').write_text(json.dumps(dict(inputs=str(source),pages=str(pages),pages_sha256=sha(pages))))
        from panel_hidden_0110_v2 import restricted
        command = restricted(out,['unshare','--net',sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--hidden'])
        os.execvp(command[0],command)
    from single_model_selective_v1 import HIDDEN
    assert all(Path(p).stat().st_size == 0 for p in HIDDEN)
    start = time.monotonic()
    assert sha(out/'pages.json') == load(out/'runtime_inputs.json')['pages_sha256']
    pages = out/'pages.json'
    manifest = load(pages)
    assert len({r['id'] for r in manifest}) == len(manifest)
    dest = out/'predictions'
    for sub in ['raw','markdown']:
        (dest/sub).mkdir(parents=True)
    records = []
    for row in manifest:
        name = row['id']
        assert Path(name).name == name
        rp,mp = source/'raw'/(name+'.json'),source/'markdown'/(name+'.md')
        raw,md = load(rp),mp.read_bytes().decode('utf-8')
        changes,audit = [],[]
        if any(b['type']=='equation' and lexical(b.get('content')or'') for b in raw['blocks']):
            with Image.open(row['image']) as image:
                raw,md,changes,audit = transform(raw,md,image)
        if changes:
            (dest/'raw'/rp.name).write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
            (dest/'markdown'/mp.name).write_bytes(md.encode('utf-8'))
        else:
            os.link(rp,dest/'raw'/rp.name)
            os.link(mp,dest/'markdown'/mp.name)
        records.append(dict(id=name,source=row['image'],source_sha256=sha(row['image']),
                            input_raw_sha256=sha(rp),input_md_sha256=sha(mp),
                            output_raw_sha256=sha(dest/'raw'/rp.name),output_md_sha256=sha(dest/'markdown'/mp.name),
                            changes=changes,audit=audit))
    receipt = dict(status='DIAGNOSTIC_NOT_ADOPTED',pages=len(manifest),records=records,
                   HTTP=0,tokens=0,GT_hidden=True,network_isolated=True,
                   changed_pages=sum(bool(r['changes']) for r in records),
                   changed_owners=sum(len(r['changes']) for r in records),
                   wall_seconds=time.monotonic()-start,manifest_sha256=sha(pages),
                   source_hashes={str(Path(__file__).relative_to(ROOT)):sha(__file__)})
    (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print({k:receipt[k] for k in ['pages','changed_pages','changed_owners','HTTP','wall_seconds']})


if __name__ == '__main__':
    main()
