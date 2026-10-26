"""Batch fresh expression comparisons, retaining equal page baselines."""
from phase2_math_groups_render_v2 import *
from phase2_math_groups_render_v2 import Renderer as IndividualRenderer


class Renderer(IndividualRenderer):
    def prepare(self, pairs):
        pairs = sorted(set(pairs) - set(self.results))
        assert len(self.results)+len(pairs) <= self.maximum
        if not pairs:
            return
        folder = self.output/f'batch_{len(self.results):04d}'
        folder.mkdir()
        all_dims = []
        for side, k in [('before', 0), ('after', 1)]:
            docs = [r'\documentclass{article}', r'\usepackage{amsmath,amssymb}',
                    r'\usepackage[paperwidth=2000pt,paperheight=600pt,margin=20pt]{geometry}',
                    r'\pagestyle{empty}', r'\setlength{\parindent}{0pt}', r'\begin{document}']
            for i, pair in enumerate(pairs):
                if i:
                    docs.append(r'\newpage')
                docs.extend([r'\setbox0=\hbox{'+pair[k]+'}',
                    r'\typeout{RSIDIM'+str(i)+r':\the\wd0,\the\ht0,\the\dp0}',
                    r'\vspace*{50pt}\noindent\raisebox{0pt}[100pt][100pt]{\box0}\par'])
            docs.append(r'\end{document}')
            (folder/(side+'.tex')).write_text('\n'.join(docs)+'\n')
            with (folder/(side+'.compile.log')).open('w') as log:
                try:
                    run = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
                            '-no-shell-escape', side+'.tex'], cwd=folder,
                            stdout=log, stderr=subprocess.STDOUT, timeout=60,
                            env=dict(os.environ, openin_any='p', openout_any='p'))
                except subprocess.TimeoutExpired:
                    break
            if run.returncode:
                break
            dims = re.findall(r'RSIDIM([0-9]+):([0-9.]+)pt,([0-9.]+)pt,([0-9.]+)pt',
                              (folder/(side+'.compile.log')).read_text())
            if len(dims) != len(pairs) or [int(d[0]) for d in dims] != list(range(len(pairs))):
                break
            all_dims.append([d[1:] for d in dims])
        if len(all_dims) != 2:
            # A failed batch does not make all its other expressions unsafe or
            # safe. Individual fresh rendering supplies each actual decision.
            for before, after in pairs:
                self.check(before, after)
            return
        docs = [fitz.open(folder/(side+'.pdf')) for side in ['before', 'after']]
        try:
            if any(len(d) != len(pairs) for d in docs):
                for before, after in pairs:
                    self.check(before, after)
                return
            for i, (before, after) in enumerate(pairs):
                dims = [all_dims[k][i] for k in (0,1)]
                if not all(float(w)<1960 and float(h)<80 and float(d)<80 for w,h,d in dims):
                    self.check(before, after)
                    continue
                pix = [d[i].get_pixmap(matrix=fitz.Matrix(2,2), alpha=False) for d in docs]
                arrays = [np.frombuffer(p.samples,np.uint8).reshape(p.height,p.width,p.n) for p in pix]
                same = bool(np.array_equal(*arrays))
                result = dict(index=len(self.results), before=before, after=after,
                    identical=same, reason='identical_full_expression_render' if same else 'visible_layout_difference',
                    pixel_difference_count=int(np.any(arrays[0]!=arrays[1],axis=2).sum()),
                    dimensions_pt=dims, pixel_sha256=[hashlib.sha256(p.samples).hexdigest() for p in pix],
                    batch=str(folder), page=i, two_independent_equal_layout_documents=True,
                    equal_forced_linebox=True, no_pixel_alignment_or_crop=True, new_model_calls=0)
                self.results[(before,after)] = result
        finally:
            for d in docs:
                d.close()
        (folder/'results.json').write_text(json.dumps(list(self.results.values()),ensure_ascii=False,indent=2)+'\n')
