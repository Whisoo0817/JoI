"""Stage ⑦ — contingency compilation (M-E).

Roles are finite, so a scenario's failure modes are enumerable offline. For
every (template x bound device instance) this module precomputes the full
response — decision, patched artifact, static findings — so the runtime path is
a dictionary lookup followed by deploying an already-verified artifact.

    offline (nightly)                          runtime (device goes offline)
    ─────────────────────                      ─────────────────────────────
    for each bound device d:                   row = table[dead_device_id]
        inventory' = inventory - d             match row.action:
        bind -> verdict                          redeploy  -> push row.artifact
        degrade -> feature-closure drop          abort     -> stop + row.notice
                -> patch -> checks               keep      -> nothing to do
        store row                                escalate  -> online pipeline

Honesty rules:
* a row that cannot be precomputed safely is stored as **escalate**, with the
  slicer's reason — the table never hides a hole (no silent caps);
* `drop_feature` expands to the whole feature closure (every role sharing the
  feature): dropping the camera alone would leave the alert email reading an
  undefined `video`, which the slicer refuses; dropping camera+email together
  is clean. The closure is the unit a purpose can lose.
* artifacts carry the hash of the source they were derived from; a stale table
  (source changed) is detected at lookup time, not silently deployed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

from .bind import bind
from .check import check_static
from .inventory import Inventory
from .patch import apply_and_check
from .slicer import plan_drop, plan_drop_source
from .structure import Structure, extract
from .template import Template, load_skeleton, load_template

_HERE = os.path.dirname(os.path.abspath(__file__))
TABLE_DIR = os.path.join(_HERE, "contingency_tables")


@dataclass
class Row:
    template: str
    device_id: str
    device_type: str
    roles_hit: list[str]
    action: str                     # keep | redeploy | abort | escalate
    verdict: str                    # bind verdict
    dropped_features: list[str] = field(default_factory=list)
    artifact: Optional[str] = None  # adapted source, ready to deploy
    artifact_bytes: int = 0
    base_hash: str = ""
    findings: list[str] = field(default_factory=list)
    notice: str = ""                # user-facing message
    reason: str = ""                # for abort/escalate
    compile_ms: float = 0.0


@dataclass
class Table:
    template: str
    inventory: str
    base_hash: str
    rows: dict[str, Row]            # device_id -> row
    compiled_ms: float = 0.0

    def lookup(self, device_id: str, current_source_hash: str) -> Row:
        if current_source_hash != self.base_hash:
            raise StaleTable(f"table built for {self.base_hash[:8]}, "
                             f"source is now {current_source_hash[:8]} — recompile")
        row = self.rows.get(device_id)
        if row is None:
            return Row(self.template, device_id, "?", [], "keep", "ok",
                       notice="device not used by this scenario")
        return row


class StaleTable(RuntimeError):
    pass


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _roles_bound_to(t: Template, st: Structure, inv: Inventory, device_id: str) -> list[str]:
    """Roles whose binding would lose this instance (offline it and diff)."""
    base = bind(t, st, inv)
    inv2 = _clone(inv)
    inv2.set_online(device_id, False)
    after = bind(t, st, inv2)
    hit = []
    base_by = {(d.role, tuple(d.source_tags)): d for d in base.decisions}
    for d in after.decisions:
        b = base_by.get((d.role, tuple(d.source_tags)))
        if b is not None and (b.action, getattr(b.device, "id", None)) != \
                (d.action, getattr(d.device, "id", None)):
            hit.append(d.role)
    return sorted(set(hit))


def _clone(inv: Inventory) -> Inventory:
    import copy
    return copy.deepcopy(inv)


def compile_row(t: Template, st: Structure, inv: Inventory, device_id: str) -> Row:
    t0 = time.perf_counter()
    base_hash = _hash(st.src)
    dev = next(d for d in inv.devices if d.id == device_id)
    roles_hit = _roles_bound_to(t, st, inv, device_id)

    def done(row: Row) -> Row:
        row.compile_ms = (time.perf_counter() - t0) * 1000
        return row

    if not roles_hit:
        return done(Row(t.id, device_id, dev.type, [], "keep", "ok",
                        base_hash=base_hash,
                        notice=f"{dev.type} loss does not affect this scenario"))

    inv2 = _clone(inv)
    inv2.set_online(device_id, False)
    rep = bind(t, st, inv2)

    if rep.verdict == "abort":
        why = [r for r in roles_hit if t.role(r).essential]
        return done(Row(t.id, device_id, dev.type, roles_hit, "abort", "abort",
                        base_hash=base_hash,
                        notice=f"시나리오 중단: 필수 역할 {why or roles_hit}의 장치({dev.type})가 "
                               f"오프라인이며 대체가 없습니다.",
                        reason="essential role lost, no sound candidate"))

    # substitution / realization rows carry their own edits
    sub_edits = [e for d in rep.decisions for e in d.edits]

    # Split the drops: a role with a surviving healthy source loses only the
    # dead source's code (source-level slice); a role that is entirely gone
    # loses its whole feature closure.
    role_decisions: dict[str, list] = {}
    for d in rep.decisions:
        role_decisions.setdefault(d.role, []).append(d)

    source_drops: list[tuple[str, int]] = []
    dropped_roles: list[str] = []
    for role, ds in role_decisions.items():
        if role not in roles_hit:
            continue
        healthy = [d for d in ds if d.action in ("keep", "substitute", "realize")]
        dead = [d for d in ds if d.action == "drop_feature"]
        if not dead:
            continue
        if healthy:
            contract = t.role(role)
            for d in dead:
                for i, src in enumerate(contract.sources):
                    if list(src.tags) == list(d.source_tags):
                        source_drops.append((role, i))
        else:
            feat = t.role(role).feature
            closure = [r.role for r in t.roles if feat is not None and r.feature == feat]
            dropped_roles.extend(closure or [role])
    dropped_roles = sorted(set(dropped_roles))
    features = sorted({t.role(r).feature for r in dropped_roles if t.role(r).feature})

    edits = list(sub_edits)
    for role, idx in source_drops:
        plan = plan_drop_source(t, st, role, idx)
        if not plan.ok:
            return done(Row(t.id, device_id, dev.type, roles_hit, "escalate", rep.verdict,
                            base_hash=base_hash, reason=plan.reason,
                            notice=f"{dev.type} 오프라인: 소스 절단 불가 — 온라인 파이프라인으로 "
                                   f"에스컬레이션합니다 ({plan.reason})"))
        edits += plan.edits
    if dropped_roles:
        plan = plan_drop(t, st, dropped_roles)
        if not plan.ok:
            return done(Row(t.id, device_id, dev.type, roles_hit, "escalate", rep.verdict,
                            base_hash=base_hash, reason=plan.reason,
                            notice=f"{dev.type} 오프라인: 자동 강등이 불가하여 온라인 파이프라인으로 "
                                   f"에스컬레이션합니다 ({plan.reason})"))
        edits += plan.edits

    if not edits:
        return done(Row(t.id, device_id, dev.type, roles_hit, "keep", rep.verdict,
                        base_hash=base_hash,
                        notice=f"{dev.type} 오프라인이지만 다른 소스가 역할을 유지합니다."))

    res = apply_and_check(st, edits)
    if not res.ok:
        return done(Row(t.id, device_id, dev.type, roles_hit, "escalate", rep.verdict,
                        base_hash=base_hash, reason=res.summary,
                        notice="사전 컴파일 실패 — 온라인 파이프라인으로 에스컬레이션"))
    findings = check_static(t, res.structure_after, before=st,
                            dropped_roles=dropped_roles or None)
    blocking = [f for f in findings if f.severity == "blocking"]
    if blocking:
        return done(Row(t.id, device_id, dev.type, roles_hit, "escalate", rep.verdict,
                        base_hash=base_hash,
                        reason="; ".join(f.detail for f in blocking)[:200],
                        notice="정적 검사 실패 — 온라인 파이프라인으로 에스컬레이션"))

    notice = (f"{dev.type} 오프라인: 기능 {features} 을(를) 포기하고 계속 동작합니다."
              if features else f"{dev.type} 오프라인: 대체 장치로 재바인딩했습니다.")
    return done(Row(t.id, device_id, dev.type, roles_hit, "redeploy", rep.verdict,
                    dropped_features=features, artifact=res.output,
                    artifact_bytes=len(res.output), base_hash=base_hash,
                    findings=[f"{f.check}:{f.detail}" for f in findings],
                    notice=notice))


def compile_table(t: Template, inv: Inventory) -> Table:
    t0 = time.perf_counter()
    st = extract(load_skeleton(t), t.name)
    rows: dict[str, Row] = {}
    for dev in inv.devices:
        rows[dev.id] = compile_row(t, st, inv, dev.id)
    return Table(template=t.id, inventory=inv.name, base_hash=_hash(st.src),
                 rows=rows, compiled_ms=(time.perf_counter() - t0) * 1000)


def save_table(table: Table, directory: str = TABLE_DIR) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{table.template}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"template": table.template, "inventory": table.inventory,
                   "base_hash": table.base_hash, "compiled_ms": table.compiled_ms,
                   "rows": {k: asdict(v) for k, v in table.rows.items()}},
                  f, ensure_ascii=False, indent=1)
    return path


def main(argv: list[str] | None = None) -> int:
    import argparse
    from .inventory import base_office
    from .template import list_templates

    ap = argparse.ArgumentParser(description="Stage ⑦: contingency compilation")
    ap.add_argument("--template", help="one template (default: all)")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args(argv)

    inv = base_office()
    for tid in ([args.template] if args.template else list_templates()):
        t = load_template(tid)
        table = compile_table(t, inv)
        print(f"\n# {tid} — compiled {len(table.rows)} rows in {table.compiled_ms:.0f} ms")
        for dev_id, row in table.rows.items():
            extra = f" features={row.dropped_features}" if row.dropped_features else ""
            extra += f" artifact={row.artifact_bytes}B" if row.artifact else ""
            extra += f" reason={row.reason[:50]}" if row.reason else ""
            print(f"  {dev_id:<6} {row.device_type:<18} -> {row.action:<9} "
                  f"({row.compile_ms:.1f} ms){extra}")
        if args.save:
            print("  saved ->", save_table(table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
