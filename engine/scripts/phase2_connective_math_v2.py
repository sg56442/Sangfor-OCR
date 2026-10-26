"""Grammatical connectives with complete mathematical statements; research only."""
import re
from phase2_connective_math_v1 import convert as original_convert


def convert(source):
    candidate, reason = original_convert(source)
    if candidate is None:
        return candidate, reason
    # A continuation beginning with an operator is not an independent sentence.
    for body in re.findall(r'\\\((.*?)\\\)', candidate, re.S):
        body = re.sub(r'^(?:\s|\\(?:quad|qquad)\b|\\[,;:!])+', '', body)
        if re.match(r'^(?:[=<>+*/]|\\(?:approx|equiv|leq|geq|times|div)\b)', body):
            return None, 'incomplete_mathematical_continuation'
    return candidate, reason
