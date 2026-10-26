"""Input-only mixed orientation diagnostic gate. No GT, source-name rules or history."""
TEXT_TYPES={'text','title','header','footer','aside_text','image_caption','table_caption','table_footnote'}
def risk(b,size):
 if b.get('type') not in TEXT_TYPES or not isinstance(b.get('content'),str) or not b['content'].strip():return False,'non_text'
 if b.get('angle') not in (90,270):return False,'not_quarter_turn'
 box=b.get('bbox');w,h=size
 if not isinstance(box,list) or len(box)!=4 or not all(isinstance(x,(int,float)) and 0<=x<=1 for x in box):return False,'invalid_bbox'
 x,y,X,Y=box
 if X<=x or Y<=y:return False,'invalid_bbox'
 if (X-x)*w<1.5*(Y-y)*h:return False,'source_not_horizontal'
 return True,'quarter_turn_horizontal_owner'
