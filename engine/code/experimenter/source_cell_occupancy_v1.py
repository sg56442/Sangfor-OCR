"""Measured source boundary bands for occupancy only. Never changes inference pixels."""
import numpy as np,cv2

def cell_occupancy(image,box,return_masks=False):
 x0,y0,x1,y1=box;pad=3;w,h=image.size
 rect=[max(0,x0-pad),max(0,y0-pad),min(w,x1+pad+1),min(h,y1+pad+1)]
 gray=np.asarray(image.convert('L').crop(rect));ink=gray<185;light=gray<220
 xx=[x0-rect[0],x1-rect[0]];yy=[y0-rect[1],y1-rect[1]];mask=np.zeros_like(ink);bands=[]
 for axis,centers,lo,hi in [(0,yy,xx[0],xx[1]),(1,xx,yy[0],yy[1])]:
  a=light if axis==0 else light.T
  length=hi-lo;trim=max(2,length//10);profile=a[:,lo+trim:hi-trim].mean(1)
  for center in centers:
   radius=max(3,min(12,(yy[1]-yy[0] if axis==0 else xx[1]-xx[0])//8))
   candidates=[i for i in range(max(0,center-radius),min(len(profile),center+radius+1)) if profile[i]>=.85]
   if not candidates:return dict(eligible=False,reason='boundary_band_not_supported')
   seed=min(candidates,key=lambda i:abs(i-center));l=r=seed
   while l>0 and profile[l-1]>=.85:l-=1
   while r+1<len(profile) and profile[r+1]>=.85:r+=1
   if not l-2<=center<=r+2 or r-l+1>max(3,(yy[1]-yy[0] if axis==0 else xx[1]-xx[0])*.15):return dict(eligible=False,reason='boundary_band_ambiguous')
   # One-pixel raster/antialias uncertainty around measured continuous rule.
   l=max(0,l-1);r=min(len(profile)-1,r+1)
   if axis==0:mask[l:r+1,:]=True
   else:mask[:,l:r+1]=True
   bands.append(dict(axis=axis,center=center,band=[l,r],support=float(profile[seed])))
 interior=np.zeros_like(ink);interior[yy[0]+1:yy[1],xx[0]+1:xx[1]]=True
 remaining=ink & interior & ~mask
 n,lab,stats,_=cv2.connectedComponentsWithStats(remaining.astype('uint8'),8)
 significant=np.zeros_like(ink);components=[]
 for i,st in enumerate(stats[1:],1):
  if st[4]>=6:significant[lab==i]=True;components.append(list(map(int,st)))
 contact=bool((cv2.dilate(significant.astype('uint8'),np.ones((3,3),np.uint8)).astype(bool)&mask).any())
 result=dict(eligible=not contact,reason='glyph_boundary_contact_uncertain' if contact else 'measured_boundary_occupancy',occupied=bool(components),remaining_ink=int(remaining.sum()),significant_ink=int(significant.sum()),boundary_ink=int((ink&interior&mask).sum()),bands=bands,components=components,rect=rect,input_pixels_unchanged=True)
 if return_masks:result['_mask']=mask;result['_remaining']=remaining
 return result
