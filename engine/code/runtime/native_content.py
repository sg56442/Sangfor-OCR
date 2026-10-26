"""Apply unchanged native recognition postprocessing to an isolated replaced block."""
import re
from mineru_vl_utils.structs import ContentBlock
def process_content(client,block,answer):
 b=ContentBlock(type=block['type'],bbox=block['bbox'],angle=block.get('angle'),content=answer,merge_prev=False)
 result=client.helper.post_process([b]);assert len(result)==1 and result[0].type==b.type
 content=result[0].content
 if b.type=='equation' and content:content=re.sub(r'\\tag\s*\{[^}]*\}','',content)
 return content
