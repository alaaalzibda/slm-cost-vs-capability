"""Model backends. Ollama is the one used for the reported results.

The mock backend exists so the pipeline can be tested without a model
running; it is never used for reported numbers.
"""
import json, time, urllib.request, urllib.error


class OllamaBackend:
    """Talks to a local Ollama server.

    Token counts come from Ollama itself (prompt_eval_count / eval_count),
    not from a re-tokenisation on our side, so they are the counts the
    model actually processed.
    """

    def __init__(self, model, host="http://localhost:11434", temperature=0.2, seed=7):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.seed = seed

    def complete(self, prompt, system=None):
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature, "seed": self.seed},
        }
        if system:
            body["system"] = system

        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=900) as r:
            data = json.loads(r.read())
        wall = time.perf_counter() - t0

        return {
            "text": data.get("response", ""),
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "duration_s": round(wall, 3),
            # Ollama reports its own timings in nanoseconds; keep them, they are
            # a cleaner cost signal than wall clock on a shared laptop.
            "eval_duration_s": round(data.get("eval_duration", 0) / 1e9, 3),
            "load_duration_s": round(data.get("load_duration", 0) / 1e9, 3),
        }


class MockBackend:
    """Deterministic stand-in used only to exercise the pipeline."""

    def __init__(self, model="mock", **kw):
        self.model = model

    def complete(self, prompt, system=None):
        import re
        m = re.search(r"from solution import (\w+)", prompt)
        fn = m.group(1) if m else "f"
        code = (
            "```python\n"
            f"from solution import {fn}\n\n"
            "def test_smoke():\n"
            "    assert True\n"
            "```"
        )
        return {
            "text": code,
            "prompt_tokens": len(prompt) // 4,
            "completion_tokens": len(code) // 4,
            "duration_s": 0.01,
            "eval_duration_s": 0.01,
            "load_duration_s": 0.0,
        }


def get_backend(name, model, **kw):
    if name == "ollama":
        return OllamaBackend(model, **kw)
    if name == "mock":
        return MockBackend(model)
    raise ValueError(f"unknown backend: {name}")
