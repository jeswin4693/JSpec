"""Fail the build if `core/` names a language, framework or test runner.

Constitution rule 20 (D-011): domain knowledge lives in `profiles/*.yaml`, not in
code. A new domain must be a YAML file, not a code change.

That rule is the kind C-04 exists to handle: it is greppable, so it belongs in CI
rather than in a docstring nobody re-reads. Without a wall here the erosion is
gradual and invisible - one `if language == "python"` at a time, each individually
reasonable, until onboarding a Go service means editing five modules and only the
original author can do it.

Docstrings and comments are stripped before searching, deliberately. Explaining WHY
a rule exists frequently requires naming the thing it forbids - `contracts/risk.py`
says "baking a Playwright risk taxonomy into the code is the failure this prevents",
which is good documentation and must not be a build failure. Only executable code
is checked.

Run:  python core/scripts/check_domain_neutrality.py
Exit: 0 clean, 1 violations found (each printed with its file and line).
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

SEARCH_ROOT = pathlib.Path("core/src")

TOOL_NAMES = re.compile(
    r"\b("
    r"pytest|ruff|mypy|tox|poetry|"  # python
    r"eslint|tsc|npx|npm|jest|vitest|playwright|cypress|"  # js/ts
    r"gradle|maven|cargo|dotnet|rspec|phpunit|go test"  # everything else
    r")\b",
    re.IGNORECASE,
)

# The two modules whose entire job is to model project-specific facts. They may
# name tools in field descriptions and validators; nothing else may.
EXEMPT = {"profiles.py", "contracts/profile.py"}


def _without_docs(tree: ast.AST) -> ast.AST:
    """Drop every docstring, so prose about a rule is not mistaken for breaking it."""
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, holders):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return tree


def violations(root: pathlib.Path = SEARCH_ROOT) -> list[str]:
    """Every executable line in `root` that names a tool, outside the exempt modules."""
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.as_posix().split("core/src/jspec/")[-1]
        if relative in EXEMPT:
            continue
        tree = _without_docs(ast.parse(path.read_text(encoding="utf-8")))
        for line in ast.unparse(tree).splitlines():
            if TOOL_NAMES.search(line):
                found.append(f"{relative}: {line.strip()[:80]}")
    return found


def main() -> int:
    found = violations()
    if not found:
        print("ok domain neutrality: core/ names no language, framework or runner")
        return 0

    print("core/ contains domain-specific knowledge (constitution rule 20, D-011):")
    for line in found:
        print(f"  {line}")
    print("\nMove it to profiles/*.yaml and read it through jspec.profiles.load().")
    return 1


if __name__ == "__main__":
    sys.exit(main())
