#!/usr/bin/env python3
"""CPU processor replay inside the existing pinned model container.

Loads the processor once, then verifies each newly consumed HTTP request from
its exact encoded image bytes. It performs no inference or service operations.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import torch
from PIL import Image
from transformers import AutoProcessor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    torch.set_num_threads(2)
    proc = AutoProcessor.from_pretrained(args.model)
    print(json.dumps(dict(status='READY', pid=os.getpid(),
          start_ticks=Path('/proc/self/stat').read_text().split(') ', 1)[1].split()[19],
          processor_class=type(proc.image_processor).__name__)), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        if request.get('stop'):
            break
        try:
            audit = Path(request['audit']).resolve()
            assert audit.is_relative_to(root)
            key = request['request_sha256']
            rows = [json.loads(x) for x in (audit / 'http.jsonl').read_text().splitlines()]
            qs = [x for x in rows if x['stage'] == 'configured' and x['request_sha256'] == key]
            rs = [x for x in rows if x['stage'] == 'consumed' and x['request_sha256'] == key]
            assert qs and rs
            q, r = qs[-1], rs[-1]
            ims = [Image.open(audit / 'images' / (x['encoded_sha256'] + '.png')).convert('RGB') for x in q['images']]
            assert all(hashlib.sha256(im.tobytes()).hexdigest() == x['pixel_sha256'] for im, x in zip(ims, q['images']))
            prompt = ''.join(x['text'] for x in q['prompts'])
            messages = [{'role': 'system', 'content': 'You are a helpful assistant.'},
                        {'role': 'user', 'content': [{'type': 'image', 'image': im} for im in ims]
                         + [{'type': 'text', 'text': prompt}]}]
            text = proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            tensors = proc(text=[text], images=ims, return_tensors='pt')
            grids = tensors['image_grid_thw'].tolist()
            tokens = tensors['input_ids'].shape[-1]
            usage = r['response'].get('usage', {})
            result = dict(request_sha256=key, images=q['images'], image_grid_thw=grids,
                          processed_sizes=[[g[2]*14, g[1]*14] for g in grids],
                          visual_tokens=[math.prod(g)//4 for g in grids],
                          processor_pixel_values_sha256=hashlib.sha256(tensors['pixel_values'].numpy().tobytes()).hexdigest(),
                          replay_prompt_tokens=tokens, server_usage=usage,
                          prompt_tokens_match=tokens == usage.get('prompt_tokens'),
                          remaining_context_before_generation=8192-usage.get('prompt_tokens', 8192),
                          finish_reasons=[x.get('finish_reason') for x in r['response']['choices']],
                          evidence='Exact consumed image bytes replayed in pinned server image on CPU')
            for im in ims:
                im.close()
            print(json.dumps(dict(status='COMPLETE', result=result)), flush=True)
        except Exception as error:
            print(json.dumps(dict(status='FAILED', error=repr(error))), flush=True)


if __name__ == '__main__':
    main()
