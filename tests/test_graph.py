"""C-06 symbol extractor tests.

The acceptance criteria for C-06 are the headings below, and each is a class:

1. `TestOneInterfaceTwoLanguages` - two genuinely different languages come out of
   identical code. If a future change makes one of them need a special case, this is
   where it surfaces, which is the same job `TestShippedProfiles` does for C-25.
2. `TestLinesAreCheckable` - every symbol's file and line is exactly right, verified
   against sources whose line numbers are written down in the test. A graph nobody
   can spot-check is indistinguishable from a confident guess.
3. `TestBrokenFilesDoNotStopTheRun` - a syntax error is reported, not fatal, and the
   part that parsed is still returned.
4. `TestAddingALanguageIsData` - no module in `core/src` names a language.

Two further behaviours get their own classes because they are the design decisions
this component was built around rather than incidental features:
`TestResolutionIsHonest` (an edge records how firmly the syntax pinned it down) and
`TestModuleColumn` (D-032 - every row knows which sub-folder it came from).
"""

from __future__ import annotations

import ast
import importlib.util
import re
import textwrap
from pathlib import Path

import pytest
from jspec.contracts.graph import ReferenceKind, Resolution, SymbolKind
from jspec.contracts.profile import Profile, Validation
from jspec.graph import ExtractError, extract_file, extract_source, extract_tree
from jspec.graph.extract import (
    is_excluded,
    iter_source_files,
    module_of,
    spec_for,
    supported,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = REPO_ROOT / "core" / "src"
NEUTRALITY_SCRIPT = REPO_ROOT / "core" / "scripts" / "check_domain_neutrality.py"


def _neutrality_helper():
    """The CI gate's docstring stripper, loaded from the script by path.

    Reused rather than re-implemented: two copies of "what counts as prose" would
    drift, and then the test and the gate would disagree about the same file.
    """
    spec = importlib.util.spec_from_file_location("_neutrality", NEUTRALITY_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._without_docs


# Line numbers are asserted against these two sources, so the literal text matters.
# Both express the same five things - two imports, a top-level function, a type with
# two methods, a call through a member, and a call through a subscript - so that the
# two languages can be compared row for row.
PY_SOURCE = """\
import os
import os.path as osp
from pathlib import Path


def top_level(a):
    return helper(a)


class Store:
    def save(self, row):
        validate(row)
        return self.write(row)

    def write(self, row):
        return handlers[0](row)
"""

TS_SOURCE = """\
import { Page } from "@playwright/test";
import helpers from "./helpers";

export interface Row {
  id: string;
}

export const build = (n: number) => wrap(n);

export function topLevel(a: string) {
  return helper(a);
}

export class Store {
  save(row: Row) {
    validate(row);
    return this.write(row);
  }

  write(row: Row) {
    return registry[0](row);
  }
}
"""


def profile_for(languages: list[str], **overrides: object) -> Profile:
    """A throwaway profile. Only `languages` and the directories matter here."""
    fields: dict[str, object] = {
        "name": "under-test",
        "description": "Fixture profile for extractor tests.",
        "languages": languages,
        "source_dirs": ["src/"],
        "test_dirs": [],
        "validation": Validation(test="run-the-tests"),
    }
    fields.update(overrides)
    return Profile(**fields)  # type: ignore[arg-type]


def extract_text(source: str, *, relative: str, language: str):
    """Extract from a string, so a test can show the source it asserts about."""
    return extract_source(
        textwrap.dedent(source).encode("utf-8"),
        relative=relative,
        spec=spec_for(language),
    )


def names(rows, kind: SymbolKind) -> list[str]:
    return [r.name for r in rows if r.kind is kind]


class TestOneInterfaceTwoLanguages:
    """The same call, on two unalike languages, yields the same shape."""

    def test_both_languages_are_supported(self) -> None:
        assert {"python", "typescript"} <= set(supported())

    @pytest.mark.parametrize(
        ("language", "source", "relative"),
        [
            ("python", PY_SOURCE, "src/sample.py"),
            ("typescript", TS_SOURCE, "src/sample.ts"),
        ],
    )
    def test_same_shape_from_both(
        self, language: str, source: str, relative: str
    ) -> None:
        """No branch anywhere says "if the language is X". Identical assertions."""
        result = extract_text(source, relative=relative, language=language)

        assert result.error is None
        assert result.parse_error is False
        assert result.language == language
        assert "Store" in names(result.symbols, SymbolKind.CLASS)
        assert {"save", "write"} <= set(names(result.symbols, SymbolKind.METHOD))

        methods = [s for s in result.symbols if s.kind is SymbolKind.METHOD]
        assert all(m.parent == "Store" for m in methods), "methods must know their type"

        # Not a count: the two samples import a different number of things, and
        # asserting parity of counts would be asserting the fixtures match, not that
        # the extractor does. The structural claims are what must hold for both.
        imports = [r for r in result.references if r.kind is ReferenceKind.IMPORT]
        assert len(imports) >= 2
        assert all(r.resolution is Resolution.EXACT for r in imports)
        assert all(r.from_symbol is None for r in imports)
        calls = [r for r in result.references if r.kind is ReferenceKind.CALL]
        assert {"validate", "write"} <= {c.name for c in calls}

    def test_a_method_is_derived_from_the_tree_not_the_node_type(self) -> None:
        """One language has a distinct node for a method; the other does not.

        Both must still report METHOD, because the promotion is structural - a
        function inside a type. That is what keeps the rule true for a language
        added later whose grammar spells it a third way.
        """
        py = extract_text(PY_SOURCE, relative="src/s.py", language="python")
        ts = extract_text(TS_SOURCE, relative="src/s.ts", language="typescript")
        assert names(py.symbols, SymbolKind.METHOD) == ["save", "write"]
        assert names(ts.symbols, SymbolKind.METHOD) == ["save", "write"]

    def test_a_nested_function_is_not_a_method(self) -> None:
        """The promotion must look at the nearest enclosing definition, not any."""
        result = extract_text(
            """
            class Outer:
                def method(self):
                    def inner():
                        return 1
                    return inner
            """,
            relative="src/n.py",
            language="python",
        )
        assert names(result.symbols, SymbolKind.METHOD) == ["method"]
        assert names(result.symbols, SymbolKind.FUNCTION) == ["inner"]

    def test_a_binding_to_a_lambda_is_a_function_and_a_constant_is_not(self) -> None:
        """Without the value constraint, every constant indexes as a function."""
        result = extract_text(
            """
            const handler = () => run();
            const LIMIT = 10;
            """,
            relative="src/c.ts",
            language="typescript",
        )
        assert names(result.symbols, SymbolKind.FUNCTION) == ["handler"]
        assert "LIMIT" not in [s.name for s in result.symbols]


class TestLinesAreCheckable:
    """Exact file and line, against sources whose numbering is written down."""

    def test_python_lines_are_exact(self) -> None:
        result = extract_text(PY_SOURCE, relative="src/sample.py", language="python")
        found = {(s.name, s.kind.value, s.line, s.end_line) for s in result.symbols}
        assert found == {
            ("top_level", "function", 6, 7),
            ("Store", "class", 10, 16),
            ("save", "method", 11, 13),
            ("write", "method", 15, 16),
        }

    def test_typescript_lines_are_exact(self) -> None:
        result = extract_text(
            TS_SOURCE, relative="src/sample.ts", language="typescript"
        )
        found = {(s.name, s.kind.value, s.line) for s in result.symbols}
        assert found == {
            ("Row", "interface", 4),
            ("build", "function", 8),
            ("topLevel", "function", 10),
            ("Store", "class", 14),
            ("save", "method", 15),
            ("write", "method", 20),
        }

    def test_every_reference_carries_the_file_it_came_from(self) -> None:
        result = extract_text(PY_SOURCE, relative="src/sample.py", language="python")
        assert result.references
        assert all(r.file == "src/sample.py" for r in result.references)
        assert all(r.line >= 1 for r in result.references)

    def test_a_reference_knows_which_symbol_contains_it(self) -> None:
        """Without this an edge is only ever file-to-file, and C-08 loses resolution."""
        result = extract_text(PY_SOURCE, relative="src/sample.py", language="python")
        by_name = {r.name: r for r in result.references}
        assert by_name["helper"].from_symbol == "top_level"
        assert by_name["validate"].from_symbol == "save"
        assert by_name["os"].from_symbol is None, "a top-level import is inside nothing"


class TestResolutionIsHonest:
    """An edge records how firmly the syntax pinned its target down."""

    def test_a_bare_identifier_call_is_exact(self) -> None:
        result = extract_text(PY_SOURCE, relative="src/s.py", language="python")
        call = next(r for r in result.references if r.name == "validate")
        assert call.resolution is Resolution.EXACT

    def test_a_member_call_is_name_only(self) -> None:
        """`self.write(row)` names the method but not which type owns it."""
        result = extract_text(PY_SOURCE, relative="src/s.py", language="python")
        call = next(
            r
            for r in result.references
            if r.name == "write" and r.kind is ReferenceKind.CALL
        )
        assert call.resolution is Resolution.NAME_ONLY

    def test_a_computed_call_is_recorded_as_unresolved_not_dropped(self) -> None:
        """Dropping it would silently understate the edge count.

        The name recorded is the syntactic form, because that is the only thing that
        is actually true about the target.
        """
        result = extract_text(PY_SOURCE, relative="src/s.py", language="python")
        unresolved = [
            r for r in result.references if r.resolution is Resolution.UNRESOLVED
        ]
        assert len(unresolved) == 1
        assert unresolved[0].line == 16

    def test_imports_are_exact_and_aliases_are_unwrapped(self) -> None:
        """`import os.path as osp` is an edge to os.path, not to "os.path as osp"."""
        result = extract_text(PY_SOURCE, relative="src/s.py", language="python")
        imports = [r for r in result.references if r.kind is ReferenceKind.IMPORT]
        assert [r.name for r in imports] == ["os", "os.path", "pathlib"]
        assert all(r.resolution is Resolution.EXACT for r in imports)

    def test_quotes_are_not_part_of_a_module_path(self) -> None:
        result = extract_text(TS_SOURCE, relative="src/s.ts", language="typescript")
        imports = [r for r in result.references if r.kind is ReferenceKind.IMPORT]
        assert [r.name for r in imports] == ["@playwright/test", "./helpers"]


class TestBrokenFilesDoNotStopTheRun:
    """Error recovery: report it, flag it, keep whatever parsed."""

    def test_a_syntax_error_is_flagged_but_the_file_still_yields_symbols(self) -> None:
        result = extract_text(
            """
            def good():
                return 1

            def broken(:
                return 2
            """,
            relative="src/b.py",
            language="python",
        )
        assert result.parse_error is True
        assert result.error is None, "a parse error is not a read failure"
        assert "good" in [s.name for s in result.symbols]

    def test_a_clean_file_is_not_flagged(self) -> None:
        result = extract_text(PY_SOURCE, relative="src/s.py", language="python")
        assert result.parse_error is False

    def test_an_unreadable_file_is_reported_rather_than_dropped(self, tmp_path) -> None:
        """A file that vanishes mid-run must appear in the output, not vanish from it.

        Silence here is how an index ends up quietly short: the run reports success,
        the blast radius is missing a caller, and the build breaks later.
        """
        missing = tmp_path / "src" / "gone.py"
        result = extract_file(missing, spec_for("python"), tmp_path)
        assert result.error is not None
        assert result.symbols == []
        assert result.file.endswith("gone.py")

    def test_one_broken_file_does_not_stop_the_others(self, tmp_path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "ok.py").write_text("def fine():\n    return 1\n", encoding="utf-8")
        (source / "bad.py").write_text("def broken(:\n", encoding="utf-8")

        report = extract_tree(tmp_path, profile_for(["python"]), patterns=())

        assert report.to_dict()["files_scanned"] == 2
        assert report.to_dict()["files_with_syntax_errors"] == 1
        assert "fine" in [s.name for s in report.symbols]


class TestModuleColumn:
    """D-032: every row knows which sub-folder it came from, from the first run."""

    @pytest.mark.parametrize(
        ("relative", "expected"),
        [
            ("core/src/jspec/router.py", "core"),
            ("tests/test_graph.py", "tests"),
            ("setup.py", "."),
        ],
    )
    def test_module_is_the_top_level_folder(self, relative: str, expected: str) -> None:
        assert module_of(relative) == expected

    def test_symbols_and_references_both_carry_it(self, tmp_path) -> None:
        nested = tmp_path / "src" / "deep" / "deeper"
        nested.mkdir(parents=True)
        (nested / "m.py").write_text("def f():\n    g()\n", encoding="utf-8")

        report = extract_tree(tmp_path, profile_for(["python"]), patterns=())

        assert [s.module for s in report.symbols] == ["src"]
        assert [r.module for r in report.references] == ["src"]

    def test_the_report_lists_the_modules_it_covered(self, tmp_path) -> None:
        """C-08 must be able to say which sub-folder a caller lives in."""
        for folder in ("src", "extra"):
            (tmp_path / folder).mkdir()
            (tmp_path / folder / "m.py").write_text("def f():\n    pass\n", "utf-8")

        profile = profile_for(["python"], source_dirs=["src/", "extra/"])
        report = extract_tree(tmp_path, profile, patterns=())

        assert report.to_dict()["modules"] == ["extra", "src"]


class TestExclusions:
    """Nothing forbidden is opened, and the rules come from config, not from here."""

    @pytest.mark.parametrize(
        "relative",
        [
            ".git/config",
            ".venv/lib/site.py",
            "core/__pycache__/x.pyc",
            "node_modules/pkg/index.js",
            ".env",
            ".env.local",
            "deploy/server.pem",
            "app/credentials.json",
            ".claude/api.md",
        ],
    )
    def test_forbidden_paths_are_excluded_by_the_shipped_rules(self, relative) -> None:
        from jspec.config import exclude_patterns

        assert is_excluded(relative, exclude_patterns())

    @pytest.mark.parametrize(
        "relative",
        ["core/src/jspec/router.py", "tests/test_graph.py", "src/app.ts"],
    )
    def test_ordinary_source_is_not_excluded(self, relative: str) -> None:
        from jspec.config import exclude_patterns

        assert not is_excluded(relative, exclude_patterns())

    def test_an_excluded_directory_is_never_walked_into(self, tmp_path) -> None:
        source = tmp_path / "src"
        (source / "vendor").mkdir(parents=True)
        (source / "keep.py").write_text("def keep():\n    pass\n", encoding="utf-8")
        (source / "vendor" / "skip.py").write_text("def skip():\n    pass\n", "utf-8")

        found = iter_source_files(tmp_path, profile_for(["python"]), ("**/vendor/**",))

        assert [p.name for p, _ in found] == ["keep.py"]

    def test_config_is_the_only_authority_for_the_rules(self) -> None:
        """The patterns must come from config.yaml, not from a copy in the code.

        A second list is the one that goes stale, so this asserts the shipped
        config's own entries are what the scanner uses.
        """
        import yaml
        from jspec.config import exclude_patterns

        raw = yaml.safe_load(
            (REPO_ROOT / ".sdd" / "config.yaml").read_text(encoding="utf-8")
        )
        declared = set(raw["context"]["preferences"]["NEVER_INCLUDE"])
        declared |= set(raw["security"]["never_send"])
        assert declared == set(exclude_patterns())


class TestAddingALanguageIsData:
    """Supporting a new language must not require new logic."""

    def test_no_module_in_core_names_a_language(self) -> None:
        """The rule table lives in YAML precisely so this holds.

        `check_domain_neutrality.py` screens *tool* names in CI. This screens
        *language* names, which is the other half of constitution rule 20 - and the
        half a node-type table written as a Python dict would have quietly broken.

        Docstrings and comments are stripped first, reusing the gate's own helper:
        explaining why a rule exists routinely means naming the thing it forbids,
        and that is documentation, not a violation.

        This started out with one exemption: C-02's `FILE_PATH` regex enumerated
        ten languages. That is now a shape-based pattern, so the expected set is
        empty and any new name at all fails the test.
        """
        strip = _neutrality_helper()
        offenders: list[str] = []
        for path in sorted(CORE_SRC.rglob("*.py")):
            tree = strip(ast.parse(path.read_text(encoding="utf-8")))
            code = ast.unparse(tree).lower()  # unparse drops comments entirely
            # Whole tokens, so a language id is not matched inside a longer
            # word. Simpler than a boundary regex and easier to read.
            tokens = set(re.findall("[a-z_]+", code))
            relative = path.relative_to(CORE_SRC).as_posix()
            for language in supported():
                if language in tokens:
                    offenders.append(f"{relative}: {language}")
        assert offenders == [], f"language names leaked into code: {offenders}"

    def test_every_shipped_language_has_a_working_grammar(self) -> None:
        """A rule table naming a grammar the pack lacks fails here, not in the field."""
        for language in supported():
            spec = spec_for(language)
            assert spec.definitions, f"{language} extracts no definitions"
            assert spec.calls, f"{language} extracts no calls"
            assert spec.extensions, f"{language} claims no file extensions"

    def test_an_unknown_language_names_what_is_available(self) -> None:
        with pytest.raises(ExtractError) as exc:
            spec_for("cobol")
        assert "cobol" in str(exc.value)
        assert "python" in str(exc.value)

    def test_a_profile_naming_an_unknown_language_fails_before_scanning(
        self, tmp_path
    ) -> None:
        (tmp_path / "src").mkdir()
        with pytest.raises(ExtractError) as exc:
            extract_tree(tmp_path, profile_for(["cobol"]), patterns=())
        assert "under-test" in str(exc.value)


class TestRunsOnThisRepository:
    """The end-to-end check: index JSpec with JSpec, using the shipped profile."""

    def test_it_indexes_its_own_source(self) -> None:
        from jspec.profiles import load as load_profile

        report = extract_tree(
            REPO_ROOT, load_profile("jspec-self", REPO_ROOT / "profiles")
        )
        summary = report.to_dict()

        assert summary["files_scanned"] > 15
        assert summary["symbols"] > 100
        assert summary["files_unreadable"] == 0
        assert summary["files_with_syntax_errors"] == 0
        assert summary["modules"] == ["core", "tests"], "test dirs are walked too"

    def test_a_known_symbol_is_found_at_its_real_line(self) -> None:
        """Spot-check against a definition that genuinely exists in this repo."""
        from jspec.profiles import load as load_profile

        report = extract_tree(
            REPO_ROOT, load_profile("jspec-self", REPO_ROOT / "profiles")
        )
        found = [s for s in report.symbols if s.name == "exclude_patterns"]
        assert found, "the extractor cannot find a function that is definitely there"

        symbol = found[0]
        actual = (REPO_ROOT / symbol.file).read_text(encoding="utf-8").splitlines()
        assert actual[symbol.line - 1].startswith("def exclude_patterns")

    def test_two_runs_over_an_unchanged_tree_agree(self) -> None:
        """C-07 compares runs to find what changed; unstable ordering breaks that."""
        from jspec.profiles import load as load_profile

        profile = load_profile("jspec-self", REPO_ROOT / "profiles")
        first = extract_tree(REPO_ROOT, profile).to_dict()
        second = extract_tree(REPO_ROOT, profile).to_dict()
        assert first == second
