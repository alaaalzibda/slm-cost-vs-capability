"""Run the study: every (model, strategy, problem) combination, once each.

Results stream to results/raw/*.json so an interrupted run can be resumed;
already-completed cells are skipped.
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(__file__))
from strategies import STRATEGIES, SYSTEM
from backends import get_backend
from evaluate import extract_code, evaluate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw")


def load_problems(n=None):
    path = os.path.join(ROOT, "data", "problems.jsonl")
    rows = [json.loads(l) for l in open(path)]
    return rows[:n] if n else rows


def cell_path(model, strategy, task_id, rep):
    safe = task_id.replace("/", "_")
    return os.path.join(RAW, f"{model.replace(':','-')}__{strategy}__{safe}__r{rep}.json")


def run_cell(backend, model, strategy, problem, rep=0):
    steps = STRATEGIES[strategy](problem)
    prompt_tokens = completion_tokens = 0
    duration = eval_duration = 0.0
    previous = None
    text = ""

    for step in steps:
        prompt = step["prompt"]
        if step.get("uses_previous"):
            prompt = prompt.format(previous=previous or "")
        out = backend.complete(prompt, system=SYSTEM if step.get("expects_code", True) else None)
        prompt_tokens += out["prompt_tokens"]
        completion_tokens += out["completion_tokens"]
        duration += out["duration_s"]
        eval_duration += out.get("eval_duration_s", 0.0)
        previous = out["text"]
        text = out["text"]

    code = extract_code(text)
    ev = evaluate(problem, code)

    return {
        "model": model,
        "strategy": strategy,
        "task_id": problem["task_id"],
        "rep": rep,
        "n_calls": len(steps),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "duration_s": round(duration, 3),
        "eval_duration_s": round(eval_duration, 3),
        **ev,
        "generated_code": code,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--strategies", nargs="+", default=list(STRATEGIES))
    ap.add_argument("--backend", default="ollama", choices=["ollama", "mock"])
    ap.add_argument("--limit", type=int, default=None, help="use only the first N problems")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--repeats", type=int, default=1,
                    help="samples per cell; >1 gives you a spread instead of a point")
    args = ap.parse_args()

    os.makedirs(RAW, exist_ok=True)
    problems = load_problems(args.limit)
    total = len(args.models) * len(args.strategies) * len(problems) * args.repeats
    done = 0

    for model in args.models:
        backend = get_backend(args.backend, model, host=args.host) \
            if args.backend == "ollama" else get_backend(args.backend, model)
        for strategy in args.strategies:
            for p in problems:
              for rep in range(args.repeats):
                done += 1
                out = cell_path(model, strategy, p["task_id"], rep)
                if os.path.exists(out):
                    prev = json.load(open(out))
                    # A cell that never reached the model (network/404/timeout)
                    # is not complete; retry it instead of freezing the failure in.
                    if prev.get("total_tokens"):
                        print(f"[{done}/{total}] skip {model} {strategy} {p['task_id']} r{rep}")
                        continue
                    print(f"[{done}/{total}] retry {model} {strategy} {p['task_id']} r{rep}")
                print(f"[{done}/{total}] {model} {strategy} {p['task_id']} r{rep} ...", flush=True)
                try:
                    # vary the seed per repeat so repeats are genuinely independent samples
                    backend.seed = 7 + rep * 1000
                    rec = run_cell(backend, model, strategy, p, rep)
                except Exception as e:
                    rec = {"model": model, "strategy": strategy, "task_id": p["task_id"],
                           "rep": rep, "error": f"{type(e).__name__}: {e}", "parsed": False}
                json.dump(rec, open(out, "w"), indent=2)
                cov = rec.get("branch_coverage")
                print(f"    tokens={rec.get('total_tokens')} "
                      f"branch_cov={cov} passed={rec.get('passed')} "
                      f"failed={rec.get('failed')}")


if __name__ == "__main__":
    main()
