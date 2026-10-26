import numpy as np

def boundary_support(image,x_intervals,mapped):
 """Reject artificial cell edges across source colspan headers.
 Each independent source-column output introduces an edge at each x boundary.
 Check actual ink continuity for every mapped y-band, not wholeheight average.
 """
 a=np.asarray(image.convert('L'))<160;h,w=a.shape;ys=sorted(set(y for c in mapped for y in c['source_y_interval']));fail=[]
 for x in [b for _,b in x_intervals[:-1]]:
  for lo,hi in zip(ys,ys[1:]):
   if hi-lo<6:continue
   margin=min(3,(hi-lo)//4);strip=a[lo+margin:hi-margin,max(0,x-4):min(w,x+5)]
   fraction=float(strip.any(1).mean()) if strip.size else 0
   if fraction<.5:fail.append(dict(x=x,y_interval=[lo,hi],ink_support=fraction))
 return not fail,fail
