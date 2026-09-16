#!/usr/bin/env python3
"""Fig2/Table1 — aggregate judge verdicts: flip rate per rewrite type and per band, split into
deploy->reject and reject->deploy, identity (same program, repeated) flip rate under the same
valid-pair rule, and 95% intervals from a bootstrap that resamples seed programs (cluster = seed).

Reads runs/<judge>/verdicts.json; writes results/summary.json, results/RESULTS.md, results/fig2.{png,pdf}.
"""
import json
import os
import random
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BOOT = 2000
BAND_ORDER = ["spelling", "logic", "temporal"]
TYPE_LABEL = OrderedDict([
    ("var_rename", ("VAR", "rename a variable")),
    ("comparator_flip", ("CMP", "mirror a comparison (x >= 26 -> 26 <= x)")),
    ("time_unit", ("UNIT", "change the time unit (3 MIN -> 180 SEC)")),
    ("exists_spelling", ("GRP", "respell a condition over a group of devices")),
    ("branch_swap", ("BR", "negate the guard and swap the branches")),
    ("delay_split", ("DLY", "split one delay into two")),
    ("loop_unroll", ("UNR", "unroll a counted periodic loop")),
    ("phase_flag", ("PHS", "integer phase -> boolean flag with shared tail")),
])
ABBR = {k: v[0] for k, v in TYPE_LABEL.items()}
CONTROL_ABBR = "CTL"
BAND_LABEL = {"spelling": "Spelling", "logic": "Logic", "temporal": "Temporal structure"}


def rate(num, den):
    return num / den if den else float("nan")


def boot_ci(items, key_fn, stat_fn, seed=0):
    """items grouped by seed id; stat_fn(list of items) -> rate. Percentile bootstrap over seeds."""
    by_seed = defaultdict(list)
    for it in items:
        by_seed[key_fn(it)].append(it)
    seeds = list(by_seed)
    if not seeds:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    vals = []
    for _ in range(BOOT):
        sample = [x for s in (rng.choice(seeds) for _ in seeds) for x in by_seed[s]]
        vals.append(stat_fn(sample))
    vals.sort()
    return (vals[int(0.025 * BOOT)], vals[int(0.975 * BOOT) - 1])


def summarize_accepted(rows):
    """Primary view: restrict to the pairs whose ORIGINAL this judge accepted, then ask how often it
    rejects the behavior-preserving rewrite of that same program. The conditioning uses only this
    judge's own first-pass verdict, so the measured quantity is the one a deployment gate faces:
    having cleared a program, does the gate block an equivalent rewrite of it? The control re-asks
    the identical accepted program."""
    def stats(rs):
        acc = [r for r in rs if r["base"][0] is True and r["variant"] is not None]
        rej = [r for r in acc if r["variant"] is False]
        seen, ctl = set(), []
        for r in rs:
            if r["id"] in seen or r["base"][0] is not True or r["base"][1] is None:
                continue
            seen.add(r["id"])
            ctl.append(r)
        ctl_rej = [r for r in ctl if r["base"][1] is False]
        return {"pairs": len(acc), "rejected": len(rej), "rate": rate(len(rej), len(acc)),
                "control_seeds": len(ctl), "control_rejected": len(ctl_rej),
                "control_rate": rate(len(ctl_rej), len(ctl))}

    def with_ci(rs):
        x = stats(rs)
        x["ci95"] = boot_ci(rs, lambda r: r["id"], lambda y: stats(y)["rate"])
        x["control_ci95"] = boot_ci(rs, lambda r: r["id"], lambda y: stats(y)["control_rate"])
        return x

    out = {"overall": with_ci(rows), "by_band": {}, "by_type": {}}
    for b in BAND_ORDER:
        rs = [r for r in rows if r["band"] == b]
        if rs:
            out["by_band"][b] = with_ci(rs)
    for t in TYPE_LABEL:
        rs = [r for r in rows if r["type"] == t]
        if rs:
            out["by_type"][t] = with_ci(rs)
    return out


def summarize(rows):
    """rows: verdict rows of one judge. Returns per-type / per-band / overall stats."""
    def pair_stats(rs):
        valid = [r for r in rs if r["base"][0] is not None and r["variant"] is not None]
        flips = [r for r in valid if r["base"][0] != r["variant"]]
        d2r = sum(1 for r in flips if r["base"][0] is True)
        return {"pairs": len(rs), "valid": len(valid), "flips": len(flips), "deploy_to_reject": d2r,
                "reject_to_deploy": len(flips) - d2r, "flip_rate": rate(len(flips), len(valid)),
                "invalid": len(rs) - len(valid),
                "base_accept_rate": rate(sum(1 for r in valid if r["base"][0] is True), len(valid))}

    def ident_stats(rs):
        # one identity pair per seed: base rep 0 vs rep 1, same valid-pair rule
        seen, ids = set(), []
        for r in rs:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            ids.append(r)
        valid = [r for r in ids if r["base"][0] is not None and r["base"][1] is not None]
        flips = [r for r in valid if r["base"][0] != r["base"][1]]
        three = [r for r in ids if None not in r["base"]]
        dis3 = [r for r in three if len(set(r["base"])) > 1]
        return {"seeds": len(ids), "valid": len(valid), "flips": len(flips), "flip_rate": rate(len(flips), len(valid)),
                "any_disagreement_in_3": len(dis3), "any_disagreement_rate_3": rate(len(dis3), len(three))}

    def with_ci(rs):
        s = pair_stats(rs)
        s["ci95"] = boot_ci(rs, lambda r: r["id"], lambda x: pair_stats(x)["flip_rate"])
        i = ident_stats(rs)
        i["ci95"] = boot_ci(rs, lambda r: r["id"], lambda x: ident_stats(x)["flip_rate"])
        s["identity"] = i
        return s

    out = {"overall": with_ci(rows), "by_band": {}, "by_type": {}}
    for b in BAND_ORDER:
        rs = [r for r in rows if r["band"] == b]
        if rs:
            out["by_band"][b] = with_ci(rs)
    for t in TYPE_LABEL:
        rs = [r for r in rows if r["type"] == t]
        if rs:
            out["by_type"][t] = with_ci(rs)
    return out


def pct(x):
    return "n/a" if x != x else f"{100 * x:.1f}%"


def ci_str(ci):
    return "n/a" if ci[0] != ci[0] else f"[{100 * ci[0]:.1f}, {100 * ci[1]:.1f}]"


BAND_NAME = {"spelling": "Notation", "logic": "Logic", "temporal": "Temporal"}
COMMON_MIN_ACCEPTS = 2      # of the 3 identical asks, how many must say "correct"


def common_summary(judges):
    """The design the manuscript reports.

    Step 1 asks every original program three times, identically, and counts how often a judge
    disagrees with itself.  That number is unconditional -- it is over all seed programs, with no
    selection at all -- so it is reported on its own rather than as a row of the rewrite table.

    Step 2 keeps the programs that *every* judge called correct in at least COMMON_MIN_ACCEPTS of
    its three asks.  One shared set of programs, so one shared denominator per row: the judges
    become directly comparable and the table needs no per-judge counts.  These are also the
    programs whose natural-language command is least ambiguous, since three different judges
    agreed on them, which removes the reading that a rejection just reflects a vague command.

    Step 3 asks each judge about the certified-equivalent rewrites of those programs.  Every
    rejection here is a judge contradicting a verdict it reached reliably, on a program that
    provably does the same thing.
    """
    base, types = {}, {}
    for j, d in judges.items():
        base[j] = {}
        for r in d["rows"]:
            base[j].setdefault(r["id"], r["base"])
            types.setdefault(r["id"], set()).add((r["type"], r["band"]))

    def accepts(b):
        return sum(1 for v in b if v is True)

    seeds = sorted(set.intersection(*(set(base[j]) for j in judges)))
    common = [i for i in seeds
              if all(accepts(base[j][i]) >= COMMON_MIN_ACCEPTS for j in judges)]

    out = {"seeds_total": len(seeds), "common_seeds": common,
           "min_accepts": COMMON_MIN_ACCEPTS, "self_disagreement": {}, "judges": {}}
    for j in judges:
        split = [i for i in seeds if 0 < accepts(base[j][i]) < 3]
        out["self_disagreement"][j] = {
            "seeds": len(seeds), "disagreed": len(split), "rate": rate(len(split), len(seeds)),
            "ci95": boot_ci(seeds, lambda i: i,
                            lambda ids: rate(sum(1 for i in ids if 0 < accepts(base[j][i]) < 3),
                                             len(ids)))}

    keep = set(common)
    for j, d in judges.items():
        rows = [r for r in d["rows"] if r["id"] in keep and r["variant"] is not None]

        def stat(rs, f):
            sel = [r for r in rs if f(r)]
            k = sum(1 for r in sel if r["variant"] is False)
            return {"pairs": len(sel), "rejected": k, "rate": rate(k, len(sel))}

        def with_ci(f):
            x = stat(rows, f)
            x["ci95"] = boot_ci(rows, lambda r: r["id"],
                                lambda rs: stat(rs, f)["rate"])
            return x

        e = {"overall": with_ci(lambda r: True), "by_band": {}, "by_type": {}}
        for b in BAND_ORDER:
            e["by_band"][b] = with_ci(lambda r, b=b: r["band"] == b)
        for t in TYPE_LABEL:
            e["by_type"][t] = with_ci(lambda r, t=t: r["type"] == t)
        out["judges"][j] = {"model": d["meta"]["config"]["model"], **e}
    return out


def main():
    total_pairs = len(json.load(open(os.path.join(HERE, "rewrites", "verified_pairs.json")))["pairs"])
    judges = OrderedDict()
    for j in ("qwen", "gpt", "claude"):
        f = os.path.join(HERE, "runs", j, "verdicts.json")
        if not os.path.exists(f):
            continue
        d = json.load(open(f))
        if len(d["rows"]) < total_pairs:   # a smoke test or an unfinished arm: don't report it
            print(f"skipping {j}: {len(d['rows'])}/{total_pairs} pairs")
            continue
        judges[j] = d
    res_dir = os.path.join(HERE, "results")
    os.makedirs(res_dir, exist_ok=True)
    summary = {j: {"meta": d["meta"], "accepted": summarize_accepted(d["rows"]),
                   "stats": summarize(d["rows"])} for j, d in judges.items()}
    json.dump(summary, open(os.path.join(res_dir, "summary.json"), "w"), ensure_ascii=False, indent=1)
    common = common_summary(judges)
    json.dump(common, open(os.path.join(res_dir, "summary_common.json"), "w"),
              ensure_ascii=False, indent=1)
    print("common set: %d of %d seed programs accepted by every judge in >=%d of 3 asks"
          % (len(common["common_seeds"]), common["seeds_total"], common["min_accepts"]))

    lines = ["# Fig2 / Table1 — judge verdict consistency on behavior-preserving rewrites", ""]
    lines.append("Seeds: E3 EQUIV-FIXPOINT programs (confirmed IR + binding). Every rewrite was re-checked by the frozen "
                 "E3 evaluator and is EQUIV-FIXPOINT against the confirmed IR (rewrites/verified_pairs.json). "
                 "Judge input: the natural-language command and the program; base and rewrite in separate calls. "
                 "Identity: the base program judged again with the same prompt (rep 0 vs rep 1). "
                 "Flip = J(base) != J(rewrite) over valid pairs (both parsed). 95% CI: percentile bootstrap over seed programs "
                 f"({BOOT} resamples).")
    lines.append("")
    lines.append("## Primary view: rewrites of programs the judge itself accepted")
    lines.append("")
    lines.append("Each judge is conditioned on its own first-pass verdict. Of the pairs whose original "
                 "this judge accepted, the table reports how often it rejected the behavior-preserving "
                 "rewrite. The control re-asks the identical accepted program.")
    lines.append("")
    lines.append("| judge | accepted pairs | rewrite rejected | rate | 95% CI | control seeds | control rejected | control rate |")
    lines.append("|---|---:|---:|---:|---|---:|---:|---:|")
    for j, s in summary.items():
        a = s["accepted"]["overall"]
        lines.append("| `" + s["meta"]["config"]["model"] + "` | %d | %d | %s | %s | %d | %d | %s |" % (
            a["pairs"], a["rejected"], pct(a["rate"]), ci_str(a["ci95"]),
            a["control_seeds"], a["control_rejected"], pct(a["control_rate"])))
    lines.append("")
    for j, s in summary.items():
        a = s["accepted"]
        band_of = {r["type"]: r["band"] for r in judges[j]["rows"]}
        lines.append("**" + s["meta"]["config"]["model"] + "**, by rewrite type:")
        lines.append("")
        lines.append("| | rewrite | accepted pairs | rejected | rate | 95% CI |")
        lines.append("|---|---|---:|---:|---:|---|")
        for b in BAND_ORDER:
            for t, (ab, lab) in TYPE_LABEL.items():
                if t in a["by_type"] and band_of.get(t) == b:
                    x = a["by_type"][t]
                    lines.append("| %s | %s | %d | %d | %s | %s |" % (
                        ab, lab, x["pairs"], x["rejected"], pct(x["rate"]), ci_str(x["ci95"])))
        lines.append("")
    lines.append("## Secondary view: all pairs, flips in either direction")
    lines.append("")
    for j, s in summary.items():
        m, st = s["meta"], s["stats"]
        cfg = m["config"]
        if cfg["backend"] == "vllm":
            desc = f", temperature {cfg['temperature']}, thinking off, seed {cfg['seed']}, budget {cfg['max_tokens']}+{cfg['answer_tokens']}"
        elif cfg["backend"] == "anthropic":
            desc = f", adaptive thinking, effort {cfg['effort']}"
        else:
            desc = f", reasoning_effort {cfg['reasoning_effort']}, seed {cfg['seed']}"
        lines.append(f"## {j}: `{cfg['model']}`" + desc)
        lines.append("")
        o = st["overall"]
        lines.append("| | pairs | valid | flip | deploy→reject | reject→deploy | flip rate | 95% CI | identity flip (n) | identity rate | identity CI |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|")
        def row(label, x):
            i = x["identity"]
            return (f"| {label} | {x['pairs']} | {x['valid']} | {x['flips']} | {x['deploy_to_reject']} | {x['reject_to_deploy']} | "
                    f"{pct(x['flip_rate'])} | {ci_str(x['ci95'])} | {i['flips']}/{i['valid']} | {pct(i['flip_rate'])} | {ci_str(i['ci95'])} |")
        lines.append(row("**all rewrites**", o))
        for b in BAND_ORDER:
            if b in st["by_band"]:
                lines.append(row(f"**{BAND_LABEL[b]}**", st["by_band"][b]))
        for t, (ab, lab) in TYPE_LABEL.items():
            if t in st["by_type"]:
                lines.append(row(f"{TYPE_LABEL[t][0]} — {TYPE_LABEL[t][1]}", st["by_type"][t]))
        lines.append("")
        lines.append(f"Base programs judged deployable: {pct(o['base_accept_rate'])} of valid pairs. "
                     f"Invalid (unparsed/error) pairs: {o['invalid']}. "
                     f"Seeds whose three identity repeats disagree at all: {o['identity']['any_disagreement_in_3']}/{o['identity']['seeds']}.")
        lines.append("")
    open(os.path.join(res_dir, "RESULTS.md"), "w").write("\n".join(lines))
    print("\n".join(lines))
    # Fig.2 is not in the manuscript (09-16). The figure it drew is kept, unregenerated, in
    # results/superseded/ with the abbreviated labels it was built with; plot() is left here
    # only so that decision can be reversed without rewriting it.
    if os.environ.get("MOTIVATION_DRAW_FIG2"):
        plot(summary, res_dir)


def plot(summary, res_dir):
    """Vertical grouped bars: one group per rewrite type, one bar per judge, control group first.

    No error bars: the tick label carries the pair count instead, and the 95% intervals are in
    Table 1 (results/RESULTS.md). The counts differ slightly between judges because each judge is
    conditioned on the programs it accepted, so the tick shows the range.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    band_of = {}
    for j in summary:
        for r in json.load(open(os.path.join(HERE, "runs", j, "verdicts.json")))["rows"]:
            band_of[r["type"]] = r["band"]
    groups = [(CONTROL_ABBR, None, None)]
    for b in BAND_ORDER:
        for t in TYPE_LABEL:
            if band_of.get(t) == b:
                groups.append((ABBR[t], t, b))

    def counts(t):
        key = "control_seeds" if t is None else "pairs"
        ns = [sm["accepted"]["overall"][key] if t is None else sm["accepted"]["by_type"][t][key]
              for sm in summary.values() if t is None or t in sm["accepted"]["by_type"]]
        return (str(ns[0]) if min(ns) == max(ns) else f"{min(ns)}-{max(ns)}") if ns else ""

    colors = {"qwen": "#4C72B0", "gpt": "#DD8452", "claude": "#55A868"}
    nj = len(summary)
    w = 0.8 / nj
    fig, ax = plt.subplots(figsize=(7.0, 2.7))
    for k, (j, sm) in enumerate(summary.items()):
        a = sm["accepted"]
        xs, ys = [], []
        for i, (ab, t, b) in enumerate(groups):
            x = a["overall"] if t is None else a["by_type"].get(t)
            if x is None:
                continue
            xs.append(i + (k - (nj - 1) / 2) * w)
            ys.append(100 * (x["control_rate"] if t is None else x["rate"]))
        ax.bar(xs, ys, width=w * 0.88, color=colors.get(j), zorder=3,
               label=sm["meta"]["config"]["model"].split("/")[-1])
        # A measured zero is not a missing bar: mark it so the reader can tell them apart.
        for x, y in zip(xs, ys):
            if y == 0:
                ax.plot([x - w * 0.44, x + w * 0.44], [0, 0], color=colors.get(j), lw=1.6,
                        solid_capstyle="butt", zorder=4)
                ax.text(x, 1.5, "0", ha="center", va="bottom", fontsize=6.5,
                        color=colors.get(j), zorder=4)

    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([ab for ab, t, b in groups], fontsize=9)
    ax.set_ylabel("verdict reversal (%)", fontsize=8.5)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_ylim(0, 92)
    ax.grid(axis="y", lw=0.4, alpha=0.45, zorder=0)
    ax.axvline(0.5, color="0.35", lw=0.7)
    prev, start = None, 1
    for i, (ab, t, b) in enumerate(groups[1:], start=1):
        if prev is not None and b != prev:
            ax.axvline(i - 0.5, color="0.7", lw=0.6, ls=":")
            ax.text((start + i - 1) / 2, 89, BAND_LABEL[prev], ha="center", va="top",
                    fontsize=7.5, color="0.35")
            start = i
        prev = b
    ax.text((start + len(groups) - 1) / 2, 89, BAND_LABEL[prev], ha="center", va="top",
            fontsize=7.5, color="0.35")
    ax.text(0, 89, "control", ha="center", va="top", fontsize=7.5, color="0.35")
    ax.legend(fontsize=7.5, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0),
              frameon=False, columnspacing=1.4)
    fig.tight_layout()
    fig.savefig(os.path.join(res_dir, "fig2.png"), dpi=300)
    fig.savefig(os.path.join(res_dir, "fig2.pdf"))
    print("wrote", os.path.join(res_dir, "fig2.png"))


if __name__ == "__main__":
    main()
