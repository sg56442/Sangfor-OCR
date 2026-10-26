"""Runtime-only primitives: no GT, page identity, source labels or answer lookup."""
from lxml import html
import numpy as np

def grids(markup):
    try: root=html.fromstring('<div>'+markup+'</div>')
    except Exception: return []
    out=[]
    for table in root.xpath('.//table'):
        rows=[r for r in table.xpath('.//tr') if r.xpath('ancestor::table')[-1] is table]
        occupied={}; cells=[]; conflicts=[]
        for r,row in enumerate(rows):
            col=0
            for cell in row.xpath('./td|./th'):
                while (r,col) in occupied: col+=1
                try: rs=max(1,int(cell.get('rowspan',1))); cs=max(1,int(cell.get('colspan',1)))
                except ValueError: rs=cs=1; conflicts.append('invalid_span')
                if rs>512 or cs>512: conflicts.append('excessive_span');continue
                idx=len(cells)
                cells.append(dict(row=r,col=col,rowspan=rs,colspan=cs,text=''.join(cell.itertext())))
                for y in range(r,r+rs):
                    for x in range(col,col+cs):
                        if (y,x) in occupied: conflicts.append([y,x])
                        occupied[y,x]=idx
                col+=cs
        width=max((x+1 for y,x in occupied),default=0)
        out.append(dict(rows=len(rows),width=width,cells=cells,conflicts=conflicts,
                        holes=sum((y,x) not in occupied for y in range(len(rows)) for x in range(width)),
                        span_beyond_rows=any(y>=len(rows) for y,x in occupied)))
    return out

def runs(mask):
    a=np.r_[False,mask,False].astype(int);return list(zip(np.where(np.diff(a)==1)[0].tolist(),np.where(np.diff(a)==-1)[0].tolist()))

def image_signals(crop):
    a=np.asarray(crop.convert('L')); ink=a<180
    # Central area avoids page border; horizontal whitespace is a proposal only.
    density=ink[:,max(0,a.shape[1]//50):max(1,a.shape[1]-a.shape[1]//50)].mean(axis=1)
    bands=runs(density>.015)
    gaps=[(s,e) for s,e in runs(density<.006) if s>.12*len(a) and e<.88*len(a)]
    return dict(size=list(crop.size),ink_bands=bands,whitespace_bands=gaps,
                line_rows=np.where(density>.65)[0].tolist())

def candidates(image,blocks):
    """At most one split per native table; merge adjacent aligned blocks. No acceptance implied."""
    w,h=image.size; result=[]; table_ids=[i for i,b in enumerate(blocks) if b['type']=='table']
    for i in table_ids:
        b=blocks[i];x0,y0,x1,y1=b['bbox'];box=[round(x0*w),round(y0*h),round(x1*w),round(y1*h)]
        crop=image.crop(box); sig=image_signals(crop); grid=grids(b.get('content',''))
        result.append(dict(kind='native_table',indices=[i],bbox=b['bbox'],signals=sig,grid=grid))
        gaps=sig['whitespace_bands']
        if gaps:
            s,e=max(gaps,key=lambda q:q[1]-q[0]); charbands=[b-a for a,b in sig['ink_bands'] if 2<=b-a<=50]
            typical=float(np.median(charbands)) if charbands else 10.
            if e-s>=max(6,typical*.65):
                cut=(box[1]+(s+e)/2)/h
                result.append(dict(kind='split_whitespace',indices=[i],bbox=b['bbox'],parts=[[x0,y0,x1,cut],[x0,cut,x1,y1]],signal=dict(gap_px=e-s,band_height_proxy=typical),accept=False))
        # Whole-table context is safe fallback for B/C when cell coordinates are unknown.
        if grid and (any(c['rowspan']>1 for c in grid[0]['cells']) or len(sig['ink_bands'])>grid[0]['rows']*1.5):
            pad=4
            result.append(dict(kind='span_context',indices=[i],bbox=[max(0,x0-pad/w),max(0,y0-pad/h),min(1,x1+pad/w),min(1,y1+pad/h)],signal={'reason':'span_or_multiple_ink_bands'},accept=False))
    ordered=sorted(table_ids,key=lambda i:blocks[i]['bbox'][1])
    for i,j in zip(ordered,ordered[1:]):
        a,b=blocks[i]['bbox'],blocks[j]['bbox'];gap=b[1]-a[3]
        align=max(abs(a[0]-b[0]),abs(a[2]-b[2]))
        if -.005<=gap<=.045 and align<=.04:
            result.append(dict(kind='merge_adjacent',indices=[i,j],bbox=[min(a[0],b[0]),a[1],max(a[2],b[2]),max(a[3],b[3])],signal=dict(gap=gap,edge_misalignment=align),accept=False))
    return result

def math_rowspan_candidate(markup):
    """Proposal only: split parallel math groups into rows, spanning unsplit labels.

    Never select automatically: multiline statistical entries can be a single cell.
    Reject rows crossed by existing rowspans to avoid crossing boundaries.
    """
    import re,copy
    root=html.fromstring('<div>'+markup+'</div>');changed=0
    for table in root.xpath('.//table'):
        rows=[r for r in table.xpath('.//tr') if r.xpath('ancestor::table')[-1] is table]
        row_grid=grids(html.tostring(table,encoding='unicode'))[0]
        for row_index,row in enumerate(rows):
            if any(c['rowspan']>1 and c['row']<=row_index<c['row']+c['rowspan'] for c in row_grid['cells']):continue
            cells=row.xpath('./td|./th');texts=[''.join(c.itertext()) for c in cells]
            groups=[re.findall(r'\\\(.*?\\\)',t,re.S) for t in texts]
            counts=[len(g) if ''.join(g).replace(' ','')==t.replace(' ','') else 0 for g,t in zip(groups,texts)]
            n=max(counts,default=0)
            if n not in (2,3) or sum(c==n for c in counts)<max(2,len(cells)*.6):continue
            newrows=[html.Element('tr') for _ in range(n)]
            for cell,parts,count in zip(cells,groups,counts):
                if count==n:
                    for nr,part in zip(newrows,parts):
                        c=copy.deepcopy(cell);c.clear();c.tag=cell.tag
                        if cell.get('colspan'):c.set('colspan',cell.get('colspan'))
                        c.text=part;nr.append(c)
                else:
                    c=copy.deepcopy(cell);c.set('rowspan',str(n));newrows[0].append(c)
            parent=row.getparent();pos=parent.index(row);parent.remove(row)
            for offset,nr in enumerate(newrows):parent.insert(pos+offset,nr)
            changed+=1
    return ''.join(html.tostring(c,encoding='unicode') for c in root),changed
