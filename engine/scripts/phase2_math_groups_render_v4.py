"""Require equal natural TeX extents as well as pixels at a fixed baseline."""
from phase2_math_groups_render_v3 import *
from phase2_math_groups_render_v3 import Renderer as BatchedRenderer


class Renderer(BatchedRenderer):
    @staticmethod
    def guard_extent(record):
        dims = record.get('dimensions_pt')
        if record['identical'] and (not dims or dims[0] != dims[1]):
            record['pixel_identical_before_extent_guard'] = True
            record['identical'] = False
            record['reason'] = 'natural_box_extent_difference'
        return record

    def check(self, before, after):
        return self.guard_extent(super().check(before, after))

    def prepare(self, pairs):
        super().prepare(pairs)
        for record in self.results.values():
            self.guard_extent(record)
        (self.output/'effective_results.json').write_text(
            json.dumps(list(self.results.values()),ensure_ascii=False,indent=2)+'\n')
