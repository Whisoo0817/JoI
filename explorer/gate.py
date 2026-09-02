"""배포 게이트 — 확인된 (IR + 기기 바인딩 표) × 후보 JoI 나란히 비교 (W3).

M3(정답쌍 자기 검증)와 달리 IR 쪽 접지를 후보 JoI가 아니라 **바인딩
표**(dataset.csv binding_gt, §9.8)에서 만든다 — 독립 출처가 아니면
재배선(엉뚱한 기기 선택)을 못 잡는다(§9.4). 양쪽 다 기기 id 기준의
셀·액션 타깃으로 내려서 비교한다:

  IR 쪽   자리 걷기 순서(§9.4)대로 조건·읽기·인자의 서비스 원자를
          기기 형태("<기기id>.Attr")로 다시 쓴다. 여러 대를 읽는 자리는
          바인딩 표의 한정자대로 펼친다: any → or, all → and (§9.10).
          call은 자리별 기기 그룹으로 언롤(기기당 액션 1개).
  JoI 쪽  인벤토리로 접지(ground.py): 셀렉터 → 기기 id 읽기/액션.
          단수 셀렉터가 여러 대와 맞으면 규약(Main 태그 1개면 그것,
          아니면 첫 후보)으로 고른다 — 바인딩 생성 규약(§9.8)과 동일.

판정: EQUIV / DIVERGE(반례 경로 + 구체 재생 확인 = T2 복원) /
REFUSED(단편 밖 — Unsupported를 fail-closed로 감쌈).

Run:  python -m explorer.gate      (캐시 정답쌍 검증 + 재배선 고장 주입)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .expr import canonical_key
from .ground import Dev, ground
from .interp import Unsupported, parse
from .ir_step import IrRunner, _CMP, _tokens, default_to_key
from .oneshot import OneShotRunner
from .pause import PauseRunner, has_blocking
from .product import (ProductResult, ReplayResult, product_runners,
                      replay_divergence)
from .runner import DoneLatch, JoiRunner

_REF = re.compile(r"\b([A-Z][A-Za-z0-9]+)\.([A-Za-z_][A-Za-z0-9_]*)")
_LIT = re.compile(r"[\d.]+|\"[^\"]*\"|'[^']*'|true|false|null")


# ── 바인딩 표 읽기 ───────────────────────────────────────────────────────────

def parse_binding(b: dict) -> dict[str, list[tuple[list[str], str | None]]]:
    """binding_gt JSON → 서비스별 자리 목록(등장 순서).

    자리 값: 기기 id 목록(그대로) 또는 {"any"/"all": [...]}(여러 대 읽기).
    반환: {서비스: [(ids, 한정자|None), ...]} — #2 접미 순서 유지."""
    out: dict[str, list] = {}
    for name, v in b.items():
        svc = name.split("#")[0]
        if isinstance(v, dict):
            quant, ids = next(iter(v.items()))
        else:
            quant, ids = None, v
        out.setdefault(svc, []).append((list(ids), quant))
    return out


# ── IR 다시 쓰기: 서비스 원자 → 기기 형태 ────────────────────────────────────

class _Rewriter:
    """IR을 자리 걷기 순서로 돌며 조건·읽기·인자의 서비스 원자를 기기
    형태로 바꾸고, call 자리별 기기 그룹(bind)과 이름 맞춤표(name_map)를
    모은다. 걷기 순서는 bindgen(§9.4)과 동일해야 자리 번호가 맞는다."""

    def __init__(self, slots: dict):
        self.slots = slots                    # 서비스 → [(ids, quant), ...]
        self.seen: dict[str, int] = {}        # 서비스 → 소비한 자리 수
        self.name_map: dict[str, str] = {}
        self.sites: dict[tuple, list] = {}    # (svc,method) → [자리별 그룹들]
        self.notes: list[str] = []

    def _next(self, svc: str) -> tuple[list[str], str | None]:
        lst = self.slots[svc]
        i = self.seen.get(svc, 0)
        self.seen[svc] = i + 1
        if len(lst) == 1:                     # 병합 자리: 전 등장이 같은 집합
            return lst[0]
        if i < len(lst):                      # 자리 수 == 등장 수 (감사 보장)
            return lst[i]
        return lst[-1]

    def _dev_atom(self, dev: str, svc: str, attr: str) -> str:
        self.name_map[default_to_key(f"{dev}.{attr}")] = \
            f"{dev}.{canonical_key(svc, attr)[1]}"
        return f"{dev}.{attr}"

    def _rw_cond(self, src: str) -> str:
        toks = _tokens(src)
        out: list[str] = []
        i = 0
        while i < len(toks):
            t = toks[i]
            m = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)\.(\w+)", t)
            if not (m and m.group(1) in self.slots):
                out.append(t)
                i += 1
                continue
            svc, attr = m.group(1), m.group(2)
            ids, quant = self._next(svc)
            if len(ids) == 1:
                out.append(self._dev_atom(ids[0], svc, attr))
                i += 1
                continue
            join = " and " if quant == "all" else " or "
            atoms = [self._dev_atom(d, svc, attr) for d in ids]
            # 비교 문맥 통째 복제: [원자 CMP 값] / [값 CMP 원자] / 맨 원자
            if (i + 2 < len(toks) and toks[i + 1] in _CMP
                    and _LIT.fullmatch(toks[i + 2])):
                parts = [f"{a} {toks[i + 1]} {toks[i + 2]}" for a in atoms]
                i += 3
            elif (len(out) >= 2 and out[-1] in _CMP
                    and _LIT.fullmatch(out[-2])):
                cmp_, lhs = out.pop(), out.pop()
                parts = [f"{lhs} {cmp_} {a}" for a in atoms]
                i += 1
            elif not (i + 1 < len(toks) and toks[i + 1] in _CMP):
                parts = atoms                 # 비교 없는 bool 원자
                i += 1
            else:
                raise Unsupported(
                    f"여러 대 읽기의 비교 상대가 단순 값이 아님: {src!r}")
            out.append("( " + join.join(parts) + " )")
        return " ".join(out)

    def _rw_arg(self, v: str) -> str:
        """인자 문자열 속 Service.Attr 읽기를 기기 형태로 (따옴표 안은 제외).
        스칼라 위치라 여러 대 자리는 없다(감사 확인) — 나오면 거부."""
        spans = [m.span() for m in
                 re.finditer(r'"[^"]*"|\'[^\']*\'', v)]

        def _in_quote(p: int) -> bool:
            return any(a <= p < b for a, b in spans)

        out, last = [], 0
        for m in _REF.finditer(v):
            svc = m.group(1)
            if svc not in self.slots or _in_quote(m.start()):
                continue
            ids, _ = self._next(svc)
            if len(ids) != 1:
                raise Unsupported(f"인자 위치에 여러 대 자리: {svc}")
            out.append(v[last:m.start()])
            out.append(self._dev_atom(ids[0], svc, m.group(2)))
            last = m.end()
        out.append(v[last:])
        return "".join(out)

    def walk(self, steps: list) -> None:
        for s in steps:
            if not isinstance(s, dict):
                continue
            for f in ("cond", "until"):
                if s.get(f):
                    s[f] = self._rw_cond(s[f])
            if s.get("op") == "read" and s.get("src"):
                svc, _, attr = s["src"].partition(".")
                if svc in self.slots:
                    ids, _ = self._next(svc)
                    if len(ids) != 1:
                        raise Unsupported(f"read 위치에 여러 대 자리: {svc}")
                    s["src"] = self._dev_atom(ids[0], svc, attr)
            if s.get("op") == "call":
                svc, _, method = s["target"].partition(".")
                if svc in self.slots:
                    ids, _ = self._next(svc)
                    self.sites.setdefault(canonical_key(svc, method), []) \
                        .append([(d,) for d in ids])
                for a, v in list((s.get("args") or {}).items()):
                    if isinstance(v, str):
                        s["args"][a] = self._rw_arg(v)
            for v in s.values():
                if isinstance(v, list):
                    self.walk(v)


def reground_ir(ir: dict, binding: dict) -> tuple[dict, dict, dict, list]:
    """IR + 바인딩 표 → (기기 형태 IR, name_map, bind, 메모)."""
    new_ir = json.loads(json.dumps(ir))
    rw = _Rewriter(parse_binding(binding))
    rw.walk(new_ir.get("timeline") or [])
    return new_ir, rw.name_map, rw.sites, rw.notes


# ── 후보 JoI 접지 ────────────────────────────────────────────────────────────

def devs_of(devices: dict) -> list[Dev]:
    out = []
    for did, d in devices.items():
        cats = tuple(d.get("category") or ())
        out.append(Dev(did, cats[0] if cats else "",
                       spaces=cats, tags=tuple(d.get("tags") or ())))
    return out


def pick_by_rule(matches: list[Dev]) -> Dev:
    """단수 셀렉터가 여러 대와 맞을 때: Main 태그가 정확히 1대면 그것,
    아니면 인벤토리 첫 후보 (§9.8 무지정 단수 규약과 동일)."""
    mains = [d for d in matches if "Main" in d.tags]
    return mains[0] if len(mains) == 1 else matches[0]


# ── 게이트 본체 ──────────────────────────────────────────────────────────────

@dataclass
class GateResult:
    verdict: str                      # EQUIV | DIVERGE | REFUSED
    product: ProductResult | None = None
    replays: list[ReplayResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def confirmed(self) -> bool:
        return any(r.confirmed for r in self.replays)


def gate_pair(ir: dict, binding: dict, devices: dict, jb: dict) -> GateResult:
    """확인된 (IR, 바인딩 표) × 후보 JoI 블록 판정.

    jb: {"script": JoI 코드, "period": ms(0=원샷), "cron": ""|"x"|크론}."""
    notes: list[str] = []
    try:
        period = int(jb.get("period") or 0)
        cron = (jb.get("cron") or "").strip()
        if cron and cron != "x":
            # cron 쌍: 같은 앵커 공유 확인 후 소거 — 창 안 행동만 비교
            tl = [dict(t) for t in (ir.get("timeline") or [])]
            if not (tl and tl[0].get("op") == "start_at"
                    and tl[0].get("anchor") == "cron"
                    and (tl[0].get("cron") or "").strip() == cron):
                raise Unsupported(f"cron 앵커 불일치: joi={cron!r}")
            tl[0] = {"op": "start_at", "anchor": "now"}
            ir = {**ir, "timeline": tl}

        new_ir, name_map, bind, rw_notes = reground_ir(ir, binding)
        notes += rw_notes
        ir_r = IrRunner(new_ir, name_map=name_map, bind=bind)

        gstmts, rep = ground(parse(jb["script"]), devs_of(devices),
                             pick=pick_by_rule)
        if rep.floating:
            notes.append(f"부유 셀렉터(인벤토리 0대): {rep.floating}")

        if period > 0:
            if has_blocking(gstmts):
                joi_r = DoneLatch(PauseRunner(gstmts, repeat=True))
            else:
                joi_r = DoneLatch(JoiRunner.from_src(gstmts))
            pr = product_runners(ir_r, joi_r, period)
        else:
            try:
                joi_r = OneShotRunner(gstmts)
            except Unsupported:
                joi_r = PauseRunner(gstmts, repeat=False)
            ts = [t for t in (set(ir_r.axes.ts_thresholds)
                              | set(joi_r.axes.ts_thresholds)) if t > 0]
            grid = 60000
            if ts and min(ts) < 60:
                grid = 1000 if min(ts) >= 1 else 100
            pr = product_runners(ir_r, joi_r, grid)
    except Unsupported as e:
        return GateResult("REFUSED", notes=notes + [str(e)])

    replays = [replay_divergence(ir_r, joi_r, dv) for dv in pr.divergences]
    return fold_verdict(pr, replays, notes)


def fold_verdict(pr: ProductResult, replays: list[ReplayResult],
                 notes: list[str]) -> GateResult:
    """product 내부 판정 → 배포 3-way 판정 (2026-09-02, whisoo 결정).

    - DIVERGE는 구체 재생으로 확인된 반례가 있을 때만 유지한다(T2 복원).
      재생이 하나도 확인되지 않으면 허위 반례 가능성 — 내부 UNKNOWN.
    - 내부 UNKNOWN(탐색 미완, 재생 미확인)은 밖으로 REFUSED로 접는다:
      배포 행동은 어차피 거절로 같고, 논문 판정은 3-way를 유지한다.
    - EQUIV는 product가 이미 닫힌 그래프에서만 내므로 그대로 통과."""
    if pr.verdict == "DIVERGE" and not any(r.confirmed for r in replays):
        return GateResult("REFUSED", pr, replays,
                          notes + ["내부 UNKNOWN: 반례 재생 미확인(허위 의심)"])
    if pr.verdict == "UNKNOWN":
        return GateResult("REFUSED", pr, replays,
                          notes + ["내부 UNKNOWN: 탐색 미완 — "
                                   + (" ".join(pr.notes) or "사유 미기록")])
    return GateResult(pr.verdict, pr, replays, notes)


# ── 하네스: 캐시 정답쌍 검증 + 재배선 고장 주입 ──────────────────────────────

def load_rows() -> dict[str, dict]:
    import csv
    out = {}
    for r in csv.DictReader(open("dataset.csv")):
        out[f'{r["category_v2"]}_{int(float(r["index"])):03d}'] = r
    return out


def main() -> None:
    import glob
    from collections import Counter

    rows = load_rows()
    res, refused = Counter(), Counter()
    diverged, unconfirmed = [], []
    n_stale = 0
    for f in sorted(glob.glob("paper/simulators/cache/*.json")):
        key = f.rsplit("/", 1)[-1][:-5]
        d = json.load(open(f))
        jb = d.get("joi_block")
        r = rows.get(key)
        if not jb or r is None:
            continue
        ir = json.loads(r["ir_gt"])
        if json.dumps(d.get("ir"), sort_keys=True) \
                != json.dumps(ir, sort_keys=True):
            n_stale += 1        # W2 개정으로 캐시 JoI가 낡은 행 — 제외
            continue
        binding = json.loads(r.get("binding_gt") or "{}")
        devices = json.loads(r["connected_devices"])
        g = gate_pair(ir, binding, devices, jb)
        res[g.verdict] += 1
        if g.verdict == "DIVERGE":
            diverged.append(key)
            if not g.confirmed:
                unconfirmed.append(key)
        if g.verdict == "REFUSED":
            refused[g.notes[-1][:60]] += 1
    print(f"게이트 × 캐시 정답 JoI (낡은 캐시 {n_stale}건 제외):", dict(res))
    if diverged:
        print(f"DIVERGE {len(diverged)}: {diverged}")
        print(f"  그중 재생 미확인: {unconfirmed or '없음'}")
    for k, v in refused.most_common(10):
        print(f"  [{v}] {k}")

    # ── 재배선 고장 주입 (EQUIV 쌍의 JoI 셀렉터를 비틀기 — 전부 DIVERGE
    #    + 재생 확인이어야 함). E3의 wrong-binding fault class 실물.
    print("\n== 재배선 고장 주입 ==")
    muts = [
        ("C03_017 읽기 재배선: 집 재실 → 실외 센서",
         "C03_017", "all(#PresenceSensor #House)", "(#PresenceSensor #Outdoor)"),
        ("C03_017 액션 재배선: 메인 사이렌 → 차고 사이렌",
         "C03_017", "(#Siren)", "(#Garage #Siren)"),
        ("C17_012 집합 탈락: 복도 조명 전체 → 한 대만 끔",
         "C17_012", "all(#Light #Hallway).light_moveToBrightness",
         "(#Light #Hallway).light_moveToBrightness"),
    ]
    for name, key, old, new in muts:
        d = json.load(open(f"paper/simulators/cache/{key}.json"))
        r = rows[key]
        jb = dict(d["joi_block"])
        assert old in jb["script"], f"{name}: 패턴 없음"
        jb["script"] = jb["script"].replace(old, new)
        g = gate_pair(json.loads(r["ir_gt"]),
                      json.loads(r.get("binding_gt") or "{}"),
                      json.loads(r["connected_devices"]), jb)
        tag = g.verdict
        if g.verdict == "DIVERGE":
            tag += " (재생 확인)" if g.confirmed else " (재생 미확인!)"
        print(f"  {name:44s} {tag}")


if __name__ == "__main__":
    main()
