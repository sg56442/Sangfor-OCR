"""Same uncovered-prose risk, independent pages on three CPU workers; no HTTP."""
import argparse,concurrent.futures,hashlib,json,multiprocessing,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/experimenter'),str(ROOT/'scripts')]

def page_row(task):
    raw_path,source=map(Path,task)
    import cv2
    cv2.setNumThreads(2)
    from PIL import Image
    from uncovered_prose_0136_v4 import detect
    raw_bytes=raw_path.read_bytes();raw=json.loads(raw_bytes)
    with Image.open(source) as im:im=im.convert('RGB');d=detect(im,raw['blocks'])
    bands=sorted(d['uncovered_bands'],key=lambda b:(b[1],b[0]));groups=[]
    for b in bands:
        match=None
        for g in groups:
            a=g[-1];overlap=max(0,min(a[2],b[2])-max(a[0],b[0]));width=min(a[2]-a[0],b[2]-b[0]);gap=b[1]-a[3];height=max(a[3]-a[1],b[3]-b[1])
            if overlap>=.6*width and 0<=gap<=2*height:match=g;break
        if match is None:groups.append([b])
        else:match.append(b)
    risk=[g for g in groups if len(g)>=4]
    return dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),raw=str(raw_path),
                raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),bands=len(bands),groups=risk)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['inputs','pages','out']:ap.add_argument('--'+name,required=True)
    ap.add_argument('--workers',type=int,choices=[1,2,3],default=3);ap.add_argument('--hidden',action='store_true');a=ap.parse_args()
    source,pages,out=map(lambda s:Path(s).resolve(),[a.inputs,a.pages,a.out]);assert out.is_relative_to(ROOT/'runs')
    if not a.hidden:
        assert not out.exists();out.mkdir();(out/'runtime_inputs.json').write_text(json.dumps(dict(inputs=str(source))))
        from panel_hidden_0110_v2 import restricted
        args=['unshare','--net',*restricted(out,[sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--hidden'])]
        os.execvp(args[0],args)
    from single_model_selective_v1 import HIDDEN
    assert all(Path(p).stat().st_size==0 for p in HIDDEN)
    begin=time.monotonic();images={p.stem:p for p in pages.iterdir() if p.is_file()};files=sorted((source/'raw').glob('*.json'));assert len(files)==1651
    tasks=[(str(p),str(images[p.stem])) for p in files];rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        for row in pool.map(page_row,tasks,chunksize=2):
            rows.append(row)
            if len(rows)%25==0:(out/'progress.json').write_text(json.dumps(dict(pages=len(rows),wall_seconds=time.monotonic()-begin)))
    rows.sort(key=lambda q:q['source_sha256']);report=dict(status='COMPLETE',pages=len(rows),expected_pages=len(files),
        risk_pages=sum(bool(q['groups']) for q in rows),risk_groups=sum(len(q['groups']) for q in rows),wall_seconds=time.monotonic()-begin,
        HTTP=0,GT_hidden=True,network_disabled=True,workers=a.workers,cv2_threads_per_worker=2,rows=rows,
        order='source content SHA256; no score,GT,name/rank priority',warning='Risk only. Same detect and grouping as0137; no source-class or content selector introduced.')
    (out/'census.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in report.items() if k not in ['rows']})

if __name__=='__main__':main()
