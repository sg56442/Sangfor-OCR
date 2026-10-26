"""Separate independently printed repeated text lines without removing any occurrence."""
import re,cv2,numpy as np
cv2.setNumThreads(2)
def parse(block):
    s=block.get('content')
    if block.get('type')!='text' or block.get('angle',0) or not isinstance(s,str):return None
    lines=s.splitlines()
    if len(lines)<2 or any(not x.strip() for x in lines) or len({x.strip() for x in lines})!=1:return None
    if not re.search(r'[A-Za-z\u4e00-\u9fff]',lines[0]) or any(x in s for x in ['\\','$','<','>']):return None
    return lines

def bands(mask):
    ys=np.flatnonzero(mask.sum(axis=1)>max(2,mask.shape[1]*.02));groups=[]
    for y in ys:
        if not groups or y-groups[-1][-1]>2:groups.append([int(y)])
        else:groups[-1].append(int(y))
    return [(g[0],g[-1]+1) for g in groups if g[-1]-g[0]>=3]

def candidate(im,block):
    lines=parse(block)
    if lines is None:return None,'not_repeated_plain_text_lines'
    w,h=im.size;bb=block.get('bbox')
    if not bb or len(bb)!=4 or not (0<=bb[0]<bb[2]<=1 and 0<=bb[1]<bb[3]<=1):return None,'invalid_bbox'
    box=[round(v*s) for v,s in zip(bb,[w,h,w,h])];a=np.asarray(im.convert('L').crop(box))
    if min(a.shape)<8 or a.max()-int(a.min())<30:return None,'low_source_contrast'
    t,_=cv2.threshold(a,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU);dark=(a<t).mean()<.5;measurements=[]
    for threshold in [max(1,t-10),min(254,t+10)]:
        mask=a<threshold if dark else a>threshold
        if not .01<mask.mean()<.45:return None,'foreground_ambiguous'
        bs=bands(mask)
        if len(bs)!=len(lines):return None,'source_line_count_mismatch'
        heights=[b-a for a,b in bs]
        if max(heights)>1.4*min(heights):return None,'source_line_height_mismatch'
        if any(b[0]-a[1]<max(heights) for a,b in zip(bs,bs[1:])):return None,'not_independent_spaced_lines'
        measurements.append(bs)
    if any(abs(a-b)>2 for lo,hi in zip(*measurements) for a,b in zip(lo,hi)):return None,'unstable_source_lines'
    new=[]
    for line,(top,bottom) in zip(lines,measurements[1]):new.append(dict(block,content=line,bbox=[bb[0],(box[1]+top)/h,bb[2],(box[1]+bottom)/h]))
    assert re.sub(r'\s+','',block['content'])==re.sub(r'\s+','',''.join(x['content'] for x in new))
    return dict(blocks=new,markdown='\n\n'.join(lines),source_box=box,source_bands=measurements,foreground_dark=bool(dark)), 'separate_source_spaced_identical_lines'
