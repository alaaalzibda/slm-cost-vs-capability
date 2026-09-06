"""The three prompt strategies compared in this study.

Chosen to span the cost range reported by Kumari & Deb (arXiv:2604.02761):
Zero-Shot is their cheap end, Chain of Thought their expensive end, and
Least-to-Most sits between the two. Least-to-Most is genuinely two model
calls, which is part of why it costs more, so it is implemented that way
rather than as a single prompt that merely mentions decomposition.
"""

SYSTEM = (
    "You are a Python testing assistant. You write pytest tests. "
    "Output ONLY Python code in a single ``` block. No prose outside the block."
)

_TASK = """Here is a Python function.

```python
{prompt}```

Write pytest unit tests for `{entry_point}`.

Your code block MUST begin with exactly this line:
from solution import {entry_point}

Do not redefine the function under test. Name every test function with a
test_ prefix. Import the function, do not reimplement it."""


def zero_shot(problem):
    """Single call, no reasoning scaffold."""
    return [{
        "name": "generate",
        "prompt": _TASK.format(**problem),
    }]


def chain_of_thought(problem):
    """Single call, reasoning requested before the code."""
    return [{
        "name": "generate",
        "prompt": _TASK.format(**problem) + (
            "\n\nThink step by step first. Reason about the function's behaviour, "
            "its branches, its boundary values and its failure cases. Put that "
            "reasoning in Python comments at the top of the code block, then write "
            "the tests below it."
        ),
    }]


def least_to_most(problem):
    """Two calls: decompose into behaviours, then write tests for that list."""
    decompose = (
        "Here is a Python function.\n\n```python\n{prompt}```\n\n"
        "List the distinct behaviours of `{entry_point}` that a test suite should "
        "cover, from the simplest to the most complex. Cover every branch and "
        "boundary. Output a numbered list only, no code."
    ).format(**problem)

    write = (
        _TASK.format(**problem)
        + "\n\nCover exactly these behaviours, one test per item:\n\n{previous}"
    )
    return [
        {"name": "decompose", "prompt": decompose, "expects_code": False},
        {"name": "generate", "prompt": write, "uses_previous": True},
    ]


STRATEGIES = {
    "zero_shot": zero_shot,
    "chain_of_thought": chain_of_thought,
    "least_to_most": least_to_most,
}
