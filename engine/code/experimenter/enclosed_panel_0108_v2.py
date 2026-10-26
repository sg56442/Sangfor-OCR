"""Original-pixel closed light panels with diverse multi-line glyphs. No OCR/GT."""
import cv2,numpy as np,hashlib

def panels(image,blocks):
 a=np.asarray(image.convert('RGB'));gray=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY);h,w=gray.shape
 # White connected interiors are computed before any owner mask.
 n,labels,stats,_=cv2.connectedComponentsWithStats((gray>=210).astype('uint8'),8)
 out=[]
 for component_id,(x,y,bw,bh,area) in enumerate(stats[1:],1):
  x,y,bw,bh,area=map(int,[x,y,bw,bh,area])
  if min(bw,bh)<40 or not(.25<bw/bh<4) or area/(bw*bh)<.55 or x<=2 or y<=2 or x+bw>=w-2 or y+bh>=h-2:continue
  if bw*bh>.15*w*h:continue
  rect=[x,y,x+bw,y+bh];ring=np.concatenate([gray[y-2:y,x:x+bw].ravel(),gray[y+bh:y+bh+2,x:x+bw].ravel(),gray[y:y+bh,x-2:x].ravel(),gray[y:y+bh,x+bw:x+bw+2].ravel()]);border=float(np.mean(ring<185))
  if border<.5:continue
  component=(labels[y:y+bh,x:x+bw]==component_id).astype('uint8')
  contours,_=cv2.findContours(component,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  interior=np.zeros_like(component);cv2.drawContours(interior,contours,-1,1,cv2.FILLED)
  ink=((gray[y:y+bh,x:x+bw]<185)&(interior>0)).astype('uint8');nn,ll,ss,_=cv2.connectedComponentsWithStats(ink,8);glyph=[q for q in ss[1:] if q[4]>=3]
  if len(glyph)<20:continue
  heights=np.array([q[3] for q in glyph]);mh=float(np.median(heights));maxh=int(max(heights))
  if mh<4 or maxh>max(4*mh,.30*bh):continue
  if any(q[0]<=0 or q[1]<=0 or q[0]+q[2]>=bw or q[1]+q[3]>=bh for q in glyph):continue
  # Reject long line topology instead of treating all coloured regions as grids.
  hor=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(8,int(.65*bw))),np.uint8));ver=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(8,int(.65*bh)),1),np.uint8))
  if hor.any() or ver.any():continue
  ys=np.where(ink.sum(axis=1)>=3)[0];bands=[]
  for yy in ys:
   if not bands or yy>bands[-1][-1]+1:bands.append([int(yy)])
   else:bands[-1].append(int(yy))
  bands=[z for z in bands if len(z)>=max(3,.4*mh)]
  if len(bands)<3:continue
  shapes=[]
  for gx,gy,gw,gh,ga in glyph:
   p=cv2.resize(ink[gy:gy+gh,gx:gx+gw],(8,8),interpolation=cv2.INTER_NEAREST);shapes.append(np.packbits(p).tobytes().hex())
  diverse=len(set(shapes))/len(shapes)
  if diverse<.25:continue
  owners=[];covered=[]
  for i,b in enumerate(blocks):
   q=b.get('bbox')
   if not q:continue
   xx0,yy0,xx1,yy1=[v*(w if j%2==0 else h) for j,v in enumerate(q)];intersection=max(0,min(x+bw,xx1)-max(x,xx0))*max(0,min(y+bh,yy1)-max(y,yy0))
   if intersection/(bw*bh)>=.95 and b['type']=='image':owners.append(i)
   if intersection/(bw*bh)>.15 and b.get('content') and b['type'] not in ['image','image_block']:covered.append(i)
  if not owners and not covered:continue
  if len(owners)>1:continue
  out.append(dict(rect=rect,owner=owners[0] if owners else None,covered=covered,normal=bool(covered),glyph_components=len(glyph),median_glyph_height=mh,shape_diversity=diverse,line_bands=[[z[0],z[-1]+1] for z in bands],dark_border_fraction=border,affine=[1,0,x,0,1,y],relation_policy='retain original image; child transcription remains attributed to complete enclosing panel; no connected graph/grid topology accepted'))
 return sorted(out,key=lambda r:(r['rect'][1],r['rect'][0]))
