"""Frozen runtime-only budget split selection; GT and page identifiers are absent."""
from difflib import SequenceMatcher
from lxml import html
from table_mechanisms import grids
from merge_selector import glyphs

def boundary_mode(parts):
 tables=[html.fromstring(s) for s in parts];rows=[t.xpath('.//tr') for t in tables]
 if len(rows)!=2 or any(len(r)<2 for r in rows):return 'unresolved'
 has_super=[any(int(c.get('colspan','1'))>1 for c in r[0].xpath('./td|./th')) for r in rows]
 texts=lambda r:''.join(r.itertext()).strip()
 same_second=SequenceMatcher(None,texts(rows[0][1]),texts(rows[1][1])).ratio()>=.8
 different_first=texts(rows[0][0])!=texts(rows[1][0])
 return 'distinct_superheaders' if all(has_super) and same_second and different_first else 'unresolved'

def choose(native_html,parts,native_finish_reason,part_finish_reasons,image_gap_px):
 gs=[grids(s) for s in parts];og=grids(native_html);nc=glyphs(native_html);cc=glyphs(''.join(parts));coverage=sum((nc&cc).values())/max(1,sum(nc.values()));mode=boundary_mode(parts)
 valid=(len(og)==1 and len(gs)==2 and all(len(g)==1 and g[0]['width']==og[0]['width'] and not g[0]['conflicts'] and not g[0]['holes'] for g in gs))
 finished=len(part_finish_reasons)==2 and all(x=='stop' for x in part_finish_reasons)
 accept=(native_finish_reason=='length' and image_gap_px>0 and valid and finished and coverage>=.90 and mode=='distinct_superheaders')
 return accept,dict(glyph_coverage=coverage,boundary_mode=mode,valid_grid=valid,finished=finished)
