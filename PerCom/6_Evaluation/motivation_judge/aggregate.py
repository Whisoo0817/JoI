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
    ("var_rename", "rename a variable"),
    ("comparator_flip", "mirror a comparison (x >= 26 -> 26 <= x)"),
    ("time_unit", "change the time unit (3 MIN -> 180 SEC)"),
    ("exists_spelling", "respell 'at least one device' (==| -> any)"),
    ("branch_swap", "negate the guard and swap the branches"),
    ("delay_split", "split one delay into two"),
    ("loop_unroll", "unroll a counted periodic loop"),
    ("phase_flag", "integer phase -> boolean flag with shared tail"),
])
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
    summary = {j: {"meta": d["meta"], "stats": summarize(d["rows"])} for j, d in judges.items()}
    json.dump(summary, open(os.path.join(res_dir, "summary.json"), "w"), ensure_ascii=False, indent=1)

    lines = ["# Fig2 / Table1 — judge verdict consistency on behavior-preserving rewrites", ""]
    lines.append("Seeds: E3 EQUIV-FIXPOINT programs (confirmed IR + binding). Every rewrite was re-checked by the frozen "
                 "E3 evaluator and is EQUIV-FIXPOINT against the confirmed IR (rewrites/verified_pairs.json). "
                 "Judge input: the natural-language command and the program; base and rewrite in separate calls. "
                 "Identity: the base program judged again with the same prompt (rep 0 vs rep 1). "
                 "Flip = J(base) != J(rewrite) over valid pairs (both parsed). 95% CI: percentile bootstrap over seed programs "
                 f"({BOOT} resamples).")
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
        for t, lab in TYPE_LABEL.items():
            if t in st["by_type"]:
                lines.append(row(f"{lab} (`{t}`)", st["by_type"][t]))
        lines.append("")
        lines.append(f"Base programs judged deployable: {pct(o['base_accept_rate'])} of valid pairs. "
                     f"Invalid (unparsed/error) pairs: {o['invalid']}. "
                     f"Seeds whose three identity repeats disagree at all: {o['identity']['any_disagreement_in_3']}/{o['identity']['seeds']}.")
        lines.append("")
    open(os.path.join(res_dir, "RESULTS.md"), "w").write("\n".join(lines))
    print("\n".join(lines))
    plot(summary, res_dir)


def plot(summary, res_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = [("identity", "same program, judged twice", None)]
    # type -> band from the verdict rows' band field
    band_of = {}
    for s in summary.values():
        for t, x in s["stats"]["by_type"].items():
            band_of.setdefault(t, None)
    for j in summary:
        for r in json.load(open(os.path.join(HERE, "runs", j, "verdicts.json")))["rows"]:
            band_of[r["type"]] = r["band"]
    for b in BAND_ORDER:
        for t, lab in TYPE_LABEL.items():
            if band_of.get(t) == b:
                rows.append((t, lab, b))
    n = len(rows)
    nj = len(summary)
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * n + 1.2))
    colors = {"qwen": "#4C72B0", "gpt": "#DD8452", "claude": "#55A868"}
    h = 0.8 / nj
    for k, (j, s) in enumerate(summary.items()):
        ys, xs, lo, hi = [], [], [], []
        for i, (t, lab, b) in enumerate(rows):
            if t == "identity":
                x = s["stats"]["overall"]["identity"]
            else:
                x = s["stats"]["by_type"].get(t)
                if x is None:
                    continue
            ys.append(i + (k - (nj - 1) / 2) * h)
            xs.append(100 * x["flip_rate"])
            lo.append(100 * (x["flip_rate"] - x["ci95"][0]))
            hi.append(100 * (x["ci95"][1] - x["flip_rate"]))
        label = s["meta"]["config"]["model"].split("/")[-1]
        ax.barh(ys, xs, height=h * 0.9, color=colors.get(j, None), label=label,
                xerr=[lo, hi], error_kw={"elinewidth": 0.8, "capsize": 2})
    ax.set_yticks(range(n))
    ax.set_yticklabels([lab for _, lab, _ in rows], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("verdict flip rate on trace-equivalent pairs (%)", fontsize=9)
    # band separators
    prev = None
    for i, (t, lab, b) in enumerate(rows):
        if b != prev and i > 0:
            ax.axhline(i - 0.5, color="grey", lw=0.6, ls=":")
            ax.text(ax.get_xlim()[1] * 0.99, i - 0.45, BAND_LABEL[b], ha="right", va="top", fontsize=7, color="grey")
        prev = b
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(axis="x", lw=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(res_dir, "fig2.png"), dpi=200)
    fig.savefig(os.path.join(res_dir, "fig2.pdf"))
    print("wrote", os.path.join(res_dir, "fig2.png"))


if __name__ == "__main__":
    main()
