"""Conservative geometry-to-response gate. No GT, page labels, numeric/date priors."""
import sys,re
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'code/research'))
from table_mechanisms import grids
from mineru_vl_utils.post_process.otsl2html import convert_otsl_to_html

def select(proposal,answer,finished=True):
 if not proposal.get('eligible'):return dict(accept=False,reason='preflight_reject')
 if not proposal['complete_context'] or proposal['outside_ink_components']:return dict(accept=False,reason='same_owner_outside_grid_content_unresolved')
 if not finished:return dict(accept=False,reason='generation_not_normal_stop')
 try:markup=convert_otsl_to_html(answer);gs=grids(markup)
 except Exception as e:return dict(accept=False,reason='parser_failure',detail=type(e).__name__)
 if len(gs)!=1:return dict(accept=False,reason='not_one_table')
 g=gs[0]
 if g['conflicts'] or g['holes'] or g['span_beyond_rows']:return dict(accept=False,reason='invalid_response_partition')
 if (g['rows'],g['width'])!=(proposal['rows'],proposal['cols']):return dict(accept=False,reason='source_response_grid_dimensions_differ',source=[proposal['rows'],proposal['cols']],response=[g['rows'],g['width']])
 key=lambda c:(c['row'],c['col'],c['rowspan'],c['colspan'])
 source={key(c):c for c in proposal['cells']};response={key(c):c for c in g['cells']}
 if set(source)!=set(response):return dict(accept=False,reason='source_response_cell_partition_differ')
 for k,s in source.items():
  occupied=bool(re.sub(r'\s+','',response[k]['text']))
  if (s['ink_pixels']>=6)!=occupied:return dict(accept=False,reason='source_response_occupied_cell_conflict',cell=list(k),source_ink=s['ink_pixels'],response_nonempty=occupied)
 return dict(accept=True,reason='geometry_partition_occupancy_match_pending_source_support_review',html=markup,scope='Geometry validates structure/occupancy, not every character. Requires normal/source support before adoption.')
