"""C-08 blast radius tests.

The component guide's acceptance criteria, each one a class below:

1. `TestEveryCallerIsFound` - on a small repository whose answer can be checked by
   hand, the transitive callers come back complete, with the connection for each.
2. `TestCyclesTerminate` - `a -> b -> a` ends, and every node appears once.
3. `TestDepthIsAlwaysReported` - a truncated answer says it was truncated. The ring
   *after* the limit is peeked at, so "stopped by depth" means something was cut.
4. `TestReverseDirection` - `dependencies` is the mirror of `dependents`, and a
   property test proves they cannot disagree about an edge.
5. `TestFastEnoughToUseCasually` - a 3,000-deep chain, with no recursion to blow.

Then the part that is specific to this component and not in the guide's list:

6. `TestCertainAndPossibleAreKeptApart` - 72% of the Made2Manage graph is `name_only`,
   so an undifferentiated count would be mostly guesswork. Every simplification in the
   resolver must err toward *possible*; these tests pin the cases where erring the
   other way would say "safe to change" about something that is not.
7. `TestFilesFollowImports` - the second graph, with relative, dotted and package
   imports, and an import that leaves the index.
8. `TestHonestWhenItCannotAnswer` - an empty index, an unknown name, a bad argument.
   A refusal names the fix; it never returns an empty list that reads as "no callers".

Line numbers asserted here are the ones in the fixture strings below. If a fixture
changes, the hand-check changes with it - which is the point of a hand-built repo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jspec.cli import EXIT_OK, EXIT_USAGE, main
from jspec.contracts.profile import Profile, Validation
from jspec.graph import traverse
from jspec.graph.store import StoreError, SymbolStore
from jspec.graph.traverse import blast_radius

# --- the hand-built repository -----------------------------------------------------

CORE = """\
def leaf():
    return 1


def mid():
    return leaf()


def top():
    return mid()


def ring_a():
    return ring_b()


def ring_b():
    leaf()
    return ring_a()
"""

SHAPES = """\
class Shape:
    def area(self):
        return 0

    def describe(self):
        return self.area()


def render(shape):
    return shape.describe()
"""

DUPES = """\
def save():
    return 1
"""

OTHER = """\
def save():
    return 2


def uses_save():
    return save()


def via_member(obj):
    return obj.save()
"""

# `late` is reachable by a possible chain of length 2 and a certain chain of length 3.
MIX = """\
def target_fn():
    return 1


def direct():
    return target_fn()


def indirect(o):
    return o.target_fn()


def c1():
    return target_fn()


def c2():
    return c1()


def late(o):
    c2()
    return o.indirect()
"""

DYNAMIC = """\
HANDLERS = {}


def dispatch(key):
    return HANDLERS[key]()
"""

BROKEN = "def broken(:\n"

TS_A = "export function a() { return 1; }\n"
TS_B = 'import { a } from "./a";\nexport function b() { return a(); }\n'
TS_C = 'import { b } from "./b";\nexport function c() { return b(); }\n'
TS_T = 'import { c } from "../c";\nexport function t() { return c(); }\n'
# Calls `a` with no import of it: the name is defined once in the repo, but that is not
# evidence this call is to it - it could be a library function of the same name.
TS_LOOSE = "export function loose() { return a(); }\n"
TS_X = 'import { y } from "./y";\nexport function x() { return y(); }\n'
TS_Y = 'import { x } from "./x";\nexport function y() { return x(); }\n'
TS_EXT = 'import { z } from "left-pad";\nimport fs from "fs";\nexport function ext() { return z(); }\n'

PKG_INIT = "def pkg_fn():\n    return 1\n"
PKG_MOD = "def mod_fn():\n    return 2\n"
PKG_SIBLING = "from .mod import mod_fn\n\n\ndef sib():\n    return mod_fn()\n"
USER = (
    "from src.pkg.mod import mod_fn\nimport pkg\n\n\ndef user():\n    return mod_fn()\n"
)
UTIL_A = ""
UTIL_B = ""

FILES = {
    "src/core.py": CORE,
    "src/shapes.py": SHAPES,
    "src/dupes.py": DUPES,
    "src/other.py": OTHER,
    "src/mix.py": MIX,
    "src/dynamic.py": DYNAMIC,
    "src/broken.py": BROKEN,
    "src/a.ts": TS_A,
    "src/b.ts": TS_B,
    "src/c.ts": TS_C,
    "src/deep/t.ts": TS_T,
    "src/loose.ts": TS_LOOSE,
    "src/x.ts": TS_X,
    "src/y.ts": TS_Y,
    "src/ext.ts": TS_EXT,
    "src/pkg/__init__.py": PKG_INIT,
    "src/pkg/mod.py": PKG_MOD,
    "src/pkg/sibling.py": PKG_SIBLING,
    "src/user.py": USER,
    "src/util.py": UTIL_A,
    "src/pkg/util.py": UTIL_B,
}


def build_profile() -> Profile:
    return Profile(
        name="traverse-test",
        description="Fixture profile for blast radius tests.",
        languages=["python", "typescript"],
        source_dirs=["src/"],
        test_dirs=[],
        validation=Validation(test="run-the-tests"),
    )


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def indexed(tmp_path_factory: pytest.TempPathFactory):
    """One store over the whole fixture, shared: the tests only read it."""
    base = tmp_path_factory.mktemp("traverse")
    tree = write_tree(base / "repo", FILES)
    store = SymbolStore(base / "index" / "t.db")
    store.refresh(tree, build_profile(), patterns=())
    yield store
    store.close()


def ask(store: SymbolStore, target: str, **kwargs):
    return blast_radius(store, target, **kwargs)


def by_name(result: dict) -> dict[str, dict]:
    """Rows keyed by name. Only valid where the fixture keeps a name unique."""
    names = [r["name"] for r in result["affected"]]
    assert len(names) == len(set(names)), f"a node appeared twice: {names}"
    return {r["name"]: r for r in result["affected"]}


def short(chain: list[str]) -> list[str]:
    return [label.split(" (")[0] for label in chain]


# --- 1 ----------------------------------------------------------------------------


class TestEveryCallerIsFound:
    def test_the_transitive_callers_of_a_function(self, indexed) -> None:
        """leaf <- mid <- top, and leaf <- ring_b <- ring_a. Counted by hand: four."""
        result = ask(indexed, "leaf")
        rows = by_name(result)

        assert set(rows) == {"mid", "ring_b", "top", "ring_a"}
        assert {n: r["depth"] for n, r in rows.items()} == {
            "mid": 1,
            "ring_b": 1,
            "top": 2,
            "ring_a": 2,
        }
        assert result["counts"]["total"] == 4

    def test_each_result_carries_the_chain_that_connects_it(self, indexed) -> None:
        """`top` is not just 'affected' - it is affected *through mid*."""
        top = by_name(ask(indexed, "leaf"))["top"]

        assert short(top["chain"]) == ["top", "mid", "leaf"]
        # The labels carry file:line, so each hop can be opened and checked.
        assert top["chain"][0] == "top (src/core.py:9)"

    def test_the_link_is_the_line_where_the_call_is_written(self, indexed) -> None:
        """`mid` calls `leaf` on line 6 of core.py - a person can go and look."""
        rows = by_name(ask(indexed, "leaf"))

        assert rows["mid"]["link"] == "src/core.py:6"
        assert rows["ring_b"]["link"] == "src/core.py:18"

    def test_callers_in_other_files_are_found_across_imports(self, indexed) -> None:
        """a <- b <- c <- t, over three files, joined only by relative imports."""
        rows = by_name(ask(indexed, "a", direction="dependents"))

        assert {n: r["depth"] for n, r in rows.items() if n != "loose"} == {
            "b": 1,
            "c": 2,
            "t": 3,
        }
        assert short(rows["t"]["chain"]) == ["t", "c", "b", "a"]

    def test_a_class_includes_the_callers_of_its_methods(self, indexed) -> None:
        """Changing `Shape` changes what `area` and `describe` do. A search that began
        at the class name alone would miss `render`, which only ever calls a method."""
        result = ask(indexed, "Shape")

        assert result["targets"]["members_included"] == 2
        assert {r["name"] for r in result["affected"]} == {"render"}

    def test_a_method_is_found_by_its_bare_name(self, indexed) -> None:
        result = ask(indexed, "area")
        rows = by_name(result)

        assert set(rows) == {"describe", "render"}
        assert rows["describe"]["depth"] == 1 and rows["render"]["depth"] == 2

    def test_a_function_nobody_calls_has_no_dependents_and_says_it_looked(
        self, indexed
    ) -> None:
        result = ask(indexed, "top")

        assert result["counts"]["total"] == 0
        assert result["depth"]["complete"] is True
        assert "everything the index can see" in result["summary"]


# --- 2 ----------------------------------------------------------------------------


class TestCyclesTerminate:
    def test_a_call_cycle_ends_and_lists_each_node_once(self, indexed) -> None:
        """ring_a <-> ring_b. `by_name` fails if either appears twice."""
        result = ask(indexed, "ring_a", depth=50)
        rows = by_name(result)

        assert set(rows) == {"ring_b"}
        assert result["depth"]["complete"] is True

    def test_a_cycle_does_not_count_the_target_as_its_own_dependent(
        self, indexed
    ) -> None:
        assert "ring_a" not in by_name(ask(indexed, "ring_a", depth=50))

    def test_an_import_cycle_ends(self, indexed) -> None:
        """x.ts and y.ts import each other."""
        result = ask(indexed, "src/x.ts", depth=50)

        assert {r["file"] for r in result["affected"]} == {"src/y.ts"}
        assert result["depth"]["complete"] is True


# --- 3 ----------------------------------------------------------------------------


class TestDepthIsAlwaysReported:
    def test_a_search_cut_short_says_so(self, indexed) -> None:
        result = ask(indexed, "leaf", depth=1)

        assert set(by_name(result)) == {"mid", "ring_b"}
        assert result["depth"] == {
            "limit": 1,
            "reached": 1,
            "complete": False,
            "stopped_by": "depth",
        }
        assert "STOPPED" in result["summary"]

    def test_a_search_that_ends_exactly_at_the_limit_is_not_called_truncated(
        self, indexed
    ) -> None:
        """The peek: depth 2 is the whole graph, and the answer must not cry wolf."""
        result = ask(indexed, "leaf", depth=2)

        assert result["counts"]["total"] == 4
        assert result["depth"]["complete"] is True
        assert result["depth"]["stopped_by"] is None

    def test_the_depth_reached_is_reported_when_the_graph_runs_out_first(
        self, indexed
    ) -> None:
        result = ask(indexed, "leaf", depth=40)

        assert result["depth"]["limit"] == 40
        assert result["depth"]["reached"] == 2

    def test_the_default_limit_is_reported_too(self, indexed) -> None:
        assert ask(indexed, "leaf")["depth"]["limit"] == traverse.DEFAULT_DEPTH

    def test_the_size_ceiling_is_reported_not_swallowed(
        self, indexed, monkeypatch
    ) -> None:
        monkeypatch.setattr(traverse, "MAX_STATES", 3)
        result = ask(indexed, "leaf", depth=50)

        assert result["depth"]["complete"] is False
        assert result["depth"]["stopped_by"] == "size"

    def test_the_row_limit_cuts_the_list_but_never_the_counts(self, indexed) -> None:
        result = ask(indexed, "leaf", limit=1)

        assert len(result["affected"]) == 1
        assert result["omitted"] == 3
        assert result["counts"]["total"] == 4


# --- 4 ----------------------------------------------------------------------------


class TestReverseDirection:
    def test_what_a_function_depends_on(self, indexed) -> None:
        result = ask(indexed, "top", direction="dependencies")
        rows = by_name(result)

        assert {n: r["depth"] for n, r in rows.items()} == {"mid": 1, "leaf": 2}
        assert short(rows["leaf"]["chain"]) == ["top", "mid", "leaf"]

    def test_forward_and_reverse_agree_about_where_the_call_is_written(
        self, indexed
    ) -> None:
        forward = by_name(ask(indexed, "top", direction="dependencies"))
        backward = by_name(ask(indexed, "mid", direction="dependents"))

        assert forward["mid"]["link"] == backward["top"]["link"] == "src/core.py:10"

    def test_calls_that_leave_the_repo_are_reported_not_dropped(self, indexed) -> None:
        """`ext` calls `z`, which is imported from a package that is not indexed."""
        result = ask(indexed, "ext", direction="dependencies")

        assert result["external"]["total"] >= 1
        assert "z" in {e["name"] for e in result["external"]["top"]}

    def test_a_computed_call_is_counted_as_unfollowable(self, indexed) -> None:
        result = ask(indexed, "dispatch", direction="dependencies")

        assert result["unresolved_calls_in_reach"] == 1

    def test_the_two_directions_are_mirror_images(self, indexed) -> None:
        """The property that matters: X is a depth-1 dependent of Y exactly when Y is
        a depth-1 dependency of X, with the same certainty. They share one resolver,
        so a disagreement here means something stopped sharing it."""
        names = [
            "leaf", "mid", "top", "ring_a", "ring_b", "area", "describe", "render",
            "uses_save", "via_member", "target_fn", "direct", "indirect", "c1", "c2",
            "late", "a", "b", "c", "t", "loose",
        ]  # fmt: skip
        dependents: dict[tuple[str, str], str] = {}
        dependencies: dict[tuple[str, str], str] = {}
        for name in names:
            for row in ask(indexed, name, direction="dependents", depth=1)["affected"]:
                dependents[(name, row["name"])] = row["certainty"]
            for row in ask(indexed, name, direction="dependencies", depth=1)[
                "affected"
            ]:
                dependencies[(row["name"], name)] = row["certainty"]

        # Restricted to pairs where both ends were queried, since the name list above
        # is not every symbol in the fixture.
        asked = set(names)
        forward = {k: v for k, v in dependencies.items() if k[0] in asked}
        backward = {k: v for k, v in dependents.items() if k[1] in asked}
        assert backward and forward == backward


# --- 5 ----------------------------------------------------------------------------


class TestFastEnoughToUseCasually:
    def test_a_three_thousand_deep_chain_is_walked_without_recursion(
        self, tmp_path: Path
    ) -> None:
        """A recursive walk dies at ~1,000 frames. This one is a loop."""
        lines = ["def f0():\n    return 0\n"]
        lines += [f"def f{i}():\n    return f{i - 1}()\n" for i in range(1, 3000)]
        tree = write_tree(tmp_path / "repo", {"src/chain.py": "\n\n".join(lines)})
        with SymbolStore(tmp_path / "index" / "c.db") as store:
            store.refresh(tree, build_profile(), patterns=())
            result = blast_radius(store, "f0", depth=10_000, limit=0)

        assert result["counts"]["total"] == 2999
        assert result["depth"]["reached"] == 2999
        assert result["depth"]["complete"] is True
        assert result["elapsed_ms"] < 10_000, "a casual query, not an event"


# --- 6 ----------------------------------------------------------------------------


class TestCertainAndPossibleAreKeptApart:
    def test_a_bare_call_in_the_same_file_is_certain(self, indexed) -> None:
        assert by_name(ask(indexed, "leaf"))["mid"]["certainty"] == "certain"

    def test_a_member_call_is_never_certain_even_when_the_name_is_unique(
        self, indexed
    ) -> None:
        """`o.target_fn()` - the name is known and the owner is not."""
        row = by_name(ask(indexed, "target_fn"))["indirect"]

        assert row["certainty"] == "possible"
        assert row["resolution"] == "name_only"
        assert row["candidates"] == 1

    def test_a_bare_call_with_no_import_is_possible_even_when_defined_once(
        self, indexed
    ) -> None:
        """The case where over-claiming costs most: `a()` in a file that never imports
        `a` may be a library function of the same name. 'Safe to change' would be wrong."""
        rows = by_name(ask(indexed, "a"))

        assert rows["loose"]["certainty"] == "possible"
        assert rows["loose"]["resolution"] == "exact"
        assert rows["b"]["certainty"] == "certain"  # same name, but b imports ./a

    def test_a_chain_is_only_as_certain_as_its_weakest_link(self, indexed) -> None:
        """render -> describe is possible, so everything past it is possible too."""
        result = ask(indexed, "area")
        assert {r["certainty"] for r in result["affected"]} == {"possible"}
        assert result["counts"]["certain"] == 0

    def test_a_node_with_any_certain_chain_is_certain_and_shows_that_chain(
        self, indexed
    ) -> None:
        """`late` is possible at depth 2 (via a member call) and certain at depth 3
        (via c2 -> c1). The certain one must win, with its own depth and chain."""
        rows = by_name(ask(indexed, "target_fn"))

        assert rows["late"]["certainty"] == "certain"
        assert rows["late"]["depth"] == 3
        assert short(rows["late"]["chain"]) == ["late", "c2", "c1", "target_fn"]
        assert rows["indirect"]["certainty"] == "possible"

    def test_the_split_is_in_the_counts_by_depth_and_by_module(self, indexed) -> None:
        counts = ask(indexed, "target_fn")["counts"]

        assert (counts["certain"], counts["possible"], counts["total"]) == (4, 1, 5)
        assert counts["by_module"] == {"src": {"certain": 4, "possible": 1}}
        assert counts["by_depth"] == [
            {"depth": 1, "certain": 2, "possible": 1},
            {"depth": 2, "certain": 1, "possible": 0},
            {"depth": 3, "certain": 1, "possible": 0},
        ]

    def test_a_shared_name_searches_every_definition_and_says_so(self, indexed) -> None:
        result = ask(indexed, "save")

        assert result["targets"]["ambiguous"] is True
        assert len(result["targets"]["definitions"]) == 2

    def test_a_bare_call_binds_to_its_own_files_definition_only(self, indexed) -> None:
        """`save()` inside other.py is other.py's `save`. Narrowing by file is what
        stops a repo with two `save`s from reporting every caller of both."""
        other = by_name(ask(indexed, "save", file="src/other.py"))
        dupes = by_name(ask(indexed, "save", file="src/dupes.py"))

        assert other["uses_save"]["certainty"] == "certain"
        assert other["via_member"]["certainty"] == "possible"
        assert set(dupes) == {"via_member"}, "uses_save must not leak onto dupes.save"
        assert dupes["via_member"]["candidates"] == 2

    def test_a_certain_node_is_listed_before_a_possible_one(self, indexed) -> None:
        certainties = [r["certainty"] for r in ask(indexed, "target_fn")["affected"]]

        assert certainties == sorted(certainties, key=lambda c: c != "certain")


# --- 7 ----------------------------------------------------------------------------


class TestFilesFollowImports:
    def test_the_importers_of_a_file_are_followed_transitively(self, indexed) -> None:
        result = ask(indexed, "src/a.ts")

        assert result["mode"] == "file"
        assert {r["file"]: r["depth"] for r in result["affected"]} == {
            "src/b.ts": 1,
            "src/c.ts": 2,
            "src/deep/t.ts": 3,
        }
        assert {r["certainty"] for r in result["affected"]} == {"certain"}

    def test_a_relative_path_climbing_out_of_a_folder_resolves(self, indexed) -> None:
        """src/deep/t.ts imports "../c"."""
        rows = {r["file"]: r for r in ask(indexed, "src/c.ts")["affected"]}

        assert rows["src/deep/t.ts"]["link"] == "src/deep/t.ts:1"
        assert rows["src/deep/t.ts"]["certainty"] == "certain"

    def test_a_dotted_name_of_two_segments_or_more_is_matched_by_its_tail(
        self, indexed
    ) -> None:
        """`from src.pkg.mod import mod_fn` - unique, and more than a bare word."""
        rows = {r["file"]: r for r in ask(indexed, "src/pkg/mod.py")["affected"]}

        assert rows["src/user.py"]["certainty"] == "certain"

    def test_a_dotted_relative_import_resolves_against_the_importing_folder(
        self, indexed
    ) -> None:
        """`from .mod import ...` inside src/pkg/."""
        rows = {r["file"]: r for r in ask(indexed, "src/pkg/mod.py")["affected"]}

        assert rows["src/pkg/sibling.py"]["certainty"] == "certain"

    def test_importing_a_package_reaches_its_entry_file_but_only_possibly(
        self, indexed
    ) -> None:
        """`import pkg` means src/pkg/__init__.py - a fact about the language, held in
        languages.yaml. One bare word is never certain: `os` would otherwise 'certainly'
        mean whichever local file is called os."""
        rows = {r["file"]: r for r in ask(indexed, "src/pkg/__init__.py")["affected"]}

        assert rows["src/user.py"]["certainty"] == "possible"

    def test_a_unique_path_tail_names_a_file(self, indexed) -> None:
        result = ask(indexed, "a.ts")

        assert result["mode"] == "file"
        assert result["targets"]["definitions"][0]["file"] == "src/a.ts"

    def test_an_ambiguous_path_tail_lists_the_candidates_instead_of_guessing(
        self, indexed
    ) -> None:
        with pytest.raises(StoreError, match=r"util\.py.*2 files"):
            ask(indexed, "util.py")

    def test_what_a_file_imports_and_what_left_the_index(self, indexed) -> None:
        result = ask(indexed, "src/ext.ts", direction="dependencies")

        assert result["counts"]["total"] == 0
        assert {e["name"] for e in result["external"]["top"]} == {"left-pad", "fs"}

    def test_the_file_limits_mention_how_imports_are_matched(self, indexed) -> None:
        assert any("import" in limit for limit in ask(indexed, "src/a.ts")["limits"])


# --- 8 ----------------------------------------------------------------------------


class TestTheIndexSaysHowCompleteItIs:
    def test_what_the_index_could_not_see_is_counted(self, indexed) -> None:
        """Absence of callers means less if 3% of files did not parse."""
        index = ask(indexed, "leaf")["index"]

        assert index["unresolved_calls"] >= 1  # dynamic.py
        assert index["files_with_parse_errors"] >= 1  # broken.py
        assert index["files"] == len(FILES)

    def test_the_known_blind_spots_travel_with_every_answer(self, indexed) -> None:
        limits = " ".join(ask(indexed, "leaf")["limits"])

        assert "passed as a value" in limits and "computed" in limits


class TestHonestWhenItCannotAnswer:
    def test_an_empty_index_refuses_and_names_the_command(self, tmp_path: Path) -> None:
        """'No dependents' and 'nothing was looked at' must never read the same."""
        with (
            SymbolStore(tmp_path / "index" / "empty.db") as store,
            pytest.raises(StoreError, match="jspec index"),
        ):
            blast_radius(store, "anything")

    def test_an_unknown_name_suggests_what_it_might_have_meant(self, indexed) -> None:
        with pytest.raises(StoreError, match=r"Similar:.*leaf"):
            ask(indexed, "lea")

    def test_an_unknown_name_with_nothing_similar_still_says_it_looked(
        self, indexed
    ) -> None:
        with pytest.raises(StoreError, match="nothing named 'zzzqqq'"):
            ask(indexed, "zzzqqq")

    def test_a_file_that_is_not_indexed_is_named(self, indexed) -> None:
        with pytest.raises(StoreError, match="not an indexed file"):
            ask(indexed, "leaf", file="src/nope.py")

    def test_a_name_that_lives_elsewhere_says_where(self, indexed) -> None:
        with pytest.raises(StoreError, match="defined in.*src/core.py"):
            ask(indexed, "leaf", file="src/other.py")

    def test_a_bad_direction_is_a_caller_mistake(self, indexed) -> None:
        with pytest.raises(ValueError, match="dependents"):
            ask(indexed, "leaf", direction="sideways")

    def test_a_depth_below_one_is_rejected(self, indexed) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            ask(indexed, "leaf", depth=0)


# --- the command line --------------------------------------------------------------


@pytest.fixture
def cli_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo plus an index directory of its own - the real `.sdd/index` is untouched."""
    monkeypatch.setattr("jspec.graph.store.index_dir", lambda *_: tmp_path / "index")
    return write_tree(tmp_path / "repo", {"src/core.py": CORE})


def run(capsys, *argv: str) -> tuple[int, dict, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    payload = json.loads(captured.out) if captured.out.strip() else {}
    return code, payload, captured.err


class TestTheCommand:
    def test_index_then_ask(self, capsys, cli_repo: Path) -> None:
        run(capsys, "index", str(cli_repo), "--profile", "python-service")
        code, out, _ = run(capsys, "blast-radius", "leaf", str(cli_repo))

        assert code == EXIT_OK
        assert out["counts"]["total"] == 4
        assert out["depth"]["complete"] is True

    def test_direction_and_depth_flags_reach_the_traversal(
        self, capsys, cli_repo: Path
    ) -> None:
        run(capsys, "index", str(cli_repo), "--profile", "python-service")
        _, out, _ = run(
            capsys,
            "blast-radius", "top", str(cli_repo),
            "--direction", "dependencies", "--depth", "1",
        )  # fmt: skip

        assert out["direction"] == "dependencies"
        assert [r["name"] for r in out["affected"]] == ["mid"]
        assert out["depth"]["complete"] is False

    def test_an_unindexed_root_is_a_usage_error_that_names_the_fix(
        self, capsys, cli_repo: Path
    ) -> None:
        code, _, err = run(capsys, "blast-radius", "leaf", str(cli_repo))

        assert code == EXIT_USAGE
        assert "jspec index" in err

    def test_an_unknown_name_is_a_usage_error_not_an_empty_answer(
        self, capsys, cli_repo: Path
    ) -> None:
        run(capsys, "index", str(cli_repo), "--profile", "python-service")
        code, out, err = run(capsys, "blast-radius", "zzzqqq", str(cli_repo))

        assert code == EXIT_USAGE and out == {} and "zzzqqq" in err

    def test_the_tool_is_registered_as_ready(self) -> None:
        from jspec import tools

        assert tools.BY_NAME["blast_radius"].ready
