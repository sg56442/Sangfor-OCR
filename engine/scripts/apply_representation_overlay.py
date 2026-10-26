#!/usr/bin/env python3
"""Apply explicit general representation rules, preserving block origins."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

from mineru_vl_utils.post_process import json2md
import probe_table_math_fonts as table_math
import probe_formula_boundary_group as boundary_group

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--combined', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--features', nargs='+', choices=['fonts','aliases','formula-boundary'], required=True)
    a = p.parse_args()
    source, out = Path(a.combined).resolve(), Path(a.out).resolve()
    assert out.is_relative_to(ROOT)
    assert len(a.features) == len(set(a.features))
    source_hashes = {str(Path(x).relative_to(ROOT)):sha(x) for x in [__file__,table_math.__file__,boundary_group.__file__]}
    out.mkdir(parents=True,exist_ok=False)
    for folder in ['predictions/raw','predictions/markdown','provenance']:
        (out/folder).mkdir(parents=True)
    counts=dict(pages=0,changed_pages=0,changed_blocks=0)
    edits=[]
    for rawpath in sorted((source/'predictions/raw').glob('*.json')):
        original=json.loads(rawpath.read_text()); raw=copy.deepcopy(original); records=[]
        mdpath=source/'predictions/markdown'/(rawpath.stem+'.md')
        for index,block in enumerate(raw['blocks']):
            for feature in a.features:
                before=block.get('content','')
                if feature in ['fonts','aliases'] and block['type']=='table':
                    after,changes=table_math.transform(before,feature)
                elif feature=='formula-boundary' and block['type']=='equation':
                    after,changes=boundary_group.repair(before)
                else:
                    continue
                if changes:
                    records.append(dict(block_index=index,feature=feature,before=before,after=after,changes=changes))
                    block['content']=after
        dest_raw=out/'predictions/raw'/rawpath.name;dest_md=out/'predictions/markdown'/mdpath.name
        if records:
            assert json2md(original['blocks'])==mdpath.read_text(), 'Input raw/Markdown mismatch'
            dest_raw.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
            dest_md.write_text(json2md(raw['blocks']))
            edits.append(dict(page_locator=rawpath.stem,records=records))
        else:
            shutil.copyfile(rawpath,dest_raw);shutil.copyfile(mdpath,dest_md)
        provenance=json.loads((source/'provenance'/rawpath.name).read_text())
        assert provenance['candidate_raw_sha256']==sha(rawpath)
        provenance.update(representation_rules=records,prior_candidate_raw_sha256=sha(rawpath),
                          candidate_raw_sha256=sha(dest_raw),candidate_markdown_sha256=sha(dest_md))
        (out/'provenance'/rawpath.name).write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
        counts['pages']+=1;counts['changed_pages']+=bool(records)
        counts['changed_blocks']+=len({r['block_index'] for r in records})
    assert source_hashes=={name:sha(ROOT/name) for name in source_hashes}
    parent=json.loads((source/'composition_receipt.json').read_text())
    receipt=dict(status='COMPLETE',prior=str(source),counts=counts,order=parent['order']+a.features,
                 changes=edits,source_code_sha256=source_hashes,model_calls=0,runtime_GT=False,
                 scope='Representation compatibility and unmatched nonprinting group cleanup; no recognized character replacement')
    (out/'composition_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(counts))


if __name__=='__main__':
    main()
