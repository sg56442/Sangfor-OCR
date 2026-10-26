"""Whole input replay; identities only bind source files, never select answers."""
import argparse,json,os,hashlib,time,copy
from pathlib import Path
from PIL import Image
from inline_display_0034_v1 import parse,propose

def transform(raw,md,im):
 out=copy.deepcopy(raw); blocks=[]; changes=[]
 for i,b in enumerate(raw['blocks']):
  z=propose(im,raw['blocks'],i) if b['type']=='text' and parse(b.get('content')or'') else None
  if z and z['accepted'] and md.count(z['original'])==1:
   replacement='\n\n'.join(t['content'] for t in z['new_blocks'])
   md=md.replace(z['original'],replacement,1);blocks.extend(z['new_blocks']);changes.append(dict(index=i,proposal=z))
  else:blocks.append(b)
 out['blocks']=blocks
 return out,md,changes

