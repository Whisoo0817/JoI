"""Build the E2 result tables from the recorded runs.

~/temp/bin/python make_e2_results.py  ->  RESULTS.md

Population: the 140 pairs of `handoff_timer/e2_population.json` (frozen 142 minus two invalid inputs). Every table,
including the development records, is computed on those 140 pairs. Inputs (plain `.jsonl` or the committed
`.jsonl.gz`):
- `runs/e2_run.timer-binding.jsonl`: final Explorer verdicts (the paper numbers). `explorer_binding_final` keeps the
  verdict of the same pair before the exploration optimizations, under the same budget and binding contract.
- `runs/e2_run.ref-frozen.jsonl`, `runs/e2_run.ref-current.jsonl`, `runs/e2_run.ref-current-supp.jsonl`,
  `runs/e2_run.binding-final.jsonl`: development records (frozen reference, None-comparison decision, supplementary
  histories, binding contract).
Refusals, timeouts and reference-unsupported pairs stay in every denominator.
"""
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
KINDS = ["correct", "fault", "llm"]
ORDER = [
    "AGREE-EQUIV-ON-CHECKED", "AGREE-DIVERGE", "EXPLORER-DIVERGE-CONFIRMED-BY-REF-ON-WITNESS",
    "FALSE-EQUIV-CANDIDATE", "FALSE-DIVERGE-CANDIDATE",
    "DIVERGE-WITNESS-ir:ok joi:unsupported", "DIVERGE-WITNESS-ir:unsupported joi:unsupported",
    "EXPLORER-REFUSED", "EXPLORER-TIMEOUT", "EXPLORER-ERROR",
]
CONFIRMED = ("AGREE-EQUIV-ON-CHECKED", "AGREE-DIVERGE", "EXPLORER-DIVERGE-CONFIRMED-BY-REF-ON-WITNESS")
CAUSE = {"C07": "nested repetition with timers (time budget exceeded)",
         "E1-099": "deadline that grows with the number of motion events (refused)"}

POPULATION = json.loads((HERE / "handoff_timer" / "e2_population.json").read_text())
EXCLUDED = {e["pair_id"]: e for e in POPULATION["exclusions"]}


def open_text(path):
    """Read `path`, or `path.gz` when only the committed compressed copy exists."""
    if not path.exists():
        gz = path.with_name(path.name + ".gz")
        if not gz.exists():
            return None
        path = gz
    return gzip.open(path, "rt").read() if path.suffix == ".gz" else path.read_text()


def load(name):
    """Rows of `runs/<name>` keyed by pair id, restricted to the 140-pair population."""
    text = open_text(RUNS / name)
    if text is None:
        return None
    rows = {r["pair_id"]: r for r in (json.loads(l) for l in text.splitlines() if l.strip())}
    return {p: r for p, r in rows.items() if p not in EXCLUDED}


def verdict(r):
    return (r.get("explorer") or {}).get("verdict")


def decided(v):
    return v in ("EQUIV", "DIVERGE")


def table(rows, key, cols):
    head = "| " + " | ".join(["", *cols, "total"]) + " |\n|" + "---|" * (len(cols) + 2) + "\n"
    names = [n for n in ORDER if any(key(r) == n for r in rows)] + sorted({key(r) for r in rows} - set(ORDER))
    body = ""
    for n in names:
        c = [sum(1 for r in rows if key(r) == n and r["_col"] == col) for col in cols]
        body += f"| {n} | " + " | ".join(map(str, c)) + f" | {sum(c)} |\n"
    tot = [sum(1 for r in rows if r["_col"] == col) for col in cols]
    return head + body + "| total | " + " | ".join(map(str, tot)) + f" | {sum(tot)} |\n"


def by_kind(rows):
    rs = list(rows.values())
    for r in rs:
        r["_col"] = r["kind"]
    return rs


def family_table(rows, key):
    faults = [r for r in rows.values() if r["kind"] == "fault"]
    for r in faults:
        r["_col"] = r["family"]
    return table(faults, key, sorted({r["family"] for r in faults}))


def section(label, rows):
    rs = by_kind(rows)
    out = f"### Reference `{label}`\n\nAgreement by pair kind:\n\n" + table(rs, lambda r: r["agreement"], KINDS)
    out += "\nReference outcome by pair kind:\n\n" + table(rs, lambda r: r["reference"]["outcome"], KINDS)
    out += "\nFault pairs, agreement by fault family:\n\n" + family_table(rows, lambda r: r["agreement"])
    return out


def history_counts():
    counts = []
    for names in (("e1_histories.json", "sample_388_histories.json"), ("supplement_histories.json",)):
        n = 0
        for name in names:
            hs = json.loads(open_text(HERE / "histories" / name))["histories"]
            n += sum(len(v) for k, v in hs.items() if f"{k}/llm" not in EXCLUDED)
        counts.append(n)
    return counts


def final_section(fin, pairs_src):
    rs = by_kind(fin)
    md = "## Final version (paper numbers)\n\n"
    md += ("Explorer with the semantics-preserving exploration optimizations (merged timer branch) under the binding "
           "contract (`BINDING_DECISION_2026-09-14.md`) and the uninitialized-variable rule (RUNTIME_CONTRACT R14, "
           "author decision 2026-09-16). Reference outcomes are those of the binding-contract run, with the "
           "reference side recomputed under R14; every new Explorer witness was replayed on the reference. "
           "Rows: `runs/e2_run.timer-binding.jsonl`. Budget per pair: 120 s, 400,000 states, 2,000,000 transitions.\n\n")
    orig, supp = history_counts()
    md += f"Histories for the 140 pairs: {orig:,} original + {supp:,} supplementary = {orig + supp:,}.\n\n"
    md += "Explorer verdicts:\n\n" + table(rs, verdict, KINDS)
    md += "\nAgreement:\n\n" + table(rs, lambda r: r["agreement"], KINDS)

    dec = [r for r in rs if decided(verdict(r))]
    confirmed = [r for r in dec if r["agreement"] in CONFIRMED]
    unconfirmable = [r["pair_id"] for r in dec if r["agreement"].startswith("DIVERGE-WITNESS")]
    false = [r["pair_id"] for r in rs if "FALSE" in r["agreement"]]
    obs = [r for r in rs if r["kind"] == "fault" and (r["reference"]["outcome"] == "REF-DIVERGE" or
           (r["explorer"].get("witness_on_reference") or {}).get("status") == "diverge")]
    count = lambda a: sum(r["agreement"] == a for r in dec)
    md += "\n### Table 1. Fidelity of decided verdicts\n\n| | pairs |\n|---|---:|\n"
    md += f"| decided (EQUIV or DIVERGE) | {len(dec)} |\n"
    md += f"| confirmed by the reference | {len(confirmed)} |\n"
    md += f"| &nbsp;&nbsp;EQUIV, no difference on the reference histories | {count('AGREE-EQUIV-ON-CHECKED')} |\n"
    md += f"| &nbsp;&nbsp;DIVERGE, difference on the reference histories | {count('AGREE-DIVERGE')} |\n"
    md += f"| &nbsp;&nbsp;DIVERGE, confirmed by replaying the Explorer witness | {count(CONFIRMED[2])} |\n"
    if unconfirmable:
        md += f"| not confirmable: reference cannot run the JoI | {len(unconfirmable)} ({', '.join(unconfirmable)}) |\n"
    md += f"| contradicted by the reference (false EQUIV / false DIVERGE) | {len(false)} |\n"
    md += f"| fault pairs with an observed difference | {len(obs)} |\n"
    md += (f"| of those: Explorer DIVERGE / EQUIV (missed) / undecided | "
           f"{sum(verdict(r) == 'DIVERGE' for r in obs)} / {sum(verdict(r) == 'EQUIV' for r in obs)} / "
           f"{sum(not decided(verdict(r)) for r in obs)} |\n")

    wit = [r for r in dec if r["agreement"] == CONFIRMED[2]]
    md += "\nWitness-only confirmations (the reference histories showed no difference):\n\n"
    for label, outcome in (("no reference history reached the diverging input", "REF-EQUIV-CHECKED"),
                           ("the JoI reads a device value the histories do not supply (reference cannot run it on "
                            "its histories)", "REF-UNSUPPORTED-JOI")):
        named = [r["pair_id"] for r in wit if r["reference"]["outcome"] == outcome]
        if named:
            md += f"- {label}: " + ", ".join(named) + "\n"
    unobs = sorted(r["pair_id"] for r in rs if r["kind"] == "fault" and r not in obs)
    md += (f"\nFault pairs without an observed difference ({len(unobs)}): {', '.join(unobs)} "
           "(both tools EQUIV or the Explorer undecided; no reference history or witness shows a difference).\n")

    llm = [r for r in rs if r["kind"] == "llm"]
    hand = [r for r in rs if r["kind"] != "llm"]
    reqs = {}
    for r in hand:
        reqs.setdefault(pairs_src[r["pair_id"]]["base_case"], []).append(r)
    full = sorted(b for b, g in reqs.items() if all(decided(verdict(r)) for r in g))
    md += "\n### Table 2. Decision rate by population\n\n| population | decided | note |\n|---|---:|---|\n"
    md += f"| LLM-generated candidates | {sum(decided(verdict(r)) for r in llm)}/{len(llm)} | random sample of the 388 set, valid inputs |\n"
    md += f"| hand-built pairs, by pair | {sum(decided(verdict(r)) for r in hand)}/{len(hand)} | correct + fault variants of E1 requirements |\n"
    md += (f"| hand-built pairs, by requirement | {len(full)}/{len(reqs)} | not fully decided: "
           f"{', '.join(sorted(set(reqs) - set(full)))} |\n")
    md += f"| all pairs | {len(dec)}/{len(rs)} | |\n"

    md += "\n### Table 3. Undecided pairs by cause\n\n| cause | requirement | pairs |\n|---|---|---:|\n"
    by = {}
    for r in rs:
        if not decided(verdict(r)):
            b = pairs_src[r["pair_id"]]["base_case"]
            by[(CAUSE.get(b, "other"), b)] = by.get((CAUSE.get(b, "other"), b), 0) + 1
    for (c, b), n in sorted(by.items()):
        md += f"| {c} | {b} | {n} |\n"

    before = {p: (r.get("explorer_binding_final") or {}).get("verdict") for p, r in fin.items()}
    changed = sorted(p for p, r in fin.items() if decided(before[p]) and before[p] != verdict(r))
    added = sorted(p for p, r in fin.items() if not decided(before[p]) and decided(verdict(r)))
    n0 = sum(decided(v) for v in before.values())
    md += "\n### Table 4. Exploration optimizations (same budget, same binding contract)\n\n"
    md += "| | pairs |\n|---|---:|\n"
    md += f"| decided before the optimizations | {n0}/{len(fin)} |\n"
    md += f"| decided after the optimizations | {len(dec)}/{len(fin)} |\n"
    md += f"| additional pairs decided | {len(added)} |\n"
    md += f"| earlier verdicts changed | {len(changed)} |\n"
    md += f"| still undecided | {len(rs) - len(dec)} |\n"
    md += "\nAdditional pairs decided:\n\n| pair | before | after | agreement |\n|---|---|---|---|\n"
    for p in added:
        md += f"| {p} | {before[p]} | {verdict(fin[p])} | {fin[p]['agreement']} |\n"
    return md


def main():
    pairs_src = {}
    for f in ("pairs/e1_pairs.json", "pairs/sample_388_pairs.json"):
        pairs_src.update({q["pair_id"]: q for q in json.loads((HERE / f).read_text())["pairs"]})
    fin = load("e2_run.timer-binding.jsonl")
    fro, cur, supp, new = (load(f"e2_run.{n}.jsonl") for n in ("ref-frozen", "ref-current", "ref-current-supp",
                                                                  "binding-final"))
    for rows, name in ((fin, "timer-binding"), (fro, "ref-frozen"), (cur, "ref-current"),
                       (supp, "ref-current-supp"), (new, "binding-final")):
        assert rows is not None, f"missing runs/e2_run.{name}.jsonl(.gz)"
        assert len(rows) == POPULATION["behavioral_population"], (name, len(rows))
    for p in fro:
        assert verdict(fro[p]) == verdict(cur[p]) == verdict(supp[p])

    md = "# E2 results (generated by `make_e2_results.py`)\n\n"
    md += (f"Population: {POPULATION['behavioral_population']} pairs (`handoff_timer/e2_population.json`). The frozen "
            f"set has {POPULATION['frozen_population']} pairs; {len(EXCLUDED)} are invalid inputs and are kept apart "
            "from every table below:\n\n")
    for p, e in sorted(EXCLUDED.items()):
        md += f"- `{p}` ({e['category']}): {e['reason']}\n"
    md += ("\nThe final section holds the paper numbers. The development records after it are kept for provenance; "
           "they are not the paper numbers. Hand inspection: `INSPECTION_2026-09-14.md`.\n\n")
    md += final_section(fin, pairs_src)

    md += "\n## Development records (not the paper numbers)\n\n"
    md += "### Frozen run: Explorer verdicts\n\n" + table(by_kind(cur), verdict, KINDS)
    walls = sorted(r["wall_seconds"] for r in cur.values())
    md += (f"\nWall time per pair: median {walls[len(walls) // 2]:.0f} s, max {walls[-1]:.0f} s, "
           f"total {sum(walls):.0f} s (Explorer budget 120 s of exploration per pair). Explorer verdicts from "
           "`runs/e2_run.jsonl`; reference side recomputed twice: `frozen` = reference at `649cb9c`, `current` = "
           "reference after the None-comparison decision (FREEZE_MANIFEST.md, harness corrections).\n\n")
    md += section("current", cur) + "\n" + section("frozen", fro)
    md += "\n### Frozen vs current\n\n| pair | reference outcome | agreement frozen | agreement current |\n|---|---|---|---|\n"
    n = 0
    for p in sorted(fro):
        f, c = fro[p], cur[p]
        if (f["reference"]["outcome"], f["agreement"]) != (c["reference"]["outcome"], c["agreement"]):
            n += 1
            md += f"| {p} | {f['reference']['outcome']} → {c['reference']['outcome']} | {f['agreement']} | {c['agreement']} |\n"
    md += (f"\n{n} pairs differ; every difference is a witness replay that the frozen reference refused on a "
           "None ordered comparison.\n" if n else "\nNo differences.\n")

    srs = by_kind(supp)
    ran = [r for r in srs if "reference_supplement" in r]
    md += "\n### Supplementary histories (PROTOCOL_DRAFT §9, added after the frozen run)\n\n"
    md += (f"The current reference was rerun on `histories/supplement_histories.json` for the {len(ran)} pairs that "
           "were REF-EQUIV-CHECKED on the frozen histories; the other pairs are unchanged. Combined outcome: "
           "REF-DIVERGE if the supplement diverges, otherwise the frozen-history outcome.\n\n")
    md += "Agreement with the combined reference outcome:\n\n" + table(srs, lambda r: r["agreement"], KINDS)
    md += ("\nOutcome on the supplementary histories alone (rerun pairs only):\n\n"
           + table(ran, lambda r: r["reference_supplement"]["outcome"], KINDS))
    md += "\n| pair | Explorer | agreement (frozen histories) | agreement (combined) | supplementary histories |\n|---|---|---|---|---|\n"
    m = 0
    for p in sorted(supp):
        s, c = supp[p], cur[p]
        rs_ = s.get("reference_supplement", {})
        if s["agreement"] != c["agreement"] or rs_.get("outcome", "REF-EQUIV-CHECKED") not in ("REF-EQUIV-CHECKED", "REF-DIVERGE"):
            m += 1
            md += f"| {p} | {verdict(s)} | {c['agreement']} | {s['agreement']} | {rs_['outcome']} ({rs_['n_histories']}) |\n"
    md += f"\n{m} pairs listed (agreement changed, or the supplement was not fully supported).\n"

    nrs = by_kind(new)
    md += "\n### Binding contract (BINDING_DECISION_2026-09-14.md, whisoo)\n\n"
    md += ("Selectors, tags, device IDs/categories, device counts and quantifiers do not decide the verdict (B1, B2); with "
           "several binding device sets for one service the pair is equal if some selector assignment is equal (B5). "
           "Both tools changed; pairs, histories, budget and start times are the frozen ones "
           "(`run_binding_v1.py`, `run_binding_b5.py`, `runs/e2_run.binding-final.jsonl`). Reference outcomes combine the "
           "frozen and supplementary histories as above. This is an evaluation-contract decision; it is not counted as "
           "an Explorer improvement (decided pairs stay at "
           f"{sum(decided(verdict(r)) for r in nrs)}/{len(nrs)}).\n\n")
    md += "Explorer verdicts:\n\n" + table(nrs, verdict, KINDS)
    md += "\nAgreement:\n\n" + table(nrs, lambda r: r["agreement"], KINDS)
    md += "\nReference outcome:\n\n" + table(nrs, lambda r: r["reference"]["outcome"], KINDS)
    md += "\nFault pairs, agreement by fault family:\n\n" + family_table(new, lambda r: r["agreement"])
    scope = sorted(p for p, r in new.items() if r["kind"] == "fault" and verdict(supp[p]) == "DIVERGE"
                   and verdict(r) == "EQUIV")
    md += ("\nFault pairs that differ only in which bound device is targeted, equal under the contract: "
           + ", ".join(f"`{p}` ({new[p]['family']})" for p in scope) + ".\n")
    md += "\n| pair | Explorer before → contract | reference before → contract | agreement before → contract | why |\n|---|---|---|---|---|\n"
    n = 0
    for p in sorted(new):
        o, r = supp[p], new[p]
        b = (verdict(o), o["reference"]["outcome"], o["agreement"])
        a = (verdict(r), r["reference"]["outcome"], r["agreement"])
        if b == a:
            continue
        n += 1
        sa = r["explorer"].get("selector_assignment") or r["reference"].get("selector_assignment") or {}
        why = ("B5 selector assignment" if sa.get("equiv_assignment") else
               "B5: some assignments not decidable on the reference (history lacks a device only the JoI reads)"
               if r["reference"].get("note", "").startswith("B5") else
               "load: see explorer_note" if r.get("explorer_note") and b[0] != a[0] else "B1/B2 selector")
        md += f"| {p} | {b[0]} → {a[0]} | {b[1]} → {a[1]} | {b[2]} → {a[2]} | {why} |\n"
    md += f"\n{n} pairs differ from the frozen-history-plus-supplement results. "
    md += ("C05/fault2 and C05/fault3 were TIMEOUT in the combined run under CPU load and were rerun alone: REFUSED at the "
           "state cap, as in the frozen run (`explorer_under_load` keeps the loaded result).\n")

    (HERE / "RESULTS.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
