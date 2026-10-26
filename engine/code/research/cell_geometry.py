"""Conservative ruled-grid image coordinates; rejects uncertain or mismatching grids."""
import cv2,numpy as np
from table_mechanisms import runs

def ruling_map(crop,grid):
 gray=np.array(crop.convert('L'));ink=(gray<150).astype('uint8')*255;h,w=ink.shape
 horizontal=cv2.morphologyEx(ink,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(max(12,int(w*.25)),1)))
 vertical=cv2.morphologyEx(ink,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(12,int(h*.25)))))
 xs=[(a+b-1)/2 for a,b in runs((vertical>0).mean(axis=0)>.30)];ys=[(a+b-1)/2 for a,b in runs((horizontal>0).mean(axis=1)>.30)]
 reason=[]
 if len(xs)!=grid['width']+1:reason.append('column_anchor_count')
 if len(ys)!=grid['rows']+1:reason.append('row_anchor_count')
 if not xs or not ys or xs[-1]-xs[0]<.85*w or ys[-1]-ys[0]<.85*h:reason.append('outer_border_coverage')
 cells=[]
 if not reason:
  for c in grid['cells']:
   r,col,rs,cs=c['row'],c['col'],c['rowspan'],c['colspan']
   if r+rs>=len(ys) or col+cs>=len(xs):reason.append('span_out_of_bounds');break
   bbox=[xs[col],ys[r],xs[col+cs],ys[r+rs]]
   # A predicted span must not cross a strong full-cell ruling.
   for k in range(r+1,r+rs):
    y=int(ys[k]);x0,x1=int(xs[col])+3,int(xs[col+cs])-3
    if x1>x0 and (ink[max(0,y-1):y+2,x0:x1]>0).mean()>.45:reason.append('rowspan_crosses_ruling')
   for k in range(col+1,col+cs):
    x=int(xs[k]);y0,y1=int(ys[r])+3,int(ys[r+rs])-3
    if y1>y0 and (ink[y0:y1,max(0,x-1):x+2]>0).mean()>.45:reason.append('colspan_crosses_ruling')
   cells.append(dict(row=r,col=col,rowspan=rs,colspan=cs,pixel_bbox=bbox))
 return dict(accepted=not reason,reasons=sorted(set(reason)),x_anchors=xs,y_anchors=ys,cells=cells,size=[w,h])
