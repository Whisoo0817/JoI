"""Account for the fixed-aggregation full run without rewriting timer-v4."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RUN = "fixed-aggregation-v1-full"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = RESULTS / f"{RUN}.jsonl"
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    assert len(rows) == len({row["pair_id"] for row in rows}) == 142
    population = json.loads((HERE / "e2_population.json").read_text())
    excluded = {row["pair_id"]: row for row in population["exclusions"]}
    accounted = []
    for row in rows:
        ident, verdict = row["pair_id"], row["explorer"]["verdict"]
        if ident in excluded:
            category = excluded[ident]["category"]
        elif verdict in ("EQUIV", "DIVERGE"):
            category = "decided"
        elif ident.startswith("E1-099/"):
            category = "dynamic_arithmetic_deadline"
        elif ident.startswith("C07/"):
            category = "finite_product_state_explosion"
        else:
            category = "unexplained"
        accounted.append({**row, "category": category})

    categories = Counter(row["category"] for row in accounted)
    verdicts = Counter(row["explorer"]["verdict"] for row in accounted)
    old = [row for row in rows if row["previous"]["verdict"] in ("EQUIV", "DIVERGE")]
    changes = [row["pair_id"] for row in old
               if row["previous"]["verdict"] != row["explorer"]["verdict"]]
    false_equiv = [row["pair_id"] for row in rows
                   if row["explorer"]["verdict"] == "EQUIV"
                   and row["frozen_reference_outcome"] == "REF-DIVERGE"]
    assert len(old) == 104 and not changes and not false_equiv
    assert categories == Counter({"decided": 130,
                                  "dynamic_arithmetic_deadline": 5,
                                  "finite_product_state_explosion": 5,
                                  "invalid_syntax": 1,
                                  "invalid_service_mapping": 1})
    assert verdicts == Counter({"DIVERGE": 86, "EQUIV": 44,
                                "REFUSED": 7, "TIMEOUT": 5})

    summary = {
        "schema": "e2-fixed-aggregation-accounting-v1",
        "population": population,
        "category_counts": dict(categories),
        "verdict_counts": dict(verdicts),
        "existing_decision_changes": changes,
        "new_equiv_against_frozen_diverge": false_equiv,
        "rows": [{**row,
                  "previous": {k: v for k, v in row["previous"].items() if k != "witness"},
                  "explorer": {k: v for k, v in row["explorer"].items() if k != "witness"}}
                 for row in sorted(accounted, key=lambda value: value["pair_id"])],
        "witness_artifact": f"results/{RUN}.jsonl.gz",
        "source_jsonl_sha256": digest(source),
    }
    (RESULTS / f"{RUN}-classified.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    with (RESULTS / f"{RUN}.jsonl.gz").open("wb") as output:
        with gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0) as archive:
            archive.write(source.read_bytes())
    print(json.dumps({"category_counts": dict(categories),
                      "verdict_counts": dict(verdicts),
                      "classified_sha256": digest(RESULTS / f"{RUN}-classified.json"),
                      "witness_sha256": digest(RESULTS / f"{RUN}.jsonl.gz")}, indent=2))


if __name__ == "__main__":
    main()
