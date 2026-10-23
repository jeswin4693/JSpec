"""C-07 symbol store: remember what C-06 found, re-read only what changed.

C-06 parses a tree in one pass. On the Made2Manage suite that is 1,885 files and
64 seconds - fine once, unusable as the thing standing between a question and its
answer. This module makes the second run cost about a second, so that asking "who
calls this?" is casual rather than an event.

WHY CONTENT HASHES AND NOT TIMESTAMPS
The obvious incremental check is `if mtime > last_indexed: reparse`, and it is
wrong in both directions. A `git checkout` rewrites mtimes on files whose contents
are identical, so the whole tree looks dirty. A file copied with its metadata, a
clock correction, or a OneDrive sync - and this repository lives in a OneDrive
folder - can leave an edited file looking older than the index, so a real change is
skipped silently. A hash of the bytes cannot lie about either: same bytes, same
digest, nothing to do. This is the idea underneath git objects, build caches and
container layers, and it is worth paying one full read per file per run to get it.

WHAT IS STORED, AND WHAT IS NOT
Symbols *and* references, both with their `module` and `resolution` columns present
from the first migration. Those two columns are the reason this schema exists at
version 1 rather than being retrofitted (D-032, D-034): adding a column to an index
means re-reading every file in every repository it has ever seen, and on the M2M
suite 72% of edges are `name_only`, so a store without `resolution` would hand C-08
a confident number that is mostly guesswork.

What is *not* here is traversal. `references_to` one hop is a query; the transitive
closure, cycle detection and depth reporting are C-08 and live there. This module
answers the four questions C-07's acceptance names - by name, by file, by kind, by
text - and stores the edges C-08 will need so that it never has to trigger a
re-index to get them.

WHERE THE DATABASE LIVES
Under JSpec's own `.sdd/index/`, one file per indexed root, never inside the
repository being read. Indexing someone else's checkout must not add an untracked
binary to their working tree; `jspec extract` was read-only and `jspec index` stays
read-only with respect to its target.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Self

from jspec.config import ConfigError, config_path, exclude_patterns, index_settings
from jspec.contracts.graph import FileSymbols
from jspec.contracts.profile import Profile
from jspec.graph.extract import LanguageSpec, extract_file, iter_source_files

SCHEMA_VERSION = 1
"""Bumped whenever a column changes. An older file is refused, never guessed at."""

Extractor = Callable[[Path, LanguageSpec, Path], FileSymbols]
"""The per-file parse. A parameter so tests can count calls - which is the only way
to *prove* the incremental path rather than assert it."""


class StoreError(Exception):
    """The index cannot be opened, or a query cannot be answered. Names the fix."""


# --- schema -----------------------------------------------------------------------

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    # `content_hash` is the whole point of the table. `error` and `parse_error` are
    # carried so that a file which failed to read is a row saying so, not a gap -
    # the same reason FileSymbols keeps them (an index quietly 3% short is worse
    # than one that admits it).
    """
    CREATE TABLE IF NOT EXISTS files (
        path            TEXT PRIMARY KEY,
        module          TEXT NOT NULL,
        language        TEXT NOT NULL,
        content_hash    TEXT NOT NULL,
        symbol_count    INTEGER NOT NULL DEFAULT 0,
        reference_count INTEGER NOT NULL DEFAULT 0,
        parse_error     INTEGER NOT NULL DEFAULT 0,
        error           TEXT,
        indexed_at      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS symbols (
        id             INTEGER PRIMARY KEY,
        name           TEXT NOT NULL,
        qualified_name TEXT NOT NULL,
        kind           TEXT NOT NULL,
        file           TEXT NOT NULL REFERENCES files(path),
        module         TEXT NOT NULL,
        line           INTEGER NOT NULL,
        end_line       INTEGER NOT NULL,
        parent         TEXT,
        language       TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS refs (
        id          INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        kind        TEXT NOT NULL,
        file        TEXT NOT NULL REFERENCES files(path),
        module      TEXT NOT NULL,
        line        INTEGER NOT NULL,
        from_symbol TEXT,
        resolution  TEXT NOT NULL,
        language    TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS symbols_name ON symbols(name)",
    "CREATE INDEX IF NOT EXISTS symbols_file ON symbols(file)",
    "CREATE INDEX IF NOT EXISTS symbols_kind ON symbols(kind)",
    "CREATE INDEX IF NOT EXISTS symbols_module ON symbols(module)",
    # Both directions are indexed because C-08 needs both: `refs_name` answers "who
    # calls X" (reverse) and `refs_file` answers "what does this file use" (forward).
    # An index the next component needs is cheaper to create now than a migration.
    "CREATE INDEX IF NOT EXISTS refs_name ON refs(name)",
    "CREATE INDEX IF NOT EXISTS refs_file ON refs(file)",
    "CREATE INDEX IF NOT EXISTS refs_from ON refs(file, from_symbol)",
)

FTS_SCHEMA = (
    # External-content FTS5: the index stores no copy of the text, it points at
    # `symbols.id`. Two triggers keep it in sync, so every write path in this module
    # gets full-text search for free and there is no second place to forget.
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
        name, qualified_name, file,
        content='symbols', content_rowid='id'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS symbols_fts_insert AFTER INSERT ON symbols BEGIN
        INSERT INTO symbols_fts(rowid, name, qualified_name, file)
        VALUES (new.id, new.name, new.qualified_name, new.file);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS symbols_fts_delete AFTER DELETE ON symbols BEGIN
        INSERT INTO symbols_fts(symbols_fts, rowid, name, qualified_name, file)
        VALUES ('delete', old.id, old.name, old.qualified_name, old.file);
    END
    """,
)


def _has_fts5(conn: sqlite3.Connection) -> bool:
    """Whether this SQLite was built with FTS5, probed rather than assumed."""
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.fts5_probe USING fts5(x)")
    except sqlite3.OperationalError:
        return False
    conn.execute("DROP TABLE temp.fts5_probe")
    return True


# --- where the database goes ------------------------------------------------------


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "root"


def db_filename(root: Path) -> str:
    """A readable, collision-proof filename for one indexed root.

    The folder name makes it recognisable in a directory listing; the digest of the
    absolute path keeps two checkouts of the same repository apart. Deterministic,
    so the same root always reopens the same index.
    """
    absolute = root.resolve().as_posix()
    digest = hashlib.sha256(absolute.encode("utf-8")).hexdigest()[:8]
    return f"{_slug(root.resolve().name)}-{digest}.db"


def index_dir(jspec_root: Path | None = None) -> Path:
    """`index.root` from `.sdd/config.yaml`, resolved against JSpec's own root.

    Relative values resolve against the directory holding `.sdd/`, never against the
    current working directory - a cache that moves when you `cd` is a cache that gets
    rebuilt for no reason.
    """
    configured = Path(str(index_settings(jspec_root)["root"]))
    if configured.is_absolute():
        return configured
    return config_path(jspec_root).parent.parent / configured


def store_path_for(root: Path, jspec_root: Path | None = None) -> Path:
    """The database file for one indexed root."""
    return index_dir(jspec_root) / db_filename(root)


# --- what a run did ---------------------------------------------------------------


@dataclass(frozen=True)
class IndexStats:
    """One refresh, in numbers a person can check.

    `files_parsed` against `files_seen` is the headline: after the first run it
    should be the number of files you actually edited. If it is not, the incremental
    path is broken, and that is visible without reading the code.
    """

    root: str
    profile: str
    store: str
    files_seen: int = 0
    files_parsed: int = 0
    files_unchanged: int = 0
    files_added: int = 0
    files_changed: int = 0
    files_deleted: int = 0
    files_renamed: int = 0
    files_unreadable: int = 0
    symbols: int = 0
    references: int = 0
    elapsed_ms: int = 0
    full_text_search: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- the store --------------------------------------------------------------------


class SymbolStore:
    """A SQLite index of one tree's symbols and references.

    Usable as a context manager. Opening creates the file and the schema; opening a
    database written by a different schema version fails with the path and the fix
    rather than querying columns that may have moved.
    """

    def __init__(self, path: Path, *, hash_algorithm: str = "sha256") -> None:
        self.path = Path(path)
        self.hash_algorithm = hash_algorithm
        try:
            hashlib.new(hash_algorithm)
        except ValueError as exc:
            raise StoreError(
                f"unknown hash algorithm {hash_algorithm!r} (from index."
                f"hash_algorithm in .sdd/config.yaml): {exc}"
            ) from exc

        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(self.path)
        except sqlite3.Error as exc:
            raise StoreError(f"cannot open index at {self.path}: {exc}") from exc
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._check_version()
        self.full_text_search = self._create_schema()

    # -- lifecycle ---------------------------------------------------------------

    def _check_version(self) -> None:
        found = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if found not in (0, SCHEMA_VERSION):
            raise StoreError(
                f"the index at {self.path} was written by schema version {found}; "
                f"this build expects {SCHEMA_VERSION}. Re-index with --rebuild, or "
                f"delete the file - it is a cache and is rebuilt from source."
            )

    def _create_schema(self) -> bool:
        with self._conn:
            for statement in SCHEMA:
                self._conn.execute(statement)
            available = _has_fts5(self._conn)
            if available:
                for statement in FTS_SCHEMA:
                    self._conn.execute(statement)
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._set_meta("schema_version", str(SCHEMA_VERSION))
            self._set_meta("full_text_search", "1" if available else "0")
        return available

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @classmethod
    def for_root(
        cls, root: Path, *, jspec_root: Path | None = None, index_root: Path | None = None
    ) -> SymbolStore:
        """Open the index belonging to one tree, per `.sdd/config.yaml`."""
        settings = index_settings(jspec_root)
        directory = Path(index_root) if index_root is not None else index_dir(jspec_root)
        return cls(
            directory / db_filename(Path(root)),
            hash_algorithm=str(settings["hash_algorithm"]),
        )

    # -- meta --------------------------------------------------------------------

    def _set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def meta(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else str(row["value"])

    # -- writing -----------------------------------------------------------------

    def _hash(self, data: bytes) -> str:
        digest = hashlib.new(self.hash_algorithm)
        digest.update(data)
        return digest.hexdigest()

    def _known_hashes(self) -> dict[str, str]:
        return {
            str(row["path"]): str(row["content_hash"])
            for row in self._conn.execute("SELECT path, content_hash FROM files")
        }

    def _forget(self, paths: Iterable[str]) -> None:
        """Drop every row belonging to these files.

        Symbols are deleted explicitly rather than by `ON DELETE CASCADE`, because
        SQLite fires row triggers for foreign-key actions only when
        `recursive_triggers` is on - so a cascade would leave the FTS index holding
        entries for symbols that no longer exist. Three statements, no PRAGMA to
        remember.
        """
        for path in paths:
            self._conn.execute("DELETE FROM symbols WHERE file = ?", (path,))
            self._conn.execute("DELETE FROM refs WHERE file = ?", (path,))
            self._conn.execute("DELETE FROM files WHERE path = ?", (path,))

    def _write(self, row: FileSymbols, content_hash: str, when: str) -> None:
        self._forget([row.file])
        self._conn.execute(
            "INSERT INTO files(path, module, language, content_hash, symbol_count, "
            "reference_count, parse_error, error, indexed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row.file,
                row.module,
                row.language,
                content_hash,
                len(row.symbols),
                len(row.references),
                int(row.parse_error),
                row.error,
                when,
            ),
        )
        self._conn.executemany(
            "INSERT INTO symbols(name, qualified_name, kind, file, module, line, "
            "end_line, parent, language) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    s.name,
                    f"{s.parent}.{s.name}" if s.parent else s.name,
                    s.kind.value,
                    s.file,
                    s.module,
                    s.line,
                    s.end_line,
                    s.parent,
                    s.language,
                )
                for s in row.symbols
            ],
        )
        self._conn.executemany(
            "INSERT INTO refs(name, kind, file, module, line, from_symbol, "
            "resolution, language) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r.name,
                    r.kind.value,
                    r.file,
                    r.module,
                    r.line,
                    r.from_symbol,
                    r.resolution.value,
                    r.language,
                )
                for r in row.references
            ],
        )

    def refresh(
        self,
        root: Path,
        profile: Profile,
        patterns: tuple[str, ...] | None = None,
        *,
        rebuild: bool = False,
        extract: Extractor = extract_file,
    ) -> IndexStats:
        """Bring the index level with the tree, parsing only what changed.

        `patterns` defaults to the exclusion rules in `.sdd/config.yaml`, exactly as
        `extract_tree` does - one authority for "do not read this", not two.

        `rebuild=True` re-parses everything without deleting the file first, so a
        schema-compatible index can be refreshed in place after a grammar change.
        """
        if patterns is None:
            patterns = exclude_patterns()

        started = time.perf_counter()
        root = Path(root)
        known = self._known_hashes()
        seen: set[str] = set()
        parsed = unchanged = added = changed = unreadable = 0

        with self._conn:
            when = time.strftime("%Y-%m-%dT%H:%M:%S")
            for path, spec in iter_source_files(root, profile, patterns):
                relative = _relative(path, root)
                seen.add(relative)
                try:
                    content_hash = self._hash(path.read_bytes())
                except OSError:
                    # Left with an empty hash on purpose: it never matches, so the
                    # file is retried on every run instead of being cached as broken.
                    content_hash = ""

                previous = known.get(relative)
                if not rebuild and content_hash and previous == content_hash:
                    unchanged += 1
                    continue

                row = extract(path, spec, root)
                self._write(row, content_hash, when)
                parsed += 1
                if row.error:
                    unreadable += 1
                if previous is None:
                    added += 1
                else:
                    changed += 1

            removed = sorted(set(known) - seen)
            # A rename is a delete plus an add of identical bytes. Hashing makes that
            # visible for free, and a summary saying "1 renamed" instead of
            # "1 deleted, 1 added" is the difference between a report and a puzzle.
            gone_hashes = {known[p] for p in removed if known[p]}
            fresh_hashes = {
                str(r["content_hash"])
                for r in self._conn.execute(
                    "SELECT content_hash FROM files WHERE indexed_at = ?", (when,)
                )
            }
            renamed = len(gone_hashes & fresh_hashes)
            self._forget(removed)
            self._set_meta("root", root.resolve().as_posix())
            self._set_meta("profile", profile.name)
            self._set_meta("indexed_at", when)

        totals = self.counts()
        return IndexStats(
            root=root.resolve().as_posix(),
            profile=profile.name,
            store=self.path.as_posix(),
            files_seen=len(seen),
            files_parsed=parsed,
            files_unchanged=unchanged,
            files_added=added,
            files_changed=changed,
            files_deleted=len(removed),
            files_renamed=renamed,
            files_unreadable=unreadable,
            symbols=int(totals["symbols"]),
            references=int(totals["references"]),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            full_text_search=self.full_text_search,
        )

    # -- reading -----------------------------------------------------------------

    def counts(self) -> dict[str, Any]:
        """Totals, and the resolution split that keeps the edge count honest."""
        one = self._conn.execute
        by_resolution = {
            str(row["resolution"]): int(row["n"])
            for row in one(
                "SELECT resolution, COUNT(*) AS n FROM refs GROUP BY resolution"
            )
        }
        return {
            "store": self.path.as_posix(),
            "root": self.meta("root"),
            "profile": self.meta("profile"),
            "indexed_at": self.meta("indexed_at"),
            "files": int(one("SELECT COUNT(*) AS n FROM files").fetchone()["n"]),
            "symbols": int(one("SELECT COUNT(*) AS n FROM symbols").fetchone()["n"]),
            "references": int(one("SELECT COUNT(*) AS n FROM refs").fetchone()["n"]),
            "modules": [
                str(row["module"])
                for row in one("SELECT DISTINCT module FROM files ORDER BY module")
            ],
            "by_resolution": by_resolution,
            "full_text_search": self.full_text_search,
        }

    @property
    def is_indexed(self) -> bool:
        """Whether anything has been indexed yet.

        A `LIMIT 1` existence check, not `counts()`: the guard runs before every
        query and `counts()` scans 200k reference rows to build its resolution
        split. Cheap questions should not pay for expensive answers.
        """
        return self._conn.execute("SELECT 1 FROM files LIMIT 1").fetchone() is not None

    def require_indexed(self, hint: str) -> None:
        """Refuse to answer from an empty index, naming the command that fills it.

        The alternative - returning `[]` - is the failure this whole system is built
        against: "nothing was found" and "nothing was looked at" read identically to
        a caller, and the second is a missing step rather than a fact about the
        repository. One guard, called by every read path, so the message cannot
        drift between the CLI and the tool surface.
        """
        if not self.is_indexed:
            raise StoreError(
                f"the index at {self.path} is empty: {hint}. Returning no results "
                f"here would read as 'nothing exists', which is a different claim "
                f"from 'nothing was indexed'."
            )

    def lookup(
        self,
        name: str | None = None,
        *,
        kind: str | None = None,
        file: str | None = None,
        module: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Symbols by exact name, and/or by kind, file or module.

        Exact on name, not `LIKE`: this is the rung C-09 calls `exact`, and a
        substring match here would quietly answer a different question. Fuzzy
        matching is `search()`.
        """
        clauses: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("name", name),
            ("kind", kind),
            ("file", file),
            ("module", module),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                values.append(value)
        if not clauses:
            raise StoreError(
                "lookup needs at least one of name, kind, file or module - "
                "listing every symbol is not a question"
            )
        sql = (
            "SELECT name, qualified_name, kind, file, module, line, end_line, parent, "
            f"language FROM symbols WHERE {' AND '.join(clauses)} "
            "ORDER BY file, line LIMIT ?"
        )
        values.append(limit)
        return [dict(row) for row in self._conn.execute(sql, values)]

    def references(
        self,
        name: str | None = None,
        *,
        kind: str | None = None,
        file: str | None = None,
        min_line: int | None = None,
        max_line: int | None = None,
    ) -> list[dict[str, Any]]:
        """Edges by exact callee name, kind, or the file and line span they sit in.

        The mirror of `lookup` for the other table, and the only query C-08 needs: by
        `name` is "who names this" (answered by `refs_name`), by `file` with a line
        span is "what does this definition use" (answered by `refs_file`).

        No `limit`, unlike `lookup`: a traversal that silently stops reading edges
        at row 50 would return a blast radius with callers missing and nothing to
        say so. Callers that want fewer rows slice what they asked for.
        """
        clauses: list[str] = []
        values: list[Any] = []
        for column, value in (("name", name), ("kind", kind), ("file", file)):
            if value is not None:
                clauses.append(f"{column} = ?")
                values.append(value)
        if not clauses:
            raise StoreError(
                "references needs at least one of name, kind or file - "
                "listing every edge is not a question"
            )
        if min_line is not None:
            clauses.append("line >= ?")
            values.append(min_line)
        if max_line is not None:
            clauses.append("line <= ?")
            values.append(max_line)
        sql = (
            "SELECT name, kind, file, module, line, from_symbol, resolution, language "
            f"FROM refs WHERE {' AND '.join(clauses)} ORDER BY file, line, id"
        )
        return [dict(row) for row in self._conn.execute(sql, values)]

    def search(self, text: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Full-text search over names, qualified names and paths.

        Every word becomes a prefix term, so `ensureAva` finds `ensureAvaTaxEnabled`.
        The query is rebuilt from word characters rather than passed through: FTS5
        treats `-`, `"` and `*` as syntax, and a raw path would be a syntax error
        rather than a search.
        """
        if not self.full_text_search:
            raise StoreError(
                f"the index at {self.path} has no full-text index: this SQLite build "
                f"({sqlite3.sqlite_version}) has no FTS5 module. lookup() still works."
            )
        words = re.findall(r"[A-Za-z0-9_]+", text)
        if not words:
            raise StoreError(f"nothing searchable in {text!r}: no letters or digits")
        query = " ".join(f'"{word}"*' for word in words)
        sql = (
            "SELECT s.name, s.qualified_name, s.kind, s.file, s.module, s.line, "
            "s.end_line, s.parent, s.language FROM symbols_fts "
            "JOIN symbols AS s ON s.id = symbols_fts.rowid "
            "WHERE symbols_fts MATCH ? ORDER BY rank LIMIT ?"
        )
        try:
            return [dict(row) for row in self._conn.execute(sql, (query, limit))]
        except sqlite3.OperationalError as exc:
            raise StoreError(f"search failed for {text!r}: {exc}") from exc

    def files(self) -> list[dict[str, Any]]:
        """Every indexed file with its hash and counts. The audit view."""
        return [
            dict(row)
            for row in self._conn.execute(
                "SELECT path, module, language, content_hash, symbol_count, "
                "reference_count, parse_error, error, indexed_at FROM files ORDER BY path"
            )
        ]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def open_store(
    root: Path,
    *,
    create: bool = True,
    jspec_root: Path | None = None,
    index_root: Path | None = None,
) -> SymbolStore:
    """Open the index for a tree, translating a config problem into a StoreError.

    `create=False` for read paths. Opening a SQLite file creates it, so `jspec find`
    against a path that was never indexed - or a mistyped one - would leave an empty
    database behind and then complain that it is empty. A query should not write
    anything, least of all a file whose existence later looks like evidence that the
    root was indexed once.
    """
    try:
        directory = Path(index_root) if index_root is not None else index_dir(jspec_root)
        path = directory / db_filename(Path(root))
        if not create and not path.is_file():
            raise StoreError(
                f"no index for {Path(root).resolve().as_posix()}: nothing at {path}. "
                f"Run `jspec index <root> --profile <name>` first."
            )
        return SymbolStore.for_root(root, jspec_root=jspec_root, index_root=index_root)
    except ConfigError as exc:
        raise StoreError(str(exc)) from exc


__all__ = [
    "SCHEMA_VERSION",
    "IndexStats",
    "StoreError",
    "SymbolStore",
    "db_filename",
    "index_dir",
    "open_store",
    "store_path_for",
]
