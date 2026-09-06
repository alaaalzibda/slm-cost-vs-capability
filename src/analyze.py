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
        from matplotlib.ticker import ScalarFormatter

        SHORT = {"zero_shot": "zero-shot", "chain_of_thought": "chain-of-thought",
                 "least_to_most": "least-to-most"}
        OFF = {"zero_shot": (0, 10), "chain_of_thought": (0, -16), "least_to_most": (0, 10)}
        PALETTE = ["#2E7D32", "#1565C0", "#EF6C00", "#6A1B9A", "#00838F"]
        ORDER = {"zero_shot": 0, "chain_of_thought": 1, "least_to_most": 2}

        models = sorted({r["model"] for r in summary})
        colours = {m: PALETTE[i % len(PALETTE)] for i, m in enumerate(models)}
        handles = []

        fig, ax = plt.subplots(figsize=(8.5, 5.5))
        for model in models:
            pts = sorted([r for r in summary if r["model"] == model],
                         key=lambda r: ORDER.get(r["strategy"], 99))
            xs = [r["median_tokens"] for r in pts]
            ys = [r["pct_executable"] for r in pts]
            ax.plot(xs, ys, color=colours[model], alpha=.35, lw=1.2, zorder=1)
            sc = ax.scatter(xs, ys, s=[40 + r["n"] * 3 for r in pts],
                            color=colours[model], zorder=3,
                            edgecolor="white", linewidth=1.2)
            handles.append((sc, model))
            lean = 1 if models.index(model) % 2 == 0 else -1
            for r in pts:
                dx, dy = OFF.get(r["strategy"], (0, 10))
                ax.annotate(SHORT.get(r["strategy"], r["strategy"]),
                            (r["median_tokens"], r["pct_executable"]),
                            textcoords="offset points",
                            xytext=(dx + 26 * lean, dy * (1 if lean > 0 else 1.6)),
                            fontsize=8.5, ha="center", color=colours[model])

        if max(r["median_tokens"] for r in summary) / max(1, min(
                r["median_tokens"] for r in summary if r["median_tokens"])) > 5:
            ax.set_xscale("log")
            # Default log ticks label only decades, which hides the range where
            # the strategies actually differ. Place ticks on the real values.
            lo = min(r["median_tokens"] for r in summary if r["median_tokens"])
            hi = max(r["median_tokens"] for r in summary)
            ticks = [t for t in (400, 600, 800, 1000, 1500, 2000, 3000, 5000,
                                 8000, 10000, 15000, 20000)
                     if lo * 0.85 <= t <= hi * 1.2]
            if ticks:
                ax.set_xticks(ticks)
                ax.set_xticks([], minor=True)
            ax.get_xaxis().set_major_formatter(ScalarFormatter())
            ax.set_xlabel("cost: median total tokens per problem (log scale)")
        else:
            ax.set_xlabel("cost: median total tokens per problem")

        ax.set_ylabel("capability: % of runs producing an executable test suite")
        ax.set_title("Cost against capability in small language models")
        ax.set_ylim(-12, 108)
        ax.grid(alpha=.25)
        ax.legend([h for h, _ in handles], [m for _, m in handles],
                  title="model", loc="center right", frameon=True)
        fig.text(.5, .005, "Marker size is the number of runs behind each point.",
                 ha="center", fontsize=7.5, color="#666")
        fig.tight_layout(rect=[0, .03, 1, 1])
        fig.savefig(os.path.join(RES, "cost_vs_capability.png"), dpi=160)
        print("\nwrote results/cost_vs_capability.png")
    except ImportError:
        print("\n(matplotlib not installed, skipping chart)")


if __name__ == "__main__":
    main()
