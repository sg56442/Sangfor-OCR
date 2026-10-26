"""Use crop-local line geometry to pair short text rows; keep every child exactly once."""
def pair_rows(blocks):
 if len(blocks)<8 or any(b['type']!='text' or b.get('angle') not in (None,0) or not b.get('content') or '\n' in b['content'].strip() or len(b['content'])>120 or b['bbox'][3]-b['bbox'][1]>.08 for b in blocks):return None,{'reason':'not_short_line_layout'}
 xs=sorted((b['bbox'][0]+b['bbox'][2])/2 for b in blocks);gap,i=max((xs[j+1]-xs[j],j) for j in range(len(xs)-1))
 if gap<.15:return None,{'reason':'no_two_spatial_columns'}
 cut=(xs[i]+xs[i+1])/2;left=[j for j,b in enumerate(blocks) if (b['bbox'][0]+b['bbox'][2])/2<cut];right=[j for j in range(len(blocks)) if j not in left]
 if len(left)!=len(right) or len(left)<4:return None,{'reason':'unequal_spatial_rows'}
 left.sort(key=lambda j:blocks[j]['bbox'][1]);right.sort(key=lambda j:blocks[j]['bbox'][1]);pairs=[]
 for a,b in zip(left,right):
  x,y=blocks[a]['bbox'],blocks[b]['bbox'];overlap=min(x[3],y[3])-max(x[1],y[1])
  if overlap/max(1e-9,min(x[3]-x[1],y[3]-y[1]))<.5 or x[2]>y[0]+.01:return None,{'reason':'row_overlap_or_column_conflict'}
  pairs.append([a,b])
 return '\n'.join(blocks[a]['content']+' '+blocks[b]['content'] for a,b in pairs),dict(reason='source_coordinate_bilateral_rows',pairs=pairs,all_children_once=sorted(sum(pairs,[]))==list(range(len(blocks))))
