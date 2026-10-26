#!/usr/bin/env python3
"""Table cells: numeric-range dash->hyphen, no CJK-digit space, \\(..\\)->$..$ (trimmed, guarded).
Pure deterministic CLI: reads <src>/raw/*.json + <src>/markdown/*.md (1651 pages per manifest),
writes <dst>/raw, <dst>/markdown and <dst>/receipt.json. HTTP=0, no model, no GT, no network.
Usage: python3 table_cell_style_v3.py --src PRED_DIR --dst OUT_DIR [--manifest control/pages1651.json]
"""
import argparse, hashlib, json, os, re, sys, time

RULE_NAME = "table_cell_style_v3"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def tree_hash(items):
    h = hashlib.sha256()
    for k in sorted(items):
        h.update((k + " " + items[k] + "\n").encode())
    return h.hexdigest()

RANGE = re.compile(r'(?<=\d)\s*[–—−]\s*(?=\d)')
CJKDIG = re.compile('([一-鿿㐀-䶿])[  ]+(?=[0-9])')
ADJ = re.compile(r'\\\)\s*\\\(')  # adjacent formulas: leave as is
PAREN_MATH = re.compile(r'\\\(\s*(.*?)\s*\\\)')


def cell_fn(s):
    """Table-cell style harmonisation (benchmark cell conventions):
    1) dash/minus between digits -> ASCII hyphen; 2) no space between CJK char and digit;
    3) inline math written \\(...\\) -> $...$ (the cell normaliser only understands whole-cell wrappers)."""
    s = RANGE.sub('-', s)
    s = CJKDIG.sub(r'\1', s)
    return (s if ADJ.search(s) else PAREN_MATH.sub(lambda m: '$' + m.group(1) + '$' if m.group(1) and '$' not in m.group(1) else m.group(0), s))

CELL = re.compile(r'(<t[dh](?:\s[^>]*)?>)(.*?)(</t[dh]>)', re.S)
TAG = re.compile(r'(<[^>]+>)')


def _cell_text_map(inner, fn):
    return "".join(p if p.startswith("<") and p.endswith(">") else fn(p) for p in TAG.split(inner))


def map_tables(text, fn):
    """Apply fn to the text of every table cell inside <table>...</table> spans of text."""
    def tbl(m):
        return CELL.sub(lambda c: c.group(1) + _cell_text_map(c.group(2), fn) + c.group(3), m.group(0))
    return re.sub(r'<table\b.*?</table>', tbl, text, flags=re.S)


def rule(raw, md):
    nmd = map_tables(md, cell_fn)
    nblocks = []; nb = 0
    for b in raw["blocks"]:
        c = b.get("content")
        if c and b.get("type") == "table" and "<table" in c:
            q = map_tables(c, cell_fn)
            if q != c:
                b = dict(b); b["content"] = q; nb += 1
        nblocks.append(b)
    if nmd == md and not nb:
        return raw, md, None
    nraw = dict(raw); nraw["blocks"] = nblocks
    return nraw, nmd, {"tables_changed_md": sum(1 for a, b in zip(re.findall(r'<table\b.*?</table>', md, re.S), re.findall(r'<table\b.*?</table>', nmd, re.S)) if a != b), "raw_table_blocks_changed": nb}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--manifest", default="/data/zxh/rsi_fixed/experiments/campaign-ft-1023/control/pages1651.json")
    a = ap.parse_args()
    t0 = time.time()
    ids = [e["id"] for e in json.load(open(a.manifest, encoding="utf-8"))]
    assert len(ids) == 1651 and len(set(ids)) == 1651
    if os.path.exists(a.dst) and os.listdir(a.dst):
        sys.exit("dst exists and is non-empty")
    os.makedirs(a.dst + "/raw", exist_ok=True)
    os.makedirs(a.dst + "/markdown", exist_ok=True)
    ih, oh, changed, stats = {}, {}, [], {}
    for pid in ids:
        rp = f"{a.src}/raw/{pid}.json"; mp = f"{a.src}/markdown/{pid}.md"
        rb = open(rp, "rb").read(); mb = open(mp, "rb").read()
        ih["raw/" + pid] = sha(rb); ih["md/" + pid] = sha(mb)
        raw = json.loads(rb.decode("utf-8")); md = mb.decode("utf-8")
        nraw, nmd, st = rule(raw, md)
        nrb = json.dumps(nraw, ensure_ascii=False, indent=2).encode("utf-8") if st else rb
        nmb = nmd.encode("utf-8") if st else mb
        if st:
            changed.append(pid)
            for k, v in st.items():
                stats[k] = stats.get(k, 0) + v
        open(f"{a.dst}/raw/{pid}.json", "wb").write(nrb)
        open(f"{a.dst}/markdown/{pid}.md", "wb").write(nmb)
        oh["raw/" + pid] = sha(nrb); oh["md/" + pid] = sha(nmb)
    rec = dict(rule=RULE_NAME, script=os.path.basename(__file__), script_sha256=sha(open(__file__, "rb").read()),
               HTTP=0, model_calls=0, gt_used=False, pages=len(ids), changed_pages=len(changed),
               changed_page_ids=changed, stats=stats, input_tree_sha256=tree_hash(ih),
               output_tree_sha256=tree_hash(oh), input_files_sha256=ih if False else None,
               seconds=round(time.time() - t0, 2))
    json.dump(rec, open(a.dst + "/receipt.json", "w"), indent=2)
    print(json.dumps({k: rec[k] for k in ("rule", "pages", "changed_pages", "stats", "output_tree_sha256")}))


if __name__ == "__main__":
    main()
