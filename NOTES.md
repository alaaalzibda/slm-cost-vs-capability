# Limitations

Written before the results, so they are not excuses added afterwards. The note
on phi3 is the exception and was added once the run exposed the problem.

**This is not a replication.** Kumari and Deb compare seven prompt strategies
across three small language models and measure duration, token consumption,
energy and carbon against coverage. This study takes three of their strategies
and measures tokens, wall-clock duration and branch coverage. It is a much
smaller thing and it borrows their question.

**phi3 is reported as an anomaly, not as a result.** Its chain-of-thought runs
produced incoherent text containing chat-template fragments (`assistant:`,
`<|...|>`) and zero executable suites across 50 runs. Because this harness
calls Ollama's completion endpoint with a separate system field rather than
the chat endpoint, and because Phi-3 is known to be sensitive to its chat
template, this is more plausibly an artifact of the interface than a limit of
the model. The finding therefore rests on qwen2.5-coder and llama3.2.
Re-running phi3 through the chat endpoint is the obvious next step.

**The prompts are my wording, not theirs.** The strategy names are standard
terms from the prompting literature, but the exact prompt text in
`src/strategies.py` is my own implementation of what those names conventionally
mean. I did not have access to the prompts used in the reference study. If
their Chain of Thought prompt differs from mine, the numbers are not strictly
comparable, and the honest reading is that this measures *these three prompts*
rather than *those three strategies*.

**No energy or carbon measurement.** Those need instrumentation I do not have,
and estimating them from wall clock on a laptop that is also doing other
things would produce a number that looks like evidence and is not. Tokens and
model-reported evaluation time are reported instead, as cost proxies, and they
are labelled as proxies.

**Coverage is not test quality.** A test suite can reach every branch and still
assert nothing useful. Branch coverage is reported because it is what the
reference study used and because it is measurable, not because it settles the
question. The proportion of generated suites that even execute, and the pass
rate of the tests that do, are reported alongside it for the same reason.

**One benchmark, one language.** 25 problems from HumanEval, Python only,
selected for having at least two branches in the canonical solution, because
branch coverage on straight-line code carries no signal. Single functions with
docstrings are an easy case; a real repository is not.

**Tests are generated against a known-correct solution.** In production the
code under test may be wrong, and a generated test that passes against wrong
code is worse than no test. This setup cannot see that failure mode at all.

**The least-to-most arm is incomplete.** It was abandoned after runs began
timing out on qwen2.5-coder and consuming 10,000 to 27,000 tokens on phi3. The
partial rows are reported because the cost is itself the finding, but they
rest on 7 to 15 runs rather than 50 and should not be compared directly with
the other two strategies.

**Sampling.** Temperature is fixed at 0.2 and the seed varies per repeat, so
repeats are independent samples rather than reruns of the same draw. With one
repeat per cell the numbers are a single draw and should be read that way.

**Generated code is executed.** Each run happens in a fresh temporary directory
in a subprocess under a timeout, but this is not a sandbox. Do not run it
anywhere that matters.
