"""Conservative source-band record grouping; no GT, vocabulary, page identity or inference."""
import re,math,cv2,numpy as np
from bs4 import BeautifulSoup
cv2.setNumThreads(2)
def bands(a):
 z=np.flatnonzero(np.diff(np.r_[False,a,False].astype(int)));return [(int(s),int(e)) for s,e in zip(z[::2],z[1::2])]
def transform(im,b):
 box=b.get('bbox')
 if not isinstance(box,(list,tuple)) or len(box)!=4 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in box) or not (0<=box[0]<box[2]<=1 and 0<=box[1]<box[3]<=1):return None,'invalid_bbox'
 if b.get('angle',0) not in [0,90,180,270]:return None,'invalid_angle'
 s=b.get('content')
 if b.get('type')!='table' or not isinstance(s,str):return None,'not_table'
 soup=BeautifulSoup(s,'html.parser');trs=soup.find_all('tr');cells=[r.find_all(['td','th'],recursive=False) for r in trs]
 if len(cells)<3 or len(soup.find_all('table'))!=1:return None,'no_prefix'
 n=len(cells[0])
 if n<3 or any(len(r)!=n for r in cells) or any(c.attrs for row in cells for c in row):return None,'complex_grid'
 if not all(c.get_text(strip=True) for c in cells[0]+cells[-1]):return None,'incomplete_header_or_record'
 if not all(row[0].get_text(strip=True) and not any(c.get_text(strip=True) for c in row[1:]) for row in cells[1:-1]):return None,'multiple_records_or_group_headings'
 w,h=im.size;box=[round(v*z) for v,z in zip(b['bbox'],[w,h,w,h])];crop=im.convert('L').crop(box).rotate(b.get('angle',0),expand=True);a=np.array(crop);proof=[]
 for threshold in [180,210]:
  ink=(a<threshold).astype('uint8');hh,ww=ink.shape
  lines=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(20,int(.8*ww))),np.uint8));hr=bands(lines.sum(1)>.8*ww)
  if len(hr)<3:return None,'missing_complete_band_boundaries'
  top=hr[-2][1]+1;bottom=hr[-1][0]-1
  if top>=bottom or top>.5*hh:return None,'not_single_full_data_band'
  body=ink[top:bottom];gaps=[(s,e) for s,e in bands(body.sum(0)==0) if s>0 and e<ww and e-s>=ww*.008]
  if len(gaps)<n-1:return None,'insufficient_source_gutters'
  best=sorted(sorted(gaps,key=lambda x:x[1]-x[0],reverse=True)[:n-1]);cuts=[0]+[(s+e)//2 for s,e in best]+[ww];stats=[]
  for left,right in zip(cuts,cuts[1:]):
   ys,xs=np.where(body[:,left:right]>0)
   if not len(ys):return None,'empty_source_column'
   stats.append(dict(y0=int(ys.min()),y1=int(ys.max()+1),center=float((ys.min()+ys.max()+1)/2),lines=len(bands(body[:,left:right].sum(1)>0))))
  first=stats[0];height=first['y1']-first['y0']
  if first['lines']<4:return None,'not_multiline_stub'
  if any((x['y1']-x['y0'])>.65*height or abs(x['center']-first['center'])>.16*height for x in stats[1:]):return None,'right_columns_not_centered_single_record'
  proof.append(dict(threshold=threshold,band=[top,bottom],cuts=cuts,stats=stats))
 if len(proof[0]['cuts'])!=len(proof[1]['cuts']) or any(abs(x-y)>3 for x,y in zip(proof[0]['cuts'],proof[1]['cuts'])):return None,'unstable_columns'
 old=[r[0].decode_contents() for r in cells[1:]];dest=cells[-1][0];dest.clear();frag=BeautifulSoup('<br/>'.join(old),'html.parser')
 for child in list(frag.contents):dest.append(child)
 for row in trs[1:-1]:row.decompose()
 return dict(html=str(soup.find('table')),proof=proof,box=box),'complete_band_centered_values'
