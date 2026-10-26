"""Runtime image evidence for stacked fraction vs inline slash; no page/GT inputs."""
import cv2,numpy as np

def fraction_bar(crop):
 a=(np.asarray(crop.convert('L'))<150).astype('uint8');h,w=a.shape;a[:3]=0;a[-3:]=0;a[:,:3]=0;a[:,-3:]=0
 n,labels,stats,centroids=cv2.connectedComponentsWithStats(a,8);components=[list(map(int,s)) for s in stats[1:] if s[4]>=3];bars=[]
 for x,y,bw,bh,area in components:
  if not(bw>=5 and bw>=3*bh and .2*h<y<.8*h and bw<.85*w and area>=.5*bw*bh):continue
  above=[];below=[]
  for xx,yy,ww,hh,aa in components:
   if max(x,xx)>=min(x+bw,xx+ww) or hh<=bh:continue
   if yy+hh<=y and y-(yy+hh)<.4*h:above.append([xx,yy,ww,hh])
   if yy>=y+bh and yy-y-bh<.4*h:below.append([xx,yy,ww,hh])
  if above and below:bars.append(dict(x=x,y=y,width=bw,height=bh,above_components=above,below_components=below))
 return dict(has_fraction_bar=bool(bars),bars=bars,criterion='independent horizontal connected component with separate glyph components above and below')
