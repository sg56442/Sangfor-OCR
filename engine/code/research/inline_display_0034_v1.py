"""Input-only spaced-label plus complete mixed display proposal, no recognition."""
import re,copy,cv2,numpy as np

def text_escape(s, slash):
 # One pass: inserted escapes must never be escaped again.
 if any(ord(c)<32 for c in s):raise ValueError("control characters unsupported")
 mapping={c:slash+c for c in "$%#&_{}"}
 mapping.update({"\\":slash+"textbackslash{}", "^":slash+"textasciicircum{}", "~":slash+"textasciitilde{}"})
 return "".join(mapping.get(c,c) for c in s)

def parse(s):
 ms=list(re.finditer(r'(\\+)\((.*?)\1\)',s,re.S))
 if len(ms)<2 or any(ord(c)<32 for c in s):return None
 prefix=s[:ms[0].start()]
 if not re.fullmatch(r'\s*[A-Za-z]+(?:[ -][A-Za-z]+){1,4}\s+',prefix):return None
 prose=[];cursor=ms[0].start()
 for m in ms:
  p=s[cursor:m.start()]
  if any(c in p for c in '{}\\$'):return None
  prose.append(p);cursor=m.end()
 tail=s[cursor:]
 if any(c in tail for c in '{}\\$'):return None
 if sum(len(re.findall(r'[A-Za-z]+',p)) for p in prose+[tail])>10:return None
 if not any(re.search(r'=|<|>|\\(?:geq?|leq?|in|equiv|approx)\b',m[2]) for m in ms):return None
 if len({m[1] for m in ms})!=1:return None
 return dict(prefix=prefix,matches=ms,tail=tail,slash=ms[0][1])

def propose(im,blocks,index):
 b=blocks[index];s=b.get('content') or '';parts=parse(s) if b['type']=='text' and b.get('angle',0)==0 else None
 if parts is None:return None
 w,h=im.size;box=[round(v*(w if i%2==0 else h)) for i,v in enumerate(b['bbox'])];ink=np.asarray(im.convert('L').crop(box))<180;H,W=ink.shape
 n,lab,stats,_=cv2.connectedComponentsWithStats(ink.astype('uint8'),8);cc=stats[1:];cc=cc[(cc[:,3]>=5)&(cc[:,4]>=4)]
 if len(cc)<8:return dict(accepted=False,reason='few_glyphs')
 gh=float(np.median(cc[:,3]))
 if H>4*gh:return dict(accepted=False,reason='not_one_display_band',height=H,glyph_height=gh)
 blank=~ink.any(0);a=np.diff(np.r_[False,blank,False].astype(int));gaps=[[int(l),int(r)] for l,r in zip(np.where(a==1)[0],np.where(a==-1)[0]) if l>0 and r<W and r-l>=1.5*gh]
 if not gaps:return dict(accepted=False,reason='no_label_gap')
 l,r=gaps[0];x=(l+r)/2
 if not .1*W<x<.55*W:return dict(accepted=False,reason='label_extent_ambiguous',gaps=gaps)
 # One common label baseline; right side can retain tall brackets/fractions, no row splitting.
 left=cc[(cc[:,0]+cc[:,2]<=l)&(cc[:,3]>=.5*gh)]
 if len(left)<4 or np.ptp(left[:,1]+left[:,3])>gh*.5:return dict(accepted=False,reason='label_baseline_ambiguous')
 foreign=[]
 for j,z in enumerate(blocks):
  if j==index:continue
  bb=[round(v*(w if k%2==0 else h)) for k,v in enumerate(z['bbox'])]
  if min(box[2],bb[2])-max(box[0],bb[0])>2 and min(box[3],bb[3])-max(box[1],bb[1])>2:foreign.append(j)
 if foreign:return dict(accepted=False,reason='foreign_owner',foreign=foreign)
 sl=parts['slash'];out=[];cursor=parts['matches'][0].start()
 for m in parts['matches']:
  p=s[cursor:m.start()]
  if p:out.append(sl+'text{'+text_escape(p,sl)+'}')
  out.append(m[2]);cursor=m.end()
 if parts['tail']:out.append(sl+'text{'+text_escape(parts['tail'],sl)+'}')
 math=sl+'['+''.join(out)+sl+']';label=copy.deepcopy(b);formula=copy.deepcopy(b);label['content']=parts['prefix'].strip();formula.update(type='equation',content=math);split=(box[0]+x)/w;label['bbox'][2]=split;formula['bbox'][0]=split
 return dict(accepted=True,reason='single_band_spaced_label_mixed_body',source_box=box,gaps=gaps,glyph_height=gh,new_blocks=[label,formula],original=s,math_segments=[m[2] for m in parts['matches']],prose_preserved=True)
