#!/usr/bin/env python3
"""Native table recognition of current-run A/E crops on an explicit RSI lane."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--requests', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--endpoint', required=True)
    p.add_argument('--model', required=True)
    a = p.parse_args()
    out = Path(a.out).resolve()
    assert out.is_relative_to(ROOT)
    out.mkdir(parents=True, exist_ok=False)
    os.environ['FT1021_AUDIT_DIR'] = str(out/'http_audit')
    sys.path.insert(0, str(ROOT/'code/runtime'))
    import http_audit
    from PIL import Image
    from mineru_vl_utils import MinerUClient
    from mineru_vl_utils.post_process import post_process
    from mineru_vl_utils.structs import ContentBlock
    with urllib.request.urlopen(a.endpoint+'/health', timeout=10) as health:
        assert health.status == 200
    client = MinerUClient(backend='http-client', model_name=a.model, server_url=a.endpoint,
                         handle_equation_block=False, image_analysis=False, max_concurrency=45,
                         max_connections=45, max_keepalive_connections=45, use_tqdm=False)
    requests = json.loads(Path(a.requests).read_text())
    answers, started = [], time.time()
    for offset in range(0, len(requests), 32):
        batch = requests[offset:offset+32]
        images = []
        for request in batch:
            with Image.open(request['image_path']) as image:
                images.append(image.convert('RGB'))
            assert hashlib.sha256(images[-1].tobytes()).hexdigest() == request['pixel_sha256']
        results = client._batch_predict(images, [client.prompts['table']]*len(images),
                                        [client.sampling_params['table']]*len(images), None, None)
        for request, result in zip(batch, results):
            processed = post_process([ContentBlock(type='table', bbox=[0.,0.,1.,1.], angle=0, content=result.text)],
                                     simple_post_process=False, handle_equation_block=False,
                                     abandon_list=False, abandon_paratext=False)
            valid = len(processed) == 1 and bool(processed[0].content)
            answers.append({'request_id': request['request_id'], 'text': result.text,
                            'html': processed[0].content if valid else '', 'valid_candidate': valid,
                            'response_sha256': hashlib.sha256(result.text.encode()).hexdigest()})
        for image in images:
            image.close()
        (out/'answers.partial.json').write_text(json.dumps(answers,ensure_ascii=False,indent=2))
    rows = [json.loads(line) for line in (out/'http_audit/http.jsonl').read_text().splitlines()] if requests else []
    configured = {row['request_sha256']: row for row in rows if row['stage']=='configured'}
    by_pixels = {}
    for row in rows:
        if row['stage'] == 'consumed':
            for image in configured[row['request_sha256']]['images']:
                by_pixels[image['pixel_sha256']] = {'usage': row['response']['usage'],
                      'finish_reason': row['response']['choices'][0]['finish_reason'], 'request_sha256': row['request_sha256']}
    for request, answer in zip(requests, answers):
        answer['http_receipt'] = by_pixels[request['pixel_sha256']]
    assert len(requests) == len(answers)
    (out/'answers.json').write_text(json.dumps(answers,ensure_ascii=False,indent=2)+'\n')
    receipt = {'status':'COMPLETE', 'requests':len(requests), 'consumed':len(answers),
               'invalid_candidates':sum(not x['valid_candidate'] for x in answers), 'endpoint':a.endpoint,
               'model':a.model, 'wall_seconds':time.time()-started, 'selected':0,
               'request_manifest_sha256':hashlib.sha256(Path(a.requests).read_bytes()).hexdigest()}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
