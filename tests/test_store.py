"""C-07 symbol store tests.

The acceptance criteria for C-07 are the classes below:

1. `TestFullIndexIsComplete` - everything C-06 found is in the database, with the
   same counts and the same lines. An index that loses rows silently is worse than
   no index, because the answer still looks complete.
2. `TestOnlyChangedFilesAreReparsed` - **the component's whole reason for existing**,
   and the one criterion that cannot be asserted from a summary. `extract_file` is
   passed in as a counting stub, so the test proves the parse did not happen rather
   than trusting a number the code under test produced about itself.
3. `TestDeletedAndRenamedFiles` - stale rows go, and a rename is reported as a
   rename because content hashing makes that free.
4. `TestTheFourQuestions` - by name, by kind, by file, by text. C-07's stated
   deliverable, one test each.
5. `TestHonestWhenItCannotAnswer` - an empty index, a filterless lookup, an
   unsearchable string and a foreign schema version all refuse with a fix in the
   message, rather than returning `[]`.
6. `TestTheStoreStaysOutOfTheIndexedRepo` - indexing a tree writes nothing into it.
7. `TestEdgesAreStoredForC08` - the references table carries `module` and
   `resolution` from the first migration (D-032, D-034), because adding either later
   means re-indexing every repository the tool has ever seen.

`TestTimestampsAreNotTrusted` sits inside class 2 rather than in its own: rewriting
identical bytes changes the mtime and must not trigger a parse, which is the
difference between this design and the `mtime >` version everyone writes first.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from jspec.contracts.graph import Resolution
from jspec.contracts.profile import Profile, Validation
from jspec.graph.extract import extract_file, extract_tree
from jspec.graph.store import (
    SCHEMA_VERSION,
    StoreError,
    SymbolStore,
    db_filename,
    index_dir,
    store_path_for,
)

# Two files in two languages, with a third that will be edited, deleted and renamed.
PY_STORE = """\
class Store:
    def save(self, row):
        return self.write(row)

    def write(self, row):
        return row


def helper(x):
    return Store().save(x)
"""

PY_OTHER = """\
def untouched(a):
    return a
"""

TS_SOURCE = """\
import { Row } from "./row";

export class Registry {
  register(row: Row) {
    return this.store.save(row);
  }
}

export const build = () => new Registry();
"""


def profile_for(languages: list[str], **overrides: object) -> Profile:
    """A throwaway profile, shaped like the one in test_graph.py."""
    fields: dict[str, object] = {
        "name": "store-under-test",
        "description": "Fixture profile for symbol store tests.",
        "languages": languages,
        "source_dirs": ["src/"],
        "test_dirs": [],
        "validation": Validation(test="run-the-tests"),
    }
    fields.update(overrides)
    return Profile(**fields)  # type: ignore[arg-type]


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A small repository whose every symbol can be checked by hand."""
    src = tmp_path / "src"
    (src / "deep").mkdir(parents=True)
    (src / "store.py").write_text(PY_STORE, encoding="utf-8")
    (src / "other.py").write_text(PY_OTHER, encoding="utf-8")
    (src / "deep" / "registry.ts").write_text(TS_SOURCE, encoding="utf-8")
    return tmp_path


@pytest.fixture
def store(tmp_path: Path) -> SymbolStore:
    """A store in its own directory, never inside the indexed tree."""
    opened = SymbolStore(tmp_path / "index" / "test.db")
    yield opened
    opened.close()


@pytest.fixture
def profile() -> Profile:
    return profile_for(["python", "typescript"])


class CountingExtractor:
    """`extract_file` with a call log.

    The only honest way to test an incremental path: `files_parsed` is produced by
    the code under test, so believing it would be circular. This counts the calls
    from outside.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, path: Path, spec, root: Path):
        self.calls.append(path.name)
        return extract_file(path, spec, root)


class TestFullIndexIsComplete:
    def test_counts_match_the_extractor(self, store, tree, profile):
        stats = store.refresh(tree, profile, patterns=())
        direct = extract_tree(tree, profile, patterns=())

        assert stats.files_seen == 3
        assert stats.files_parsed == 3
        assert stats.symbols == len(direct.symbols)
        assert stats.references == len(direct.references)
        assert stats.symbols > 0, "an empty index would pass every other assertion"

    def test_lines_survive_the_round_trip(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        (row,) = store.lookup("save")
        # PY_STORE: class Store line 1, def save line 2, body line 3.
        assert (row["file"], row["line"], row["end_line"]) == ("src/store.py", 2, 3)
        assert (row["kind"], row["parent"]) == ("method", "Store")
        assert row["qualified_name"] == "Store.save"

    def test_every_file_is_recorded_with_its_hash(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        files = {row["path"]: row for row in store.files()}
        assert set(files) == {"src/store.py", "src/other.py", "src/deep/registry.ts"}
        assert all(len(row["content_hash"]) == 64 for row in files.values())
        assert files["src/deep/registry.ts"]["module"] == "src"

    def test_indexing_twice_does_not_duplicate_rows(self, store, tree, profile):
        first = store.refresh(tree, profile, patterns=())
        second = store.refresh(tree, profile, patterns=())
        assert second.symbols == first.symbols
        assert second.references == first.references


class TestOnlyChangedFilesAreReparsed:
    def test_second_run_parses_nothing(self, store, tree, profile):
        counter = CountingExtractor()
        store.refresh(tree, profile, patterns=(), extract=counter)
        assert len(counter.calls) == 3

        counter.calls.clear()
        stats = store.refresh(tree, profile, patterns=(), extract=counter)
        assert counter.calls == [], "an unchanged tree must cost zero parses"
        assert (stats.files_parsed, stats.files_unchanged) == (0, 3)

    def test_editing_one_file_parses_exactly_that_file(self, store, tree, profile):
        counter = CountingExtractor()
        store.refresh(tree, profile, patterns=(), extract=counter)
        counter.calls.clear()

        (tree / "src" / "store.py").write_text(
            PY_STORE + "\n\ndef added():\n    return helper(1)\n", encoding="utf-8"
        )
        stats = store.refresh(tree, profile, patterns=(), extract=counter)

        assert counter.calls == ["store.py"]
        assert (stats.files_parsed, stats.files_changed) == (1, 1)
        assert stats.files_unchanged == 2
        assert store.lookup("added"), "the new symbol must be queryable"

    def test_rewriting_identical_bytes_parses_nothing(self, store, tree, profile):
        """The timestamp trap, made into a test.

        Writing a file's own bytes back changes its mtime and nothing else. A
        `mtime > last_indexed` design re-parses the whole tree after a `git
        checkout` for exactly this reason; a content hash cannot be fooled by it.
        """
        counter = CountingExtractor()
        store.refresh(tree, profile, patterns=(), extract=counter)
        counter.calls.clear()

        target = tree / "src" / "store.py"
        before = target.stat().st_mtime_ns
        target.write_bytes(target.read_bytes())
        # The mtime is moved an hour forward explicitly rather than left to the
        # rewrite: on a fast filesystem the write can land inside the same clock
        # tick, and then the test would pass because nothing changed rather than
        # because the hash was consulted.
        moved = (before // 1_000_000_000) + 3600
        os.utime(target, (moved, moved))
        assert target.stat().st_mtime_ns > before, "the trap must actually be set"

        stats = store.refresh(tree, profile, patterns=(), extract=counter)
        assert counter.calls == []
        assert stats.files_unchanged == 3

    def test_rebuild_reparses_everything_on_purpose(self, store, tree, profile):
        counter = CountingExtractor()
        store.refresh(tree, profile, patterns=(), extract=counter)
        counter.calls.clear()

        stats = store.refresh(tree, profile, patterns=(), rebuild=True, extract=counter)
        assert sorted(counter.calls) == ["other.py", "registry.ts", "store.py"]
        assert stats.files_parsed == 3


class TestDeletedAndRenamedFiles:
    def test_deleting_a_file_removes_its_symbols(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        assert store.lookup("untouched")

        (tree / "src" / "other.py").unlink()
        stats = store.refresh(tree, profile, patterns=())

        assert stats.files_deleted == 1
        assert store.lookup("untouched") == []
        assert store.lookup(file="src/other.py") == []
        assert "src/other.py" not in {row["path"] for row in store.files()}

    def test_a_rename_is_reported_as_a_rename(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        (tree / "src" / "other.py").rename(tree / "src" / "renamed.py")
        stats = store.refresh(tree, profile, patterns=())

        assert (stats.files_deleted, stats.files_added, stats.files_renamed) == (
            1,
            1,
            1,
        )
        (row,) = store.lookup("untouched")
        assert row["file"] == "src/renamed.py"

    def test_deleting_a_file_clears_its_full_text_entries(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        assert store.search("untouched")

        (tree / "src" / "other.py").unlink()
        store.refresh(tree, profile, patterns=())
        assert store.search("untouched") == [], (
            "an FTS index out of step with its content table answers with symbols "
            "that no longer exist"
        )


class TestTheFourQuestions:
    def test_by_name(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        (row,) = store.lookup("Registry")
        assert (row["kind"], row["file"]) == ("class", "src/deep/registry.ts")

    def test_by_kind_and_module(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        methods = store.lookup(kind="method")
        assert {row["name"] for row in methods} >= {"save", "write", "register"}
        assert all(row["module"] == "src" for row in store.lookup(module="src"))

    def test_by_file(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        rows = store.lookup(file="src/store.py")
        assert {row["name"] for row in rows} == {"Store", "save", "write", "helper"}
        assert [row["line"] for row in rows] == sorted(row["line"] for row in rows)

    def test_by_text_matches_a_prefix(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        names = {row["name"] for row in store.search("regist")}
        assert "Registry" in names, "prefix search is what makes a partial name useful"

    def test_text_search_finds_by_qualified_name(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        assert any(row["name"] == "save" for row in store.search("Store save"))

    def test_exact_lookup_is_not_a_substring_match(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        assert store.lookup("sav") == [], "lookup is the exact rung; search is fuzzy"


class TestHonestWhenItCannotAnswer:
    def test_an_empty_index_refuses_and_names_the_fix(self, store):
        with pytest.raises(StoreError, match="jspec index"):
            store.require_indexed("run `jspec index . --profile x` first")

    def test_a_filterless_lookup_is_rejected(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        with pytest.raises(StoreError, match="not a question"):
            store.lookup()

    def test_an_unsearchable_query_is_rejected(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        with pytest.raises(StoreError, match="nothing searchable"):
            store.search("!!! ---")

    def test_punctuation_in_a_query_does_not_crash_fts(self, store, tree, profile):
        """FTS5 treats `-`, `"` and `*` as syntax, so a raw path would be a syntax
        error rather than a search. The query is rebuilt from word characters."""
        store.refresh(tree, profile, patterns=())
        assert store.search('src/deep/registry.ts "*"') != []

    def test_a_foreign_schema_version_is_refused(self, tmp_path):
        path = tmp_path / "index" / "foreign.db"
        path.parent.mkdir(parents=True)
        conn = sqlite3.connect(path)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 7}")
        conn.commit()
        conn.close()

        with pytest.raises(StoreError, match="schema version"):
            SymbolStore(path)

    def test_an_unknown_hash_algorithm_names_the_config_key(self, tmp_path):
        with pytest.raises(StoreError, match="hash_algorithm"):
            SymbolStore(tmp_path / "x.db", hash_algorithm="not-a-hash")

    def test_an_unreadable_file_is_retried_not_cached(self, store, tree, profile):
        """A file that failed to read gets an empty hash, which never matches, so
        the next run tries again instead of remembering it as broken forever."""
        store.refresh(tree, profile, patterns=())

        def failing(path: Path, spec, root: Path):
            row = extract_file(path, spec, root)
            return row.model_copy(update={"error": "could not read: simulated"})

        broken = tree / "src" / "store.py"
        broken.write_text(PY_STORE + "\n# changed\n", encoding="utf-8")
        stats = store.refresh(tree, profile, patterns=(), extract=failing)
        assert stats.files_unreadable == 1

        (recorded,) = [r for r in store.files() if r["path"] == "src/store.py"]
        assert recorded["error"] == "could not read: simulated"


class TestTheStoreStaysOutOfTheIndexedRepo:
    def test_indexing_writes_nothing_into_the_tree(self, store, tree, profile):
        before = {p.relative_to(tree).as_posix() for p in tree.rglob("*")}
        store.refresh(tree, profile, patterns=())
        after = {p.relative_to(tree).as_posix() for p in tree.rglob("*")}
        assert before == after, (
            "indexing a repository must not add an untracked database to it"
        )

    def test_two_roots_get_two_databases(self, tmp_path):
        a = tmp_path / "alpha"
        b = tmp_path / "beta"
        a.mkdir()
        b.mkdir()
        assert db_filename(a) != db_filename(b)
        assert db_filename(a) == db_filename(a), "the same root must reopen the same db"
        assert db_filename(a).startswith("alpha-")

    def test_same_name_different_place_does_not_collide(self, tmp_path):
        one = tmp_path / "one" / "repo"
        two = tmp_path / "two" / "repo"
        one.mkdir(parents=True)
        two.mkdir(parents=True)
        assert db_filename(one) != db_filename(two)

    def test_the_configured_index_root_is_used(self, tree):
        assert index_dir().name == "index"
        assert index_dir().parent.name == ".sdd"
        assert store_path_for(tree).parent == index_dir()


class TestEdgesAreStoredForC08:
    def test_references_carry_module_and_resolution(self, store, tree, profile):
        store.refresh(tree, profile, patterns=())
        rows = list(
            store._conn.execute(
                "SELECT name, module, resolution, from_symbol, line FROM refs "
                "WHERE name = 'save'"
            )
        )
        assert rows, "the edge into Store.save must be stored, not dropped"
        assert {row["module"] for row in rows} == {"src"}
        assert {row["resolution"] for row in rows} <= {r.value for r in Resolution}

    def test_the_resolution_split_is_preserved(self, store, tree, profile):
        stats = store.refresh(tree, profile, patterns=())
        split = store.counts()["by_resolution"]
        assert sum(split.values()) == stats.references
        assert Resolution.NAME_ONLY.value in split, (
            "`this.store.save(row)` is a member call on an unknown receiver; if the "
            "store ever reports it as exact, C-08 will overstate its certainty"
        )

    def test_one_hop_callers_are_queryable(self, store, tree, profile):
        """The query C-08 will build its traversal on, and the reason `from_symbol`
        is a column: without it an edge says a file touches a name, not which part
        of the file does, and a blast radius could only ever be file-shaped.

        `Store()` in `helper` is the one `exact` edge in the fixture - a bare
        identifier, no receiver to guess at - which is what makes it the right
        assertion here.
        """
        store.refresh(tree, profile, patterns=())
        callers = list(
            store._conn.execute(
                "SELECT file, from_symbol, line, resolution FROM refs "
                "WHERE name = 'Store'"
            )
        )
        assert [(row["file"], row["from_symbol"], row["line"]) for row in callers] == [
            ("src/store.py", "helper", 10)
        ]
        assert callers[0]["resolution"] == Resolution.EXACT.value


class TestAQueryNeverWritesAFile:
    """Opening SQLite creates the file, so a read path has to check first.

    Otherwise `jspec find` against a mistyped root leaves an empty database behind
    and then reports that it is empty - and the file's existence afterwards looks
    like evidence the root was once indexed.
    """

    def test_reading_an_unindexed_root_creates_nothing(self, tmp_path):
        from jspec.graph.store import open_store

        root = tmp_path / "never-indexed"
        root.mkdir()
        index_root = tmp_path / "index"

        with pytest.raises(StoreError, match="no index for"):
            open_store(root, create=False, index_root=index_root)

        assert not index_root.exists(), "a failed read must not leave a database"

    def test_indexing_then_reading_works(self, tmp_path, tree, profile):
        from jspec.graph.store import open_store

        index_root = tmp_path / "index"
        with open_store(tree, index_root=index_root) as store:
            store.refresh(tree, profile, patterns=())
        with open_store(tree, create=False, index_root=index_root) as store:
            assert store.lookup("Store")
