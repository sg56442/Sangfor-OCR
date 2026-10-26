"""Independent equal-layout documents avoid TeX prevdepth across pages."""
from phase2_math_groups_render_v1 import *
from phase2_math_groups_render_v1 import Renderer as PreviousRenderer


class Renderer(PreviousRenderer):
    def check(self, before, after):
        key = (before, after)
        if key in self.results:
            return self.results[key]
        assert len(self.results) < self.maximum, 'Declared render-pair budget exhausted'
        index = len(self.results)
        folder = self.output/f'{index:04d}'
        folder.mkdir()
        record = dict(index=index, before=before, after=after, identical=False,
                      reason='render_failed', no_extra_model_calls=True,
                      two_independent_equal_layout_documents=True)
        dimensions = []
        for side, expression in [('before', before), ('after', after)]:
            docs = [r'\documentclass{article}', r'\usepackage{amsmath,amssymb}',
                    r'\usepackage[paperwidth=2000pt,paperheight=600pt,margin=20pt]{geometry}',
                    r'\pagestyle{empty}', r'\setlength{\parindent}{0pt}',
                    r'\begin{document}', r'\setbox0=\hbox{'+expression+'}',
                    r'\typeout{RSIDIM:\the\wd0,\the\ht0,\the\dp0}',
                    r'\vspace*{50pt}\noindent\box0\par', r'\end{document}']
            (folder/(side+'.tex')).write_text('\n'.join(docs)+'\n')
            with (folder/(side+'.compile.log')).open('w') as log:
                try:
                    run = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
                            '-no-shell-escape', side+'.tex'], cwd=folder,
                            stdout=log, stderr=subprocess.STDOUT, timeout=12,
                            env=dict(os.environ, openin_any='p', openout_any='p'))
                    record[side+'_returncode'] = run.returncode
                except subprocess.TimeoutExpired:
                    record['reason'] = 'compile_timeout'
                    break
            if run.returncode:
                break
            dims = re.findall(r'RSIDIM:([0-9.]+)pt,([0-9.]+)pt,([0-9.]+)pt',
                              (folder/(side+'.compile.log')).read_text())
            if len(dims) != 1 or not all(float(w)<1960 and float(h)+float(d)<500 for w,h,d in dims):
                record['reason'] = 'unmeasured_or_clipped_dimensions'
                break
            dimensions.append(dims[0])
        if len(dimensions) == 2:
            record['dimensions_pt'] = dimensions
            pix = []
            for side in ['before', 'after']:
                with fitz.open(folder/(side+'.pdf')) as doc:
                    if len(doc) != 1:
                        record['reason'] = 'unexpected_page_count'
                        break
                    pix.append(doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False))
            if len(pix) == 2:
                arr = [np.frombuffer(p.samples, np.uint8).reshape(p.height,p.width,p.n) for p in pix]
                record['identical'] = bool(np.array_equal(*arr))
                record['pixel_difference_count'] = int(np.any(arr[0] != arr[1], axis=2).sum())
                record['reason'] = 'identical_full_expression_render' if record['identical'] else 'visible_layout_difference'
                record['pixel_sha256'] = [hashlib.sha256(p.samples).hexdigest() for p in pix]
        self.results[key] = record
        (folder/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        return record
