"""A printed closed data band with one value per column can contain a wrapped label."""
import re
import cv2
import numpy as np
from bs4 import BeautifulSoup
from PIL import Image
cv2.setNumThreads(2)

def groups(mask):
    xs=np.flatnonzero(mask);out=[]
    for x in xs:
        x=int(x)
        if not out or x-out[-1][-1]>2:out.append([x])
        else:out[-1].append(x)
    return [(a[0],a[-1]+1) for a in out]

def parse(text):
    if not isinstance(text,str) or text.lower().count('<table')!=1:return None
    table=BeautifulSoup(text,'html.parser').find('table')
    if table is None or table.find('table') is not None:return None
    rows=table.find_all('tr',recursive=False)
    if len(rows)!=3:return None
    cells=[r.find_all(['td','th'],recursive=False) for r in rows]
    n=len(cells[0])
    if not 3<=n<=12 or any(len(r)!=n for r in cells):return None
    try:
        if any(int(c.get('rowspan',1))!=1 or int(c.get('colspan',1))!=1 for row in cells for c in row):return None
    except (TypeError,ValueError):return None
    values=[[c.get_text().strip() for c in row] for row in cells]
    if not all(values[0]) or not values[1][0] or any(values[1][1:]) or not all(values[2]):return None
    # Each data field has a single scalar-looking value; this is not a multi-record text list.
    numeric=lambda x:bool(re.fullmatch(r'[+−–\-()\d.,%\s]+',x)) and any(z.isdigit() for z in x)
    if not all(numeric(v) for v in values[2][1:]):return None
    return dict(columns=n,values=values)

def geometry(im,block,n,threshold):
    w,h=im.size;bb=block['bbox'];box=[max(0,round(bb[0]*w)-4),max(0,round(bb[1]*h)-4),min(w,round(bb[2]*w)+4),min(h,round(bb[3]*h)+4)]
    a=np.asarray(im.convert('L').crop(box));hh,ww=a.shape
    if ww<100 or hh<40:return None,'small_source'
    ink=(a<threshold).astype(np.uint8)
    horizontal=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(30,int(.6*ww))),np.uint8))
    hs=groups(horizontal.sum(axis=1)>.85*ww)
    if len(hs)!=2:return None,'not_one_bounded_data_band'
    top,bottom=hs[0][1]+2,hs[1][0]-2
    if top<.12*hh or bottom-top<.3*hh:return None,'insufficient_header_or_data_extent'
    body=ink[top:bottom];bh=body.shape[0]
    vertical=cv2.morphologyEx(body,cv2.MORPH_OPEN,np.ones((max(10,int(.8*bh)),1),np.uint8))
    vs=groups(vertical.sum(axis=0)>.85*bh)
    vs=[(l,r) for l,r in vs if l>3 and r<ww-3]
    if len(vs)!=n-1:return None,'column_rule_mismatch'
    edges=[0]+[round((l+r)/2) for l,r in vs]+[ww]
    if min(b-a for a,b in zip(edges,edges[1:]))<12:return None,'narrow_column'
    bands=[]
    for left,right in zip(edges,edges[1:]):
        region=body[:,left+3:right-3]
        count,labels,stats,centroids=cv2.connectedComponentsWithStats(region,8)
        clean=np.zeros_like(region)
        for index,(x,y,cw,ch,area) in enumerate(stats[1:],1):
            if area>=3 and 2<=ch<.7*bh and cw<.8*region.shape[1]:clean[labels==index]=1
        bs=groups(clean.sum(axis=1)>=2)
        bs=[(a,b) for a,b in bs if b-a>=3]
        bands.append(bs)
    if len(bands[0])<2 or any(len(bs)!=1 for bs in bands[1:]):return None,'not_wrapped_label_single_value_each'
    last=bands[0][-1];height=max(b-a for bs in bands for a,b in bs)
    if any(abs(bs[0][1]-last[1])>.6*height for bs in bands[1:]):return None,'data_baselines_disagree'
    if any(a<bands[0][0][0]-.5*height for bs in bands[1:] for a,b in bs):return None,'values_precede_label'
    return dict(box=box,data_top=top,data_bottom=bottom,xedges=edges,bands=bands,horizontal=hs,vertical=vs),None

def candidate(im,block):
    text=block.get('content');p=parse(text)
    if p is None:return None,'not_three_row_header_prefix_single_record'
    if block.get('angle',0):return None,'rotation'
    bb=block.get('bbox')
    if not isinstance(bb,(list,tuple)) or len(bb)!=4 or not all(isinstance(v,(int,float)) and np.isfinite(v) for v in bb) or not (0<=bb[0]<bb[2]<=1 and 0<=bb[1]<bb[3]<=1):return None,'invalid_bbox'
    low,reason=geometry(im,block,p['columns'],170)
    if low is None:return None,reason
    high,reason=geometry(im,block,p['columns'],210)
    if high is None:return None,reason
    if any(abs(a-b)>3 for a,b in zip(low['xedges'],high['xedges'])) or any(abs(low[k]-high[k])>3 for k in ['data_top','data_bottom']):return None,'unstable_source_rules'
    rows=list(re.finditer(r'<tr\b[^>]*>.*?</tr\s*>',text,re.I|re.S))
    if len(rows)!=3:return None,'ambiguous_markup_rows'
    cells=[list(re.finditer(r'<t[dh]\b[^>]*>(.*?)</t[dh]\s*>',r.group(),re.I|re.S)) for r in rows]
    if any(len(c)!=p['columns'] for c in cells):return None,'ambiguous_markup_cells'
    a,b=cells[1][0],cells[2][0];last=rows[2].group();joined=a.group(1)+'<br/>'+b.group(1)
    last=last[:b.start(1)]+joined+last[b.end(1):]
    new=text[:rows[1].start()]+text[rows[1].end():rows[2].start()]+last+text[rows[2].end():]
    compact=lambda x:re.sub(r'\s+','',BeautifulSoup(x,'html.parser').get_text())
    assert compact(new)==compact(text)
    return dict(content=new,columns=p['columns'],geometry=high,low_threshold_geometry=low,
        reason='complete_printed_data_band_one_numeric_value_per_column_wrapped_label',HTTP=0),'accepted'
