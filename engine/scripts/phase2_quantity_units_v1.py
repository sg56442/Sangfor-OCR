"""Keep a standalone numeric quantity and its explicit unit in one math span.

This changes representation ownership only. Every original number, operator,
parenthesis and unit is retained. No source identities or answers are inputs.
"""
import re

from pylatexenc.latexwalker import LatexWalker


LINE = re.compile(
    r'^(?P<lead>\s*)(?P<open>\\\(|\\\[|\$(?!\$))'
    r'(?P<body>.*?)(?P<close>\\\)|\\\]|(?<!\$)\$)'
    r'(?P<gap>[ \t]*)(?P<unit>\([^()（）\\${}\n]+\)|（[^()（）\\${}\n]+）)'
    r'(?P<trail>[ \t]*)$'
)
PAIRS = {r'\(': r'\)', r'\[': r'\]', '$': '$'}
NUMERIC_COMMANDS = {
    'times', 'div', 'cdot', 'approx', 'simeq', 'leq', 'geq',
    'pm', 'mp', 'frac', 'dfrac', 'tfrac', 'sqrt', 'left', 'right',
}
NAMED_UNITS = {
    '克', '千克', '公斤', '毫克', '微克', '吨',
    '秒', '毫秒', '微秒', '纳秒', '分钟', '分', '小时', '时', '天', '日',
    '升', '毫升', '度', '摄氏度', '开尔文', '安培', '毫安',
    '伏', '伏特', '千伏', '瓦', '瓦特', '千瓦', '焦', '焦耳',
    '千焦', '牛', '牛顿', '帕', '帕斯卡', '千帕', '兆帕', '赫兹',
    '千赫', '兆赫', '库仑', '欧姆', '摩尔', '坎德拉',
    '元', '角', '美元', '人民币元', '欧元', '英镑', '日元',
}
LENGTH = re.compile(r'(?:(?:平方|立方))?(?:千|分|厘|毫|微|纳)?米')
SI_ATOM = r'(?:[yzafpnumcdhkMGTPEZYμµ]?(?:mol|cd|Hz|Pa|Wb|eV|m|s|g|A|K|N|J|W|C|V|F|Ω|S|T|H|l|L))(?:[²³]|\^[23])?'
SI_UNIT = re.compile(SI_ATOM + r'(?:[·/]' + SI_ATOM + r')*')


def explicit_unit(value):
    inner = value[1:-1].strip()
    return bool(inner in NAMED_UNITS or LENGTH.fullmatch(inner) or SI_UNIT.fullmatch(inner))


def numeric_expression(body):
    """Reject variables, prose, nested math delimiters and unknown commands."""
    if not re.search(r'\d', body) or '$' in body:
        return False
    names = re.findall(r'\\([A-Za-z]+)', body)
    if any(name not in NUMERIC_COMMANDS for name in names):
        return False
    plain = re.sub(r'\\[A-Za-z]+', '', body)
    if not re.fullmatch(r'[0-9\s+*/=<>^.,:()\[\]{}−–×÷±≈-]+', plain):
        return False
    try:
        _, start, length = LatexWalker(body, tolerant_parsing=False).get_latex_nodes()
        return start == 0 and length == len(body)
    except Exception:
        return False


def transform(content):
    if any(marker in content.lower() for marker in ['`', '~~~', '<code', '<pre']):
        return content, []
    result, changes = [], []
    for ordinal, line in enumerate(content.splitlines(keepends=True)):
        body = line.rstrip('\r\n')
        ending = line[len(body):]
        match = LINE.fullmatch(body)
        if (match is None or PAIRS[match['open']] != match['close']
                or not explicit_unit(match['unit'])
                or not numeric_expression(match['body'])):
            result.append(line)
            continue
        after = (match['lead'] + match['open'] + match['body'] + match['gap']
                 + r'\text{' + match['unit'] + '}' + match['close'] + match['trail'])
        changes.append(dict(line=ordinal, before=body, after=after,
                            numeric_body=match['body'], original_unit=match['unit']))
        result.append(after + ending)
    return ''.join(result), changes
