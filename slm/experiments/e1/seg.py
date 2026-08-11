# -*- coding: utf-8 -*-
"""
E1 — Korean clause segmenter + evaluation-item selection.

Public interface
----------------
    segment_kor(cmd: str) -> list[str]
    build_items(dataset_path: str, out_json: str, n: int = 60, min_ops: int = 4) -> dict

Everything is rule based, deterministic, stdlib only.

Segmentation model
------------------
Korean is head-final: a clause ends on its last word, which carries the
connective ending.  So we split AFTER a word, never before one.  The whole
algorithm is therefore a per-word boolean `is_boundary(i)`, and the invariant
    " ".join(segment_kor(cmd)) == " ".join(cmd.split())
holds by construction (we only ever regroup the token list produced by
`cmd.split()`; no token is rewritten, dropped, added or reordered).

Cues (clause-final endings) and the guards that kill their false positives are
documented next to the tables below.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, OrderedDict

# --------------------------------------------------------------------------
# 0. token-level helpers
# --------------------------------------------------------------------------

# punctuation that may trail a token and that we strip before matching endings
_TRAIL_PUNCT = '.,!?;:)]』」”\'"…~'
# closing delimiters stripped before we look at the real sentence punctuation
_CLOSERS = '"\'”’)]}』」>'
# punctuation that, on its own, terminates a clause
_COMMA_PUNCT = (',', ';', '，', '；', '·')
_STOP_PUNCT = ('.', '!', '?', '…', '。')

_QUOTE_CHARS = {'"': '"', "'": "'"}
_QUOTE_OPEN = '“‘「『'
_QUOTE_CLOSE = '”’」』'


def _core(tok: str) -> str:
    """token minus trailing punctuation (leading quotes are kept: they are
    part of a quoted argument and never affect the ending)."""
    return tok.rstrip(_TRAIL_PUNCT)


def _has_digit(s: str) -> bool:
    return any(ch.isdigit() for ch in s)


# --------------------------------------------------------------------------
# 1. false-positive guards
# --------------------------------------------------------------------------

# Nouns whose citation form ends in '고' — '차고 문', '창고 온도', '금고 문' ...
# Matched as a WHOLE word only, so verb forms such as '떨어지고' are unaffected.
_NOUN_GO = {
    '차고', '창고', '냉장고', '금고', '경고', '광고', '보고', '신고', '사고',
    '참고', '최고', '중고', '원고', '재고', '완고', '온고', '농고', '고',
    '그리고',            # sentence-initial conjunction: starts a clause, never ends one
}

# Nouns whose citation form ends in '면' — '수면 모드', '라면', '화면' ...
_NOUN_MYEON = {
    '수면', '화면', '지면', '표면', '측면', '벽면', '라면', '반면', '장면',
    '단면', '정면', '노면', '국면', '도면', '평면', '액면', '이면', '방면',
    '한편', '면',
    '아니면',           # else-marker: it OPENS the else clause, so no split after it
}

# '서'-final tokens that are not connectives
_NOUN_SEO = {'센서', '서', '문서', '순서', '질서', '엽서', '명세서'}

# genuine '-서' connective endings (converb).  '에서' (locative) is absent from
# this set on purpose, which is what kills '주방에서 / 차고에서 / 사이에서'.
_SUF_SEO = ('해서', '아서', '어서', '여서', '와서', '워서', '라서', '고서', '봐서')

# quotative complementiser: '...라고 말해줘' / '...다고 알려줘'.  The quoted
# material is an ARGUMENT of the following verb, not a separate clause.
_SUF_QUOTATIVE = ('라고', '다고', '냐고', '자고', '느냐고', '으라고')

# '-고 있다 / -고 없다' progressive-resultative auxiliary: '감지되고 있으면'
# is ONE predicate, so '감지되고' does not close a clause.
_AUX_NEXT_PREFIX = ('있', '없', '계시', '싶')

# temporal "after N" heads.  Only the locative-marked forms ('후에', '뒤에',
# '다음에') close a clause; a BARE '후 / 뒤' is a measure phrase that still
# belongs with the following verb ('3번 후 멈춰줘', '1시간 뒤 다시 확인해서'),
# so it is deliberately not listed.
# '오후 / 이후에 / 향후' are excluded: they are clause-INITIAL adverbials
# ('주말 오후에 30분마다 ...', '열리면 이후에 1분마다 ...').
_AFTER_HEADS = {'후에', '뒤에', '다음에'}
_AFTER_BLOCK = {'오후', '오후에', '이후', '이후에', '향후', '전후', '최후', '노후'}
# merged spellings seen in the corpus: '10분뒤에', '10초뒤에'
_AFTER_MERGED = re.compile(r'\d\s*(초|분|시간|시|일|번)\s*(뒤에|후에|다음에)$')
# a duration/count phrase that legitimately licenses a bare '후에 / 뒤에'
_DURATION_PREV = re.compile(r'\d\s*(초|분|시간|시|일|주|달|개월|번|회)$')
# adnominal verb form that licenses '-(으)ㄴ 후에'  ('끝난 후에', '조리된 다음에')
_ADNOM_PREV = re.compile(r'(한|은|린|난|된|친|간)$')


def _is_after_head(core: str, prev_core: str) -> bool:
    if core in _AFTER_BLOCK:
        return False
    if _AFTER_MERGED.search(core):
        return True
    if core not in _AFTER_HEADS:
        return False
    if not prev_core:
        return False
    if _DURATION_PREV.search(prev_core):
        return True
    return bool(_ADNOM_PREV.search(prev_core)) and len(prev_core) >= 2


# --------------------------------------------------------------------------
# 2. the cue table
# --------------------------------------------------------------------------

def _is_cue(core: str, prev_core: str, next_core: str) -> bool:
    """True when `core` carries a clause-final connective ending."""
    if len(core) < 2:
        return False

    # -- quotative: never a clause end -------------------------------------
    if core.endswith(_SUF_QUOTATIVE):
        return False

    # -- '-때 / -때마다'  (whenever / at the time that) ---------------------
    if core.endswith(('때마다', '때에', '때는', '때')):
        return True

    # -- '-자마자' (as soon as) --------------------------------------------
    if core.endswith('자마자'):
        return True

    # -- '-면서' (while) ----------------------------------------------------
    if core.endswith('면서'):
        return True

    # -- '-는데 / -ㄴ데 / -은데' (background) --------------------------------
    if len(core) >= 3 and core.endswith(('는데', '은데', 'ㄴ데', '인데')):
        return True

    # -- '-다가' (transition) ----------------------------------------------
    if len(core) >= 3 and core.endswith('다가'):
        return True

    # -- '-거나' (or) -------------------------------------------------------
    if core.endswith('거나'):
        return True

    # -- '-면' (if / when) --------------------------------------------------
    if core.endswith('면') and core not in _NOUN_MYEON:
        return True

    # -- '-서' (and-then / because) ----------------------------------------
    if core.endswith(_SUF_SEO) and core not in _NOUN_SEO and len(core) >= 3:
        return True

    # -- '-고' (and) --------------------------------------------------------
    if core.endswith('고') and core not in _NOUN_GO:
        # '-고 있다' auxiliary → not a boundary
        if next_core.startswith(_AUX_NEXT_PREFIX):
            return False
        # '그렇지 않고 ...' → 않고 opens the else clause
        if core == '않고' and prev_core.rstrip(_TRAIL_PUNCT) == '그렇지':
            return False
        return True

    # -- 'N분 후에 / N초 뒤에 / ... 다음에' ---------------------------------
    if _is_after_head(core, prev_core):
        return True

    return False


# --------------------------------------------------------------------------
# 3. segment_kor
# --------------------------------------------------------------------------

def _quote_depth_after_token(tokens: list[str]) -> list[int]:
    """quote nesting state at the END of every token (0 == outside a quote)."""
    out = []
    dq = False   # inside "..."
    sq = False   # inside '...'
    ang = 0      # inside “...” / 「...」
    for tok in tokens:
        for ch in tok:
            if ch == '"':
                dq = not dq
            elif ch == "'":
                sq = not sq
            elif ch in _QUOTE_OPEN:
                ang += 1
            elif ch in _QUOTE_CLOSE:
                ang = max(0, ang - 1)
        out.append(int(dq) + int(sq) + ang)
    return out


def segment_kor(cmd: str) -> list[str]:
    """Split a Korean IoT command into ordered clauses.

    Invariant: " ".join(segment_kor(cmd)) == " ".join(cmd.split())
    """
    tokens = cmd.split()
    if not tokens:
        return []

    depth = _quote_depth_after_token(tokens)

    clauses: list[str] = []
    cur: list[str] = []
    for i, tok in enumerate(tokens):
        cur.append(tok)
        if i == len(tokens) - 1:
            break                       # never split after the final token
        if depth[i] > 0:
            continue                    # inside a quoted string argument

        core = _core(tok)
        prev_core = _core(tokens[i - 1]) if i > 0 else ''
        next_core = _core(tokens[i + 1])

        # trailing punctuation, ignoring any closing quote / bracket
        tail = tok.rstrip(_CLOSERS)

        boundary = False
        if tail.endswith(_COMMA_PUNCT):
            boundary = True                     # comma / semicolon closes a clause
        elif tail.endswith(_STOP_PUNCT):
            boundary = True                     # sentence break mid-command
        elif _is_cue(core, prev_core, next_core):
            boundary = True

        if boundary:
            clauses.append(' '.join(cur))
            cur = []
    if cur:
        clauses.append(' '.join(cur))
    return clauses


def count_boundaries(cmd: str) -> int:
    return max(0, len(segment_kor(cmd)) - 1)


# --------------------------------------------------------------------------
# 4. IR helpers
# --------------------------------------------------------------------------

def parse_ir(raw: str) -> dict:
    return json.loads(raw, strict=False)


def count_ops(node) -> int:
    """number of dicts carrying an "op" key, recursively."""
    n = 0
    if isinstance(node, dict):
        if 'op' in node:
            n += 1
        for v in node.values():
            n += count_ops(v)
    elif isinstance(node, list):
        for v in node:
            n += count_ops(v)
    return n


def op_sequence(node, out=None) -> list[str]:
    """flattened, depth-first op names (document order)."""
    if out is None:
        out = []
    if isinstance(node, dict):
        if 'op' in node and isinstance(node['op'], str):
            out.append(node['op'])
        for k in node:
            op_sequence(node[k], out)
    elif isinstance(node, list):
        for v in node:
            op_sequence(v, out)
    return out


def has_non_ascii_string(node) -> bool:
    """True when ANY string (key or value) in the IR contains a non-ASCII char."""
    if isinstance(node, str):
        return any(ord(c) > 127 for c in node)
    if isinstance(node, dict):
        for k, v in node.items():
            if has_non_ascii_string(k) or has_non_ascii_string(v):
                return True
        return False
    if isinstance(node, list):
        return any(has_non_ascii_string(v) for v in node)
    return False


# --------------------------------------------------------------------------
# 5. item selection
# --------------------------------------------------------------------------

def _read_rows(dataset_path: str) -> list[dict]:
    csv.field_size_limit(10 ** 7)
    with open(dataset_path, newline='', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def _largest_remainder(pool_hist: "OrderedDict[int,int]", n: int) -> "OrderedDict[int,int]":
    """proportional allocation of n slots over strata, largest-remainder method."""
    total = sum(pool_hist.values())
    if total == 0:
        return OrderedDict()
    n = min(n, total)
    exact = {k: pool_hist[k] * n / total for k in pool_hist}
    alloc = {k: min(int(exact[k]), pool_hist[k]) for k in pool_hist}
    left = n - sum(alloc.values())
    # deterministic ordering: bigger remainder first, then bigger stratum, then key
    order = sorted(pool_hist, key=lambda k: (-(exact[k] - int(exact[k])), -pool_hist[k], k))
    idx = 0
    while left > 0:
        k = order[idx % len(order)]
        if alloc[k] < pool_hist[k]:
            alloc[k] += 1
            left -= 1
        idx += 1
        if idx > 10 * len(order) + n:
            break
    return OrderedDict((k, alloc[k]) for k in pool_hist)


def _spread_pick(items: list, k: int) -> list:
    """deterministic, evenly spaced pick of k elements from an ordered list."""
    m = len(items)
    if k >= m:
        return list(items)
    if k <= 0:
        return []
    return [items[int(round(i * (m - 1) / (k - 1)))] if k > 1 else items[m // 2]
            for i in range(k)]


def build_items(dataset_path: str, out_json: str, n: int = 60, min_ops: int = 4) -> dict:
    rows = _read_rows(dataset_path)

    stats = {
        'rows_total': len(rows),
        'unique_commands': 0,
        'dup_commands_dropped': 0,
        'ir_parse_errors': 0,
        'excluded_non_ascii_ir': 0,
        'excluded_few_ops': 0,
        'excluded_single_clause': 0,
        'eligible': 0,
        'selected': 0,
    }

    seen_cmd = set()
    eligible = []
    for ordinal, row in enumerate(rows):
        cmd = (row.get('command_kor') or '').strip()
        if not cmd:
            continue
        if cmd in seen_cmd:
            stats['dup_commands_dropped'] += 1
            continue
        seen_cmd.add(cmd)

        try:
            ir = parse_ir(row['ir_gt'])
        except Exception:
            stats['ir_parse_errors'] += 1
            continue

        n_ops = count_ops(ir)
        clauses = segment_kor(cmd)

        # exclusion order is fixed so the counters are unambiguous
        if has_non_ascii_string(ir):
            stats['excluded_non_ascii_ir'] += 1
            continue
        if n_ops < min_ops:
            stats['excluded_few_ops'] += 1
            continue
        if len(clauses) < 2:
            stats['excluded_single_clause'] += 1
            continue

        eligible.append({
            'index': ordinal,
            'csv_index': row.get('index', ''),
            'category': row.get('category_v2', ''),
            'cmd': cmd,
            'devices': row.get('connected_devices', ''),
            'ir_gt': ir,
            'n_ops': n_ops,
            'clauses': clauses,
        })

    stats['unique_commands'] = len(seen_cmd)
    stats['eligible'] = len(eligible)

    # ---- stratified deterministic pick over op-count ----------------------
    by_ops: "OrderedDict[int,list]" = OrderedDict()
    for it in sorted(eligible, key=lambda d: d['index']):
        by_ops.setdefault(it['n_ops'], []).append(it)
    pool_hist = OrderedDict((k, len(by_ops[k])) for k in sorted(by_ops))
    alloc = _largest_remainder(pool_hist, n)

    chosen = []
    for k in sorted(alloc):
        chosen.extend(_spread_pick(by_ops[k], alloc[k]))
    chosen.sort(key=lambda d: d['index'])
    stats['selected'] = len(chosen)

    stats['pool_op_hist'] = dict(pool_hist)
    stats['selected_op_hist'] = dict(sorted(Counter(it['n_ops'] for it in chosen).items()))
    stats['pool_clause_hist'] = dict(sorted(Counter(len(it['clauses']) for it in eligible).items()))
    stats['selected_clause_hist'] = dict(sorted(Counter(len(it['clauses']) for it in chosen).items()))

    os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
    with open(out_json, 'w', encoding='utf-8') as fh:
        json.dump(chosen, fh, ensure_ascii=False, indent=2)

    stats['out_json'] = os.path.abspath(out_json)
    return stats


# --------------------------------------------------------------------------
# 6. self-test
# --------------------------------------------------------------------------

DATASET = '/home/ikess/joi-llm/joi_new/dataset.csv'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'items.json')


def _main() -> int:
    rows = _read_rows(DATASET)
    cmds = []
    seen = set()
    for r in rows:
        c = (r.get('command_kor') or '').strip()
        if c and c not in seen:
            seen.add(c)
            cmds.append(c)

    # ---- (a) invariant ----------------------------------------------------
    bad = []
    for c in cmds:
        segs = segment_kor(c)
        if ' '.join(segs) != ' '.join(c.split()):
            bad.append(c)
        assert all(s.strip() for s in segs), c
    print('=' * 78)
    print('(a) LOSSLESS INVARIANT   " ".join(segment_kor(c)) == " ".join(c.split())')
    print(f'    commands checked : {len(cmds)}')
    print(f'    result           : {"PASS" if not bad else "FAIL (%d)" % len(bad)}')
    for c in bad[:5]:
        print('      !!', c)

    nb = [count_boundaries(c) for c in cmds]
    print(f'    boundary markers : {sum(nb)} across {sum(1 for x in nb if x)} commands '
          f'({sum(1 for x in nb if not x)} single-clause)')
    print(f'    clause-count hist: {dict(sorted(Counter(len(segment_kor(c)) for c in cmds).items()))}')

    # ---- (b) selection stats ---------------------------------------------
    stats = build_items(DATASET, OUT)
    print()
    print('=' * 78)
    print('(b) E1 ITEM SELECTION')
    for k in ('rows_total', 'unique_commands', 'dup_commands_dropped', 'ir_parse_errors',
              'excluded_non_ascii_ir', 'excluded_few_ops', 'excluded_single_clause',
              'eligible', 'selected', 'out_json'):
        print(f'    {k:24s}: {stats[k]}')
    print(f'    {"pool_op_hist":24s}: {stats["pool_op_hist"]}')
    print(f'    {"selected_op_hist":24s}: {stats["selected_op_hist"]}')
    print(f'    {"pool_clause_hist":24s}: {stats["pool_clause_hist"]}')
    print(f'    {"selected_clause_hist":24s}: {stats["selected_clause_hist"]}')
    tot = sum(stats['pool_op_hist'].values()) or 1
    sel = sum(stats['selected_op_hist'].values()) or 1
    print('    stratification check (share of pool vs share of sample):')
    for k in sorted(stats['pool_op_hist']):
        p = stats['pool_op_hist'][k] / tot
        s = stats['selected_op_hist'].get(k, 0) / sel
        print(f'        {k:2d} ops : pool {p:6.1%}   sample {s:6.1%}')

    # ---- (c) 12 example segmentations -------------------------------------
    with open(OUT, encoding='utf-8') as fh:
        items = json.load(fh)
    print()
    print('=' * 78)
    print('(c) 12 EXAMPLE SEGMENTATIONS  (clause1 | clause2 | ... ;  gold op sequence)')
    picks = _spread_pick(items, 12)
    for it in picks:
        print()
        print(f'  #{it["index"]:3d}  [{it["category"]}]  n_ops={it["n_ops"]}  '
              f'n_clauses={len(it["clauses"])}')
        print('    ' + ' | '.join(it['clauses']))
        print('    gold: ' + ' > '.join(op_sequence(it['ir_gt'])))
    print()
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(_main())
