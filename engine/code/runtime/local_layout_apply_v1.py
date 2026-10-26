import copy,re

def area(b):return max(0,b[2]-b[0])*max(0,b[3]-b[1])
def overlap(a,b):return area([max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3])])
def mapped(box,p):
 x,y,z,t=p['pixel_rect'];w,h=p['page_size'];return [(x+box[0]*(z-x))/w,(y+box[1]*(t-y))/h,(x+box[2]*(z-x))/w,(y+box[3]*(t-y))/h]
def protected(b):
 s=b.get('content')or''
 return b['type']=='table' or (b['type']=='equation' and bool(re.search(r'\\(?:tag|label)\b|\\begin\s*\{(?:array|[bpvBV]?matrix)|\([0-9]+(?:\.[0-9]+)*\)\s*(?:\\\])?\s*$',s)))
def inner(s):
 s=s.strip()
 for l,r in [('\\[','\\]'),('$$','$$')]:
  if s.startswith(l) and s.endswith(r):return s[len(l):-len(r)].strip()
 return s

def apply(blocks,proposals,responses,family):
 bs=copy.deepcopy(blocks);replacements={};removed=set();records=[]
 for p in proposals:
  local=responses.get(p['proposal_id'],[]);maps=[dict(b,bbox=mapped(b['bbox'],p)) for b in local];ids=p['indices'];rec=dict(proposal=p['proposal_id'],accepted=False,mapped_layout=maps,original_indices=ids,selected_groups=[])
  if family=='group':
   for region in maps:
    if region['type']!='text' or region.get('angle') not in (None,0):continue
    members=[i for i in ids if area(bs[i]['bbox'])>0 and overlap(bs[i]['bbox'],region['bbox'])/area(bs[i]['bbox'])>=.9]
    if len(members)<2 or any(i in removed or protected(bs[i]) for i in members):continue
    if any(i not in ids and overlap(b['bbox'],region['bbox'])>0.1*max(area(b['bbox']),1e-9) for i,b in enumerate(bs)):continue
    if not any(bs[i]['type']=='equation' for i in members):continue
    if not re.search(r'\\(?:because|therefore)\b|[∵∴]|(?:解|证明|故|因此|从而)', ''.join(bs[i].get('content','') for i in members)):continue
    if members!=list(range(min(members),max(members)+1)):continue
    parts=[('\\('+inner(bs[i]['content'])+'\\)') if bs[i]['type']=='equation' else bs[i]['content'] for i in members];b=copy.deepcopy(bs[members[0]]);b.update(type='text',content='\n'.join(parts),bbox=[min(bs[i]['bbox'][0] for i in members),min(bs[i]['bbox'][1] for i in members),max(bs[i]['bbox'][2] for i in members),max(bs[i]['bbox'][3] for i in members)],merge_prev=False);replacements[members[0]]=[b];removed.update(members);rec['selected_groups'].append(dict(indices=members,native_contents=[bs[i]['content'] for i in members],assembled=b['content']))
   rec.update(accepted=bool(rec['selected_groups']),reason='source_layout_text_enclosure' if rec['selected_groups'] else 'no_unprotected_source_supported_group')
  else:
   i=ids[0]
   if len(ids)!=1 or bs[i]['type']!='text' or not maps or any(b['type']!='text' or b.get('angle') not in (None,0) for b in maps):rec['reason']='parent_or_subview_not_pure_text'
   elif any(j!=i and overlap(b['bbox'],p['bbox'])>.1*max(area(b['bbox']),1e-9) for j,b in enumerate(bs)):rec['reason']='other_native_block_overlap'
   elif any(not b.get('content') for b in maps):rec['reason']='missing_recognition'
   else:
    for j,b in enumerate(maps):b['merge_prev']=False if j==0 else b.get('merge_prev',False)
    replacements[i]=maps;removed.add(i);rec.update(accepted=True,reason='native_text_parent_only_local_layout',selected_groups=[dict(indices=[i],native_contents=[bs[i]['content']])])
  records.append(rec)
 result=[]
 for i,b in enumerate(bs):
  if i in replacements:result.extend(replacements[i])
  elif i not in removed:result.append(b)
 return result,records
