"""Aggregate results/raw into a CSV, a summary table and one chart."""
import json, os, glob, csv, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw")
RES = os.path.join(ROOT, "results")

FIELDS = ["model", "strategy", "task_id", "rep", "n_calls", "prompt_tokens",
          "completion_tokens", "total_tokens", "duration_s", "eval_duration_s",
          "parsed", "collected", "passed", "failed", "errors",
          "line_coverage", "branch_coverage", "no_module_import", "error"]


def load():
    rows = []
    for f in sorted(glob.glob(os.path.join(RAW, "*.json"))):
        r = json.load(open(f))
        rows.append({k: r.get(k) for k in FIELDS})
    return rows


def main():
    rows = load()
    if not rows:
        print("no results yet"); return

    with open(os.path.join(RES, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)

    groups = {}
    for r in rows:
        groups.setdefault((r["model"], r["strategy"]), []).append(r)

    print(f"\n{'model':<22}{'strategy':<18}{'n':>4}{'tokens':>9}{'sec':>8}"
          f"{'branch%':>9}{'exec%':>8}{'passrate%':>11}")
    print("-" * 89)
    summary = []
    for (m, s), g in sorted(groups.items()):
        n = len(g)
        toks = [r["total_tokens"] for r in g if r["total_tokens"]]
        secs = [r["duration_s"] for r in g if r["duration_s"]]
        covs = [r["branch_coverage"] for r in g if r["branch_coverage"] is not None]
        execd = [r for r in g if r["collected"]]
        tp = sum(r["passed"] or 0 for r in g); tc = sum(r["collected"] or 0 for r in g)
        own = sum(1 for r in g if r.get("no_module_import"))
        row = {
            "model": m, "strategy": s, "n": n,
            "median_tokens": int(st.median(toks)) if toks else 0,
            "median_seconds": round(st.median(secs), 1) if secs else 0,
            "mean_branch_coverage": round(st.mean(covs), 1) if covs else 0,
            "pct_executable": round(100 * len(execd) / n, 1),
            "test_pass_rate": round(100 * tp / tc, 1) if tc else 0,
            "pct_no_import": round(100 * own / n, 1),
        }
        summary.append(row)
        print(f"{m:<22}{s:<18}{n:>4}{row['median_tokens']:>9}{row['median_seconds']:>8}"
              f"{row['mean_branch_coverage']:>9}{row['pct_executable']:>8}"
              f"{row['test_pass_rate']:>11}{row['pct_no_import']:>11}")

    json.dump(summary, open(os.path.join(RES, "summary.json"), "w"), indent=2)

    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 5))
        marks = {}
        for row in summary:
            marks.setdefault(row["model"], []).append(row)
        for model, rs in marks.items():
            ax.scatter([r["median_tokens"] for r in rs],
                       [r["mean_branch_coverage"] for r in rs], s=90, label=model)
            for r in rs:
                ax.annotate(r["strategy"], (r["median_tokens"], r["mean_branch_coverage"]),
                            textcoords="offset points", xytext=(6, 5), fontsize=9)
        ax.set_xlabel("cost: median total tokens per problem")
        ax.set_ylabel("capability: mean branch coverage (%)")
        ax.set_title("Cost against capability in small language models")
        ax.grid(alpha=.3); ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(RES, "coverage_vs_tokens.png"), dpi=150)
        print("\nwrote results/coverage_vs_tokens.png")
    except ImportError:
        print("\n(matplotlib not installed, skipping chart)")


if __name__ == "__main__":
    main()
