"""Fail-closed pretransport checks. No model calls; does not authorize retries."""
import json,hashlib

def validate(selected_parameters, native_parameters, encoded_bytes, task, known_request_identities, known_pixels):
 if selected_parameters != native_parameters:
  raise ValueError('sampling differs from bound native Table request')
 if hashlib.sha256(encoded_bytes).hexdigest()!=task['encoded_sha256']:
  raise ValueError('prepared bytes changed')
 if task['identity'] in known_request_identities or task['pixel_sha256'] in known_pixels:
  raise ValueError('previously observed request or pixels')
 return True

def audit_consumed(configured, consumed, task, native_parameters):
 if configured['parameters'] != native_parameters:
  raise RuntimeError('actual wire differs: halt entire queue, not per-item continue')
 if configured['images'][0]['pixel_sha256'] != task['pixel_sha256']:
  raise RuntimeError('actual image mismatch: halt entire queue')
 if consumed['response']['usage']['prompt_tokens'] != task['processor']['prompt_tokens']:
  raise RuntimeError('processor token mismatch: halt entire queue')
 return True
