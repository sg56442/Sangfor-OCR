"""General selection of a same-model table proposal from current inputs only."""
import html
from pathlib import Path
import re
import sys
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/research'),str(ROOT/'code/experimenter')]
from table_mechanisms import grids
from phase2_local_cell_gate_0012 import detect


def signature(markup):
    parsed=grids(markup)
    if len(parsed)!=1 or any(parsed[0][k] for k in ['holes','conflicts','span_beyond_rows']):
        return None
    g=parsed[0]
    rows={c['row'] for c in g['cells'] if str(c['text']).strip()}
    text=' '.join(str(c['text']) for c in g['cells'])
    text=unicodedata.normalize('NFKC',html.unescape(text)).replace('−','-')
    text=text.replace('{',' ').replace('}',' ')
    tokens=re.findall(r'[+\-]|\d+(?:\.\d*)?|\.\d+',text)
    return dict(nonempty_row_starts=len(rows),rows=g['rows'],numeric_tokens=tokens)


def content_key(text):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',html.unescape(text)))


def source_merge(image,before,after,index):
    old,new=grids(before['blocks'][index]['content'])[0],grids(after['blocks'][index]['content'])[0]
    rec=dict(accepted=False,reason='source_grid_unresolved')
    if old['width']!=new['width'] or old['rows']<=new['rows']:
        return dict(rec,reason='not_same_column_row_reduction')
    first,second=detect(image,after,index,185),detect(image,after,index,220)
    rec['source_shapes']=[first.get('source_shape'),second.get('source_shape')]
    if first['reason']!='local_axes_mapped' or second['reason']!='local_axes_mapped':
        return rec
    for axis in ['xs','ys']:
        if len(first[axis])!=len(second[axis]) or any(abs(x-y)>2 for x,y in zip(first[axis],second[axis])):
            return dict(rec,reason='source_axes_unstable')
    locals_by_cell={c['cell_index']:c for c in second['cells']}
    merges=[];deleted=set()
    for ci,cell in enumerate(new['cells']):
        target=content_key(cell['text'])
        if cell['colspan']!=1 or not target:
            continue
        prior=[c for c in old['cells'] if c['col']==cell['col'] and c['colspan']==1]
        matches=[]
        for start in range(len(prior)):
            text=''
            for end in range(start,len(prior)):
                current=prior[end]
                if current['rowspan']!=1 or not content_key(current['text']):
                    break
                if end>start and prior[end-1]['row']+1!=current['row']:
                    break
                text+=content_key(current['text'])
                if len(text)>len(target):
                    break
                if end>start and text==target:
                    matches.append(prior[start:end+1])
        if not matches:
            continue
        if len(matches)!=1:
            return dict(rec,reason='ambiguous_old_cell_sequence')
        local=locals_by_cell.get(ci,{})
        if not local.get('eligible'):
            return dict(rec,reason='merge_cell_not_closed_and_independently_anchored',cell=ci,
                        local_reason=local.get('reason'))
        source_rows=[c['row'] for c in matches[0]]
        deleted.update(source_rows[1:])
        merges.append(dict(candidate_cell=ci,native_rows=source_rows,column=cell['col'],
                           source_pixel_box=local['pixel_box'],row_anchors=local['row_anchors'],
                           column_anchors=local['column_anchors'],edges=local['edges']))
    rec.update(merges=merges,explained_deleted_boundaries=sorted(deleted),
               actual_row_reduction=old['rows']-new['rows'])
    if len(deleted)!=old['rows']-new['rows']:
        return dict(rec,reason='unexplained_row_reduction')
    return dict(rec,accepted=True,reason='unique_source_closed_cell_merges_explain_row_reduction')


def choose(image,before,after,index):
    a,b=signature(before['blocks'][index]['content']),signature(after['blocks'][index]['content'])
    if a is None or b is None:
        return dict(accepted=False,reason='invalid_topology')
    record=dict(accepted=False,before=a,after=b,
                numeric_tokens_preserved=a['numeric_tokens']==b['numeric_tokens'])
    if not record['numeric_tokens_preserved']:
        return dict(record,reason='numerical_token_change_unconfirmed')
    if b['nonempty_row_starts']>=a['nonempty_row_starts']:
        return dict(record,accepted=True,reason='numbers_and_nonempty_row_count_retained')
    evidence=source_merge(image,before,after,index)
    return dict(record,accepted=evidence['accepted'],reason=evidence['reason'],source_merge=evidence)
