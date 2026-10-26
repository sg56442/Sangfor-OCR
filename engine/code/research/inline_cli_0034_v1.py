"""Isolated zero-call full-input inline display regrouping. No diagnostic inputs."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[2]
GT=['/opt/p2t10/hidden/OmniDocBench.json','/opt/p2t10/hidden/source_validation_v2_references.jsonl','/opt/p2t10/hidden/source_validation_v1_references.jsonl']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--out',required=True);ap.add_argument('--isolated',action='store_true');a=ap.parse_args()
 if not a.isolated:
  gt=[p for p in GT if Path(p).exists()]
  sh='set -euo pipefail\nn="$1"; shift\nfor ((i=0;i<n;i++)); do mount --bind /dev/null "$1"; test ! -s "$1"; shift; done\nexec "$@"'
  subprocess.run(['unshare','--net','--mount','--propagation','private','/bin/bash','-c',sh,'inline0034',str(len(gt)),*gt,sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:],'--isolated'],check=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',INLINE_PARENT_NET=os.readlink('/proc/self/ns/net')));return
 assert os.readlink('/proc/self/ns/net')!=os.environ['INLINE_PARENT_NET']
 assert all(not Path(p).exists() or Path(p).stat().st_size==0 for p in GT)
 from PIL import Image
 from inline_transform_0034_v1 import transform
 from inline_display_0034_v1 import parse,propose
 src,manifest,out=map(lambda x:Path(x).resolve(),[a.inputs,a.manifest,a.out]);assert out.is_relative_to(R) and not out.exists()
 pages=json.loads(manifest.read_text());ids={p['id'] for p in pages};assert len(ids)==len(pages)==1651
 for sub,ext in [('raw','.json'),('markdown','.md')]:
  assert {p.stem for p in (src/sub).glob('*'+ext)}==ids
  (out/sub).mkdir(parents=True)
 start=time.monotonic();records=[]
 for p in pages:
  rp=src/'raw'/(p['id']+'.json');mp=src/'markdown'/(p['id']+'.md');rb=rp.read_bytes();mb=mp.read_bytes();raw=json.loads(rb);md=mb.decode();new,nmd,zs=raw,md,[];audit=[]
  indices=[i for i,b in enumerate(raw['blocks']) if b['type']=='text' and parse(b.get('content')or'')]
  if indices:
   with Image.open(p['image']) as im:
    new,nmd,zs=transform(raw,md,im)
    audit=[dict(index=i,geometry=propose(im,raw['blocks'],i),unique_md=md.count(raw['blocks'][i]['content'])==1) for i in indices]
  ro,mo=out/'raw'/rp.name,out/'markdown'/mp.name
  if zs:ro.write_text(json.dumps(new,ensure_ascii=False,indent=2));mo.write_bytes(nmd.encode())
  else:assert new==raw and nmd==md;os.link(rp.resolve(),ro);os.link(mp.resolve(),mo)
  records.append(dict(id=p['id'],source=p['image'],source_sha256=sha(p['image']),input_raw_sha256=sha(rp),input_md_sha256=sha(mp),output_raw_sha256=sha(ro),output_md_sha256=sha(mo),changes=zs,audit=audit))
 deps=[Path(__file__).resolve(),R/'code/research/inline_transform_0034_v1.py',R/'code/research/inline_display_0034_v1.py']
 receipt=dict(pages=1651,changed_pages=sum(bool(r['changes']) for r in records),changed_owners=sum(len(r['changes']) for r in records),HTTP=0,tokens=0,GT_hidden=True,network_isolated=True,wall_seconds=time.monotonic()-start,manifest_sha256=sha(manifest),dependencies={str(p):sha(p) for p in deps},records=records)
 (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print({k:v for k,v in receipt.items() if k not in ['records','dependencies']})
if __name__=='__main__':main()
