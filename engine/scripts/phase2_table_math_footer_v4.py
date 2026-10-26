"""Separate source-isolated full-width mathematical table notes, without inference."""
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
def inline_parts(text):
    """Consume only complete inline math units; preserve inner text exactly."""
    parts, position = [], 0
    while position < len(text):
        if text[position].isspace():
            position += 1
            continue
        if text.startswith('\\(',position):
            end = text.find('\\)',position+2)
            if end < 0 or '\\(' in text[position+2:end]:
                return None
            parts.append(text[position+2:end])
            position = end+2
        elif text[position] == '$' and not text.startswith('$$',position):
            end = position+1
            while end < len(text):
                if text[end] == '$':
                    preceding = 0
                    j = end-1
                    while j > position and text[j] == '\\':
                        preceding += 1
                        j -= 1
                    if preceding % 2 == 0:
                        break
                end += 1
            if end == len(text):
                return None
            parts.append(text[position+1:end])
            position = end+1
        else:
            return None
    return parts


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
    try:
        tree = html.fromstring(content)
        if tree.tag != 'table' or tree.xpath('.//table'):
            return None
        rows = tree.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')
        if len(rows) < 3:
            return None
        cells = rows[-1].xpath('./td|./th')
        if len(cells) != 1 or len(cells[0]) or int(cells[0].get('colspan','1')) < 2:
            return None
        width = int(cells[0].get('colspan'))
        if max(sum(int(c.get('colspan','1')) for c in r.xpath('./td|./th')) for r in rows[:-1]) != width:
            return None
        for i,row in enumerate(rows[:-1]):
            if any(i+int(c.get('rowspan','1')) > len(rows)-1 for c in row.xpath('./td|./th')):
                return None
        text = ''.join(cells[0].itertext())
        parts = inline_parts(text)
        if parts is None or not 1 <= len(parts) <= 8:
            return None
        for p in parts:
            if not re.search(r'=|<|>|\\(?:leq|geq|equiv|approx)\b',p) or '\\begin' in p or '\\\\' in p:
                return None
            depth = 0
            for token in re.findall(r'\\.|[{}]',p):
                depth += (token == '{')-(token == '}')
                if depth < 0:
                    return None
            if depth:
                return None
        spans = list(re.finditer(r'<tr\b[^>]*>.*?</tr\s*>',content,re.S|re.I))
        if len(spans) != len(rows):
            return None
        last = spans[-1]
        parsed = html.fromstring(last[0])
        if html.tostring(parsed) != html.tostring(rows[-1]):
            return None
        return dict(parts=parts, span=[last.start(),last.end()], columns=width)
    except (ValueError,TypeError,html.etree.ParserError):
        return None


def geometry(image, blocks, index, count):
    block = blocks[index]
    if block.get('angle',0) != 0:
        return None, 'rotation'
    w,h = image.size
    rect = [round(v*s) for v,s in zip(block['bbox'],[w,h,w,h])]
    x0,y0,x1,y1 = rect
    if x1-x0 < 40 or y1-y0 < 30:
        return None, 'too_small'
    gray = np.array(image.convert('L').crop(rect))
    ink = (gray < 180).astype('uint8')
    ch,cw = ink.shape
    horizontal = cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(12,round(cw*.5))),np.uint8))
    rules = groups(np.where(horizontal.sum(1) >= cw*.65)[0])
    if len(rules) < 3:
        return None, 'no_stable_horizontal_grid'
    separator,bottom = rules[-2:]
    top,stop = separator[1],bottom[0]
    if ch-bottom[1] > max(3,ch*.05) or stop-top < 8:
        return None, 'footer_not_at_table_end'
    prev = rules[-3][1]
    above = ink[prev:separator[0],:]
    if above.shape[0] < 5:
        return None, 'no_body_grid'
    columns = groups(np.where(above.sum(0) >= above.shape[0]*.75)[0])
    internal = [(a,b) for a,b in columns if a>cw*.05 and b<cw*.95]
    if len(internal) < 2:
        return None, 'no_internal_column_termination'
    below = ink[top:stop,:]
    for a,b in internal:
        if np.max(below[:,max(0,a-1):min(cw,b+1)].sum(0)) >= below.shape[0]*.75:
            return None, 'column_continues_into_footer'
    bands = groups(np.where(below.sum(1) > 0)[0])
    if len(bands) != count:
        return None, 'source_baselines_do_not_match_complete_math_segments'
    boxes = []
    for a,b in bands:
        xs = np.where(below[a:b,:].sum(0)>0)[0]
        if len(xs) < 4 or b-a < 3:
            return None, 'incomplete_glyph_band'
        mask = below[a:b, xs[0]:xs[-1]+1]
        n,_,stats,_ = cv2.connectedComponentsWithStats(mask)
        if sum(stats[i,cv2.CC_STAT_AREA] >= 2 for i in range(1,n)) < 4:
            return None, 'insufficient_formula_glyphs'
        box = [x0+int(xs[0]), y0+top+a, x0+int(xs[-1])+1, y0+top+b]
        for j,other in enumerate(blocks):
            if j == index or not other.get('content'):
                continue
            ob = [v*s for v,s in zip(other['bbox'],[w,h,w,h])]
            if min(ob[2],box[2])>max(ob[0],box[0]) and min(ob[3],box[3])>max(ob[1],box[1]):
                return None, 'foreign_content_owner'
        boxes.append(box)
    return dict(table_bottom=(y0+separator[1])/h,
                boxes=boxes, bbox=[[v/(w if k%2==0 else h) for k,v in enumerate(box)] for box in boxes],
                rules=rules, internal_columns=internal), 'complete_math_notes_below_terminated_column_grid'


def transform(raw, md, image):
    result = copy.deepcopy(raw)
    blocks,edits,audit = [],[],[]
    for i,b in enumerate(raw['blocks']):
        parsed = lexical(b.get('content') or '') if b['type']=='table' else None
        if not parsed:
            blocks.append(copy.deepcopy(b))
            continue
        geom,why = geometry(image,raw['blocks'],i,len(parsed['parts']))
        unique = md.count(b['content']) == 1
        audit.append(dict(owner=i,reason=why,geometry=geom,unique_md=unique))
        if geom is None or not unique:
            blocks.append(copy.deepcopy(b))
            continue
        start,end = parsed['span']
        table = b['content'][:start]+b['content'][end:]
        displays = ['\\[\n'+p.strip()+'\n\\]' for p in parsed['parts']]
        original_table = html.fromstring(b['content'])
        oldrows = original_table.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')
        oldrows[-1].getparent().remove(oldrows[-1])
        assert html.tostring(original_table) == html.tostring(html.fromstring(table))
        new = copy.deepcopy(b)
        new['content'] = table
        new['bbox'][3] = geom['table_bottom']
        blocks.append(new)
        for content,bbox in zip(displays,geom['bbox']):
            blocks.append(dict(type='equation',bbox=bbox,angle=0,content=content,
                               source_table_parent_index=i,source_relation='full_width_math_footer_note'))
        md = md.replace(b['content'], table+'\n\n'+'\n\n'.join(displays),1)
        edits.append(dict(owner=i,parts=parsed['parts'],source_geometry=geom,character_recovery=0))
    result['blocks'] = blocks
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
        if any(b['type']=='table' and lexical(b.get('content')or'') for b in raw['blocks']):
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
