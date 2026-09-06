"""Execute generated tests against the canonical solution and measure coverage.

SAFETY: generated code is executed. Every run happens in a fresh temporary
directory, in a separate process, under a timeout. Do not run this on a
machine where an infinite loop or a stray file write would matter.
"""
import json, os, re, subprocess, sys, tempfile, shutil

FENCE = re.compile(r"```(?:python)?\s*(.*?)```", re.S)


def extract_code(text):
    """Pull the code out of a fenced block; fall back to the raw text."""
    blocks = FENCE.findall(text or "")
    if blocks:
        return max(blocks, key=len).strip()
    return (text or "").strip()


def evaluate(problem, test_code, timeout=120):
    """Run the tests, return execution outcome and branch coverage.

    Returns a dict. `parsed` is False when the generated tests are not even
    valid Python, which is itself one of the quality signals worth reporting.
    """
    result = {
        "parsed": False, "collected": 0, "passed": 0, "failed": 0, "errors": 0,
        "line_coverage": None, "branch_coverage": None,
        # True when the generated code never imports the module under test.
        # Observed cause is the model omitting the import line entirely, so its
        # tests reference an undefined name; it can also mean the model pasted
        # its own copy of the function. Either way nothing real was verified.
        "no_module_import": False,
        "error": None,
    }

    try:
        compile(test_code, "test_generated.py", "exec")
        result["parsed"] = True
    except SyntaxError as e:
        result["error"] = f"SyntaxError: {e}"
        return result

    work = tempfile.mkdtemp(prefix="slmtest_")
    try:
        solution = problem["prompt"] + problem["canonical_solution"]
        open(os.path.join(work, "solution.py"), "w").write(solution)
        open(os.path.join(work, "test_generated.py"), "w").write(test_code)

        cmd = [
            sys.executable, "-m", "pytest", "test_generated.py",
            "-q", "--no-header", "-p", "no:cacheprovider",
            "--cov=solution", "--cov-branch",
            "--cov-report=json:cov.json",
            "--json-report", "--json-report-file=report.json",
        ]
        try:
            proc = subprocess.run(
                cmd, cwd=work, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            result["error"] = "timeout"
            return result

        rp = os.path.join(work, "report.json")
        if os.path.exists(rp):
            rep = json.load(open(rp))
            summary = rep.get("summary", {})
            result["collected"] = summary.get("total", 0)
            result["passed"] = summary.get("passed", 0)
            result["failed"] = summary.get("failed", 0)
            result["errors"] = summary.get("error", 0)

        cp = os.path.join(work, "cov.json")
        found_module = False
        if os.path.exists(cp):
            cov = json.load(open(cp))
            files = cov.get("files", {})
            key = next((k for k in files if k.endswith("solution.py")), None)
            if key:
                found_module = True
                s = files[key]["summary"]
                result["line_coverage"] = s.get("percent_covered")
                cb, tb = s.get("covered_branches"), s.get("num_branches")
                if tb:
                    result["branch_coverage"] = round(100.0 * cb / tb, 2)
                else:
                    result["branch_coverage"] = result["line_coverage"]

        if not found_module and result["collected"] > 0:
            # Tests ran but the module under test was never imported, so
            # coverage.py wrote no report at all. Nothing real was verified.
            # Score as zero capability rather than leaving it unknown.
            result["no_module_import"] = True
            result["line_coverage"] = 0.0
            result["branch_coverage"] = 0.0

        if result["collected"] == 0 and not result["error"]:
            result["error"] = (proc.stdout or proc.stderr or "")[-400:]
        return result
    finally:
        shutil.rmtree(work, ignore_errors=True)
