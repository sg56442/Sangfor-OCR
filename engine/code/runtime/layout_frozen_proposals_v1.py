"""Frozen v2 proposal functions, independent of campaign artifact paths."""
import re
CUE=re.compile(r'\\(?:because|therefore)\b|[∵∴]|(?:^|[：:])(?:解|证明|故|因此|从而)')


def inner(text):
    text=text.strip()
    if text.startswith(r'\[') and text.endswith(r'\]'):return text[2:-2].strip()
    if text.startswith('$$') and text.endswith('$$'):return text[2:-2].strip()
    return text


def new_problem(block):
    compact=re.sub(r'\s+','',inner(block.get('content')or''))
    return bool(re.match(r'^(?:\d{1,3}[.、．]|[（(]\d{1,3}[）)])',compact))


def connected(a,b):
    aa,bb=a['bbox'],b['bbox']
    w1,w2=aa[2]-aa[0],bb[2]-bb[0]
    h1,h2=aa[3]-aa[1],bb[3]-bb[1]
    if min(w1,w2,h1,h2)<=0:return False
    overlap=min(aa[2],bb[2])-max(aa[0],bb[0])
    gap=bb[1]-aa[3]
    return bb[1]>=aa[1]-.005 and -.01<=gap<=min(.035,.75*max(h1,h2)) and overlap/min(w1,w2)>=.3


def leading_text(block):
    text=inner(block.get('content')or'').strip()
    text=re.sub(r'^\\(?:text|mathrm)\s*\{([^{}]*)\}',r'\1',text)
    text=re.sub(r'^\\\(\s*', '', text)
    return text.strip()


def section_start(block):
    text=leading_text(block)
    return new_problem(block) or bool(re.match(
        r'^(?:(?:例题?|习题|定理|引理|命题)\s*[\d一二三四五六七八九十]|(?:解|证明)\s*[：:\s]|(?:Proof|Solution)\b|[\u4e00-\u9fff]{2,12}\s*[：:])',text,re.I))


def assumption_start(block):
    return block['type']=='text' and bool(re.match(r'^(?:设|令|取|Let\b|Assume\b|Suppose\b)',leading_text(block),re.I))


def reasoning_start(block):
    text=leading_text(block)
    return bool(re.match(r'^(?:\\(?:because|therefore)\b|[∵∴]|解[：:\s]|证明[：:\s]|故|因此|从而|Proof\b|Solution\b)',text,re.I))


def proposals(blocks):
    sequences=[];current=[]
    for i,b in enumerate(blocks):
        valid=b['type'] in ['text','equation'] and bool(b.get('content')) and not b.get('angle')
        if not valid:
            if current:sequences.append(current)
            current=[];continue
        if current and (not connected(blocks[current[-1]],b) or section_start(b) or assumption_start(b)):
            sequences.append(current);current=[]
        if not current and not reasoning_start(b):continue
        current.append(i)
    if current:sequences.append(current)
    result=[]
    for ids in sequences:
        contents=[blocks[i]['content'] for i in ids]
        cues=sum(len(CUE.findall(s)) for s in contents)
        equations=sum(blocks[i]['type']=='equation' for i in ids)
        cjk=sum(len(re.findall(r'[\u4e00-\u9fff]',s)) for s in contents)
        if len(ids)<3 or equations<2 or cues<2 or cjk<2:continue
        if any(re.search(r'\\tag\b|\\label\b',s) for s in contents):continue
        boxes=[blocks[i]['bbox'] for i in ids]
        result.append({'indices':ids,'bbox':[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)],
                       'reasoning_cues':cues,'equation_blocks':equations,'native_cjk_characters':cjk,
                       'rule':'ANCHORED_REASONING_SECTION_BOUNDARIES_V2'})
    return result

