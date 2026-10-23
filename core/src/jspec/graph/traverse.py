"""C-08 blast radius: what is affected if this changes, and how sure the answer is.

C-06 reads the source, C-07 remembers it. This walks what they stored, so that "who
calls this, and who calls them?" is a query with a checkable answer rather than a
text search that misses every indirect caller.

TWO GRAPHS, ONE WALK
A *name* is answered over the call graph: nodes are definitions, an edge says one
definition's body calls another. A *file* is answered over the import graph: nodes are
files, an edge says one file imports another. They are kept apart because mixing them
over-claims - every importer of a module would become a caller of every function in it.
Each can be walked in two directions: `dependents` (who is affected if this changes)
and `dependencies` (what this relies on).

WHY BREADTH-FIRST
Not for speed - both orders cost O(nodes + edges). BFS explores in rings of distance,
so ring 1 is the code that breaks immediately and ring 4 probably never does; the first
time a node is reached is by the shortest connection, which is the chain reported with
it; and "stopped at depth 4" means something. A depth limit on DFS is meaningless -
deep down one path, untouched on another - and a truncated answer shaped like a complete
one is what D-034 forbids. Cycles are handled by the visited set, so `a -> b -> a` ends.

CERTAIN AND POSSIBLE
72% of the Made2Manage graph is `name_only`: `page.fill()`, `this.save()`, a member on a
receiver the parser cannot type. A bare count would be mostly guesswork, so every edge is
either certain or possible, and a result is certain only if *some* chain to it is certain
end to end. The walk therefore tracks `(node, tainted)`, where tainted means "a possible
edge is on the path so far": reaching a node untainted is certain, reaching it only
tainted is possible. It is one pass over at most twice the nodes.

An edge is certain only when the syntax and the index together leave no alternative:

  call    a bare name (`resolution = exact`) that lexical scope or an import pins to
          one definition: a definition in the same file, else a definition in a file
          this file imports. A bare name with neither is possible even when the repo
          defines it once - the call may be to a library function of the same name.
          A member call (`name_only`) is never certain: the name is known, the owner
          is not.
  import  a relative path that resolves to exactly one file; or a dotted or path-like
          name of two or more segments that matches exactly one file's tail.

**Every simplification here errs toward "possible", never toward "certain".**
Under-claiming certainty costs a reader a look; over-claiming it costs a wrong "safe to
change". Forward and reverse use the same `_Graph.targets`, so they cannot disagree
about whether an edge is certain.

WHAT IT CANNOT SEE
Edges are calls and imports only. A function passed as a value, a decorator, an
inheritance link, a type reference and a call through a computed expression leave no
edge. The answer says so (`limits`) and counts what it knows it could not follow
(`index.unresolved_calls`, files that failed to parse) instead of reading as complete.
"""

from __future__ import annotations

import posixpath
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jspec.graph.extract import ExtractError, spec_for
from jspec.graph.store import StoreError, SymbolStore

DEFAULT_DEPTH = 4
"""Rings searched by default. Ring 1 breaks at once; past ring 4 on a real suite the
`possible` set is mostly noise. The answer reports whether the limit was what stopped
it, so a caller who needs more asks for more."""

MAX_STATES = 20_000
"""A hard ceiling on `(node, tainted)` states, so one hot name cannot make a query
unbounded. Hitting it is reported as `stopped_by: "size"`, never swallowed."""

DIRECTIONS = ("dependents", "dependencies")

CALLABLE_KINDS = frozenset({"function", "method", "class"})
"""What a call can land on. An interface cannot be called, and counting one as a
candidate would dilute every certain edge into a possible one."""

_EVERYTHING = 1_000_000
"""`lookup` demands a limit; this is "all of them" for a column of names."""

_EXTERNAL_SHOWN = 25


class TraverseError(StoreError):
    """The question cannot be answered as asked. Names the fix."""


# --- the graph's vocabulary --------------------------------------------------------


@dataclass(frozen=True)
class Node:
    """A definition, or a file. Hashable, so it can live in the visited set."""

    kind: str  # function | method | class | interface | file
    name: str
    file: str
    module: str
    line: int
    end_line: int
    parent: str | None = None

    @classmethod
    def symbol(cls, row: dict[str, Any]) -> Node:
        return cls(
            kind=row["kind"],
            name=row["name"],
            file=row["file"],
            module=row["module"],
            line=row["line"],
            end_line=row["end_line"],
            parent=row["parent"],
        )

    @classmethod
    def of_file(cls, path: str, module: str) -> Node:
        return cls("file", path, path, module, 1, 1)

    @property
    def label(self) -> str:
        if self.kind == "file":
            return self.file
        qualified = f"{self.parent}.{self.name}" if self.parent else self.name
        return f"{qualified} ({self.file}:{self.line})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file": self.file,
            "line": self.line,
            "module": self.module,
            "parent": self.parent,
        }


@dataclass(frozen=True)
class Edge:
    """One link: where it is written, and how firmly the index pins it down.

    `line` is in the file of whichever end *uses* the other - the call site, or the
    import statement - so a person can open it and check.
    """

    line: int
    certain: bool
    resolution: str  # exact | name_only | import
    candidates: int  # how many definitions or files the name could have meant


@dataclass(frozen=True)
class _Step:
    depth: int
    previous: tuple[Node, bool] | None
    edge: Edge | None


State = tuple[Node, bool]


def _better(new: Edge, old: Edge | None) -> bool:
    """Prefer a certain edge, then the earlier line. Deterministic either way."""
    if old is None:
        return True
    if new.certain != old.certain:
        return new.certain
    return new.line < old.line


# --- the per-query view of the store -----------------------------------------------


class _Graph:
    """Everything a walk asks the store, loaded lazily and cached for one query."""

    def __init__(self, store: SymbolStore) -> None:
        self.store = store
        self._defs: dict[str, list[Node]] = {}
        self._def_sets: dict[str, frozenset[Node]] = {}
        self._refs: dict[str, list[dict[str, Any]]] = {}
        self._members: dict[str, dict[Node, Edge]] = {}
        self._enclosing: dict[tuple[str, str | None, int], Node] = {}
        self._in_file: dict[str, dict[str, list[Node]]] = {}
        self._file_info: dict[str, tuple[str, str]] | None = None
        self._imports: (
            tuple[dict[str, dict[str, Edge]], dict[str, dict[str, Edge]]] | None
        )
        self._imports = None
        self._external_imports: dict[str, set[tuple[str, int]]] = {}
        self.unresolved: set[tuple[str, int, str]] = set()
        # name -> where it was used. A set of places, not a counter: a node can be
        # expanded twice (once tainted, once not) and must not be counted twice.
        self.external: dict[str, set[tuple[str, int]]] = {}

    # -- definitions -----------------------------------------------------------

    def callable_defs(self, name: str) -> list[Node]:
        if name not in self._defs:
            rows = self.store.lookup(name, limit=_EVERYTHING)
            self._defs[name] = [
                Node.symbol(r) for r in rows if r["kind"] in CALLABLE_KINDS
            ]
        return self._defs[name]

    def symbols_in(self, file: str) -> list[Node]:
        return [n for group in self._by_name_in(file).values() for n in group]

    def _by_name_in(self, file: str) -> dict[str, list[Node]]:
        if file not in self._in_file:
            grouped: dict[str, list[Node]] = {}
            for row in self.store.lookup(file=file, limit=_EVERYTHING):
                grouped.setdefault(row["name"], []).append(Node.symbol(row))
            self._in_file[file] = grouped
        return self._in_file[file]

    def file_info(self) -> dict[str, tuple[str, str]]:
        """path -> (module, language) for every indexed file."""
        if self._file_info is None:
            self._file_info = {
                f["path"]: (f["module"], f["language"]) for f in self.store.files()
            }
        return self._file_info

    def enclosing(self, ref: dict[str, Any]) -> Node:
        """The definition a reference is written inside, found by line, not by name.

        `from_symbol` is a bare name, and two classes in one file can both have a
        `save`. The line range is what tells them apart; the name only narrows the
        search. A reference at file level - or one whose container cannot be found -
        is attributed to the file, which is true and cannot be wrong.
        """
        key = (ref["file"], ref["from_symbol"], ref["line"])
        if key not in self._enclosing:
            best: Node | None = None
            for node in self._by_name_in(ref["file"]).get(ref["from_symbol"], ()):
                if node.line <= ref["line"] <= node.end_line and (
                    best is None or node.end_line - node.line < best.end_line - best.line
                ):
                    best = node
            self._enclosing[key] = best or Node.of_file(ref["file"], ref["module"])
        return self._enclosing[key]

    # -- the call graph --------------------------------------------------------

    def targets(
        self, ref: dict[str, Any], only: Node | None = None
    ) -> list[tuple[Node, Edge]]:
        """Which definitions a call reference can mean, each with its certainty.

        The single place that decides certainty for calls; both directions use it.
        A bare name is looked for in its own file first, then in the files this file
        imports - lexical scope, then the import that brought it in. Only a name
        found there, once, is certain. A member call has no such narrowing:
        `other.write()` in a file that defines `write` is not that `write`.

        `only` keeps just one candidate. A reverse walk asks about a single node, and
        building an edge per candidate for a name with thirty definitions would be
        paid for on every one of its thousands of references.
        """
        candidates = self.callable_defs(ref["name"])
        if not candidates:
            return []
        line = ref["line"]
        if ref["resolution"] != "exact":
            edge = Edge(line, False, "name_only", len(candidates))
            chosen = candidates
        else:
            here = [c for c in candidates if c.file == ref["file"]]
            linked = self.import_tables()[0].get(ref["file"], {})
            via = [c for c in candidates if c.file in linked]
            if here:
                chosen, certain = here, len(here) == 1
            elif via:
                chosen = via
                certain = len(via) == 1 and linked[via[0].file].certain
            else:
                chosen, certain = candidates, False
            edge = Edge(line, certain, "exact", len(chosen))
        if only is None:
            return [(c, edge) for c in chosen]
        # Set membership, not `==` down a list: on a name defined 177 times, the list
        # scan was paid on each of its thousands of references, for each definition.
        pool = self._def_set(ref["name"]) if chosen is candidates else frozenset(chosen)
        return [(only, edge)] if only in pool else []

    def _def_set(self, name: str) -> frozenset[Node]:
        if name not in self._def_sets:
            self._def_sets[name] = frozenset(self.callable_defs(name))
        return self._def_sets[name]

    def _call_refs(self, name: str) -> list[dict[str, Any]]:
        """Every followable call naming `name`, read once however many definitions
        share it. `unresolved` is dropped: its recorded name is a syntax form, not a
        callee, and could only ever match a definition by coincidence."""
        if name not in self._refs:
            self._refs[name] = [
                r
                for r in self.store.references(name, kind="call")
                if r["resolution"] != "unresolved"
            ]
        return self._refs[name]

    def _member_callers(self, name: str) -> dict[Node, Edge]:
        """Callers reached by a member call. Identical for every definition of `name`:
        `x.save()` is a possible call to each `save` equally, so it is computed once
        and shared, not once per definition (177 page objects each define `button`)."""
        if name not in self._members:
            found: dict[Node, Edge] = {}
            edge_count = len(self.callable_defs(name))
            for ref in self._call_refs(name):
                if ref["resolution"] == "exact":
                    continue
                caller = self.enclosing(ref)
                edge = Edge(ref["line"], False, "name_only", edge_count)
                if _better(edge, found.get(caller)):
                    found[caller] = edge
            self._members[name] = found
        return self._members[name]

    def callers(self, node: Node) -> dict[Node, Edge]:
        if node not in self._def_set(node.name):
            return {}  # an interface cannot be called, so nothing calls it
        found = {c: e for c, e in self._member_callers(node.name).items() if c != node}
        for ref in self._call_refs(node.name):
            if ref["resolution"] != "exact":
                continue
            for _, edge in self.targets(ref, only=node):
                caller = self.enclosing(ref)
                if caller != node and _better(edge, found.get(caller)):
                    found[caller] = edge
        return found

    def callees(self, node: Node) -> dict[Node, Edge]:
        found: dict[Node, Edge] = {}
        refs = self.store.references(
            file=node.file, kind="call", min_line=node.line, max_line=node.end_line
        )
        for ref in refs:
            if ref["resolution"] == "unresolved":
                self.unresolved.add((ref["file"], ref["line"], ref["name"]))
                continue
            targets = self.targets(ref)
            if not targets:
                self.external.setdefault(ref["name"], set()).add(
                    (ref["file"], ref["line"])
                )
            for target, edge in targets:
                if target != node and _better(edge, found.get(target)):
                    found[target] = edge
        return found

    # -- the import graph ------------------------------------------------------

    def import_tables(
        self,
    ) -> tuple[dict[str, dict[str, Edge]], dict[str, dict[str, Edge]]]:
        """`(forward, reverse)`: importer -> targets, and target -> importers.

        Built once per query by resolving every import in the index to files. There
        is no way to ask the store "who imports this file" directly, because the
        store keeps the text of the import, and turning that text into a file is the
        resolution below.
        """
        if self._imports is not None:
            return self._imports
        tails = self._stem_index()
        forward: dict[str, dict[str, Edge]] = {}
        reverse: dict[str, dict[str, Edge]] = {}
        for ref in self.store.references(kind="import"):
            importer = ref["file"]
            paths, certain = _resolve_import(importer, ref["name"], tails)
            paths = [p for p in paths if p != importer]
            if not paths:
                self._external_imports.setdefault(importer, set()).add(
                    (ref["name"], ref["line"])
                )
                continue
            edge = Edge(ref["line"], certain, "import", len(paths))
            for path in paths:
                for table, a, b in ((forward, importer, path), (reverse, path, importer)):
                    row = table.setdefault(a, {})
                    if _better(edge, row.get(b)):
                        row[b] = edge
        self._imports = (forward, reverse)
        return self._imports

    def _stem_index(self) -> dict[str, list[tuple[str, str]]]:
        """Last path segment -> [(stem, file)], for matching an import by its tail.

        A stem is a path without its extension. A file named as an entry stem for
        its language (`entry_stems` in languages.yaml) is also registered under its
        directory, because importing the directory means importing that file.
        """
        tails: dict[str, list[tuple[str, str]]] = {}

        def add(stem: str, path: str) -> None:
            tails.setdefault(stem.rpartition("/")[2], []).append((stem, path))

        for path, (_, language) in self.file_info().items():
            stem = posixpath.splitext(path)[0]
            add(stem, path)
            head, _, base = stem.rpartition("/")
            try:
                entry = spec_for(language).entry_stems
            except ExtractError:
                entry = frozenset()
            if head and base in entry:
                add(head, path)
        return tails

    def importers(self, node: Node) -> dict[Node, Edge]:
        return self._as_nodes(self.import_tables()[1].get(node.file, {}))

    def imports_of(self, node: Node) -> dict[Node, Edge]:
        forward = self.import_tables()[0]
        for name, line in self._external_imports.get(node.file, ()):
            self.external.setdefault(name, set()).add((node.file, line))
        return self._as_nodes(forward.get(node.file, {}))

    def _as_nodes(self, row: dict[str, Edge]) -> dict[Node, Edge]:
        info = self.file_info()
        return {Node.of_file(path, info[path][0]): edge for path, edge in row.items()}

    # -- the walk's one entry point ---------------------------------------------

    def expander(self, mode: str, direction: str) -> Callable[[Node], dict[Node, Edge]]:
        table = {
            ("call", "dependents"): self.callers,
            ("call", "dependencies"): self.callees,
            ("file", "dependents"): self.importers,
            ("file", "dependencies"): self.imports_of,
        }
        return table[(mode, direction)]


def _resolve_import(
    importer: str, name: str, tails: dict[str, list[tuple[str, str]]]
) -> tuple[list[str], bool]:
    """Turn the text of an import into indexed files, and say how sure that is.

    A relative name is resolved against the importing file's directory and must match
    a stem exactly (a guessed extension is possible, never certain). Anything else is matched by its tail, on whole path segments, so
    `a.b` finds `src/a/b` and not `src/data/b`. One segment is never certain: `os`
    or `react` would otherwise "certainly" mean whichever local file shares the name.
    """
    if name.startswith("."):
        if "/" in name:
            want = posixpath.normpath(posixpath.join(posixpath.dirname(importer), name))
        else:
            dots = len(name) - len(name.lstrip("."))
            base = posixpath.dirname(importer)
            for _ in range(dots - 1):
                base = posixpath.dirname(base)
            rest = name[dots:].replace(".", "/")
            want = posixpath.normpath(posixpath.join(base, rest)) if rest else base
        want = "" if want == "." else want
        paths = [p for s, p in tails.get(want.rpartition("/")[2], ()) if s == want]
        if paths:
            return paths, len(paths) == 1
        # `./x.js` written for a file `x.ts` is common in modern source. It is a match
        # by guesswork about the extension, so it is never certain.
        bare = posixpath.splitext(want)[0]
        paths = [p for s, p in tails.get(bare.rpartition("/")[2], ()) if s == bare]
        return paths, False

    want = (name if "/" in name else name.replace(".", "/")).strip("/")
    if not want:
        return [], False
    last = want.rpartition("/")[2]
    paths = [p for s, p in tails.get(last, ()) if s == want or s.endswith("/" + want)]
    return paths, len(paths) == 1 and "/" in want


# --- the walk ----------------------------------------------------------------------


def _walk(
    expand: Callable[[Node], dict[Node, Edge]], seeds: list[Node], depth_limit: int
) -> tuple[dict[State, _Step], str | None]:
    """Breadth-first over `(node, tainted)` states. Returns what it reached, and why
    it stopped if something other than running out of graph stopped it.

    The ring *after* the limit is peeked at rather than skipped: only by looking can
    the answer say "there was more" instead of "this is all of it".
    """
    # A node is expanded once per state, and can be in two (tainted and not). Its
    # neighbours do not depend on how it was reached, so ask the store once.
    cache: dict[Node, dict[Node, Edge]] = {}

    def neighbours(node: Node) -> dict[Node, Edge]:
        if node not in cache:
            cache[node] = expand(node)
        return cache[node]

    reached: dict[State, _Step] = {(s, False): _Step(0, None, None) for s in seeds}
    frontier: list[State] = list(reached)
    stopped: str | None = None
    depth = 0
    while frontier and stopped is None:
        depth += 1
        fresh: list[State] = []
        for state in frontier:
            node, tainted = state
            for neighbour, edge in neighbours(node).items():
                nxt: State = (neighbour, tainted or not edge.certain)
                # A node already reached certainly needs no tainted twin: everything
                # reachable from the twin is reachable from the original, no weaker.
                if nxt in reached or (nxt[1] and (neighbour, False) in reached):
                    continue
                if depth > depth_limit:
                    stopped = "depth"
                    break
                if len(reached) >= MAX_STATES:
                    stopped = "size"
                    break
                reached[nxt] = _Step(depth, state, edge)
                fresh.append(nxt)
            if stopped:
                break
        frontier = fresh
    return reached, stopped


def _chain(reached: dict[State, _Step], state: State, direction: str) -> list[Node]:
    """The connection, written in the direction the calls (or imports) run."""
    nodes: list[Node] = []
    cursor: State | None = state
    while cursor is not None:
        nodes.append(cursor[0])
        cursor = reached[cursor].previous
    # Walking back from the result reaches the target last: that is already
    # "result calls ... calls target", the order for dependents. Dependencies run
    # the other way - the target uses the first hop - so flip it.
    return nodes if direction == "dependents" else nodes[::-1]


# --- finding the target ------------------------------------------------------------


def _resolve_target(
    graph: _Graph, target: str, file: str | None, direction: str
) -> tuple[str, list[Node], list[Node]]:
    """`(mode, named targets, extra seeds)`. Mode is `call` for a name, `file` for a path.

    Extra seeds are the members of a class target. Changing a class changes what its
    methods do, so a blast radius that started at the class alone would miss every
    caller of every method.
    """
    store = graph.store
    info = graph.file_info()

    if file is not None:
        if file not in info:
            raise TraverseError(
                f"{file!r} is not an indexed file in {store.path}; "
                f"`jspec find --file <path>` lists what is indexed"
            )
        rows = store.lookup(target, file=file, limit=_EVERYTHING)
        if not rows:
            where = [r["file"] for r in store.lookup(target, limit=10)]
            hint = f" It is defined in: {where}." if where else ""
            raise TraverseError(f"no definition named {target!r} in {file}.{hint}")
        return _symbol_seeds(graph, [Node.symbol(r) for r in rows], direction)

    if target in info:
        return "file", [Node.of_file(target, info[target][0])], []

    rows = store.lookup(target, limit=_EVERYTHING)
    if rows:
        return _symbol_seeds(graph, [Node.symbol(r) for r in rows], direction)

    # Last, a unique path tail: `avalaraSetupPage.ts` instead of the whole path.
    tail = "/" + target
    matches = [p for p in info if p.endswith(tail)]
    if len(matches) == 1:
        return "file", [Node.of_file(matches[0], info[matches[0]][0])], []
    if len(matches) > 1:
        raise TraverseError(
            f"{target!r} matches {len(matches)} files: {matches[:8]}. Give the full path."
        )

    near = (
        store.search(target, limit=5)
        if store.full_text_search and _searchable(target)
        else []
    )
    hint = (
        " Similar: "
        + ", ".join(f"{r['qualified_name']} ({r['file']}:{r['line']})" for r in near)
        if near
        else ""
    )
    raise TraverseError(f"nothing named {target!r} in {store.path}.{hint}")


def _searchable(text: str) -> bool:
    return any(ch.isalnum() or ch == "_" for ch in text)


def _symbol_seeds(
    graph: _Graph, named: list[Node], direction: str
) -> tuple[str, list[Node], list[Node]]:
    members: list[Node] = []
    if direction == "dependents":
        for node in named:
            if node.kind != "class":
                continue
            members += [
                m
                for m in graph.symbols_in(node.file)
                if m.parent == node.name
                and node.line <= m.line <= node.end_line
                and m != node
            ]
    return "call", named, [m for m in members if m not in named]


# --- the import graph, for callers that are not asking a blast-radius question -------


def imported_by(store: SymbolStore) -> dict[str, set[str]]:
    """Target file -> the files that import it, at any certainty.

    One pass, no traversal. The project profiler (C-26) asks "which folder do the most
    others import?" and needs the edges, not a walk; handing it the resolved table
    keeps import resolution in one place instead of growing a second copy there.
    """
    reverse = _Graph(store).import_tables()[1]
    return {target: set(importers) for target, importers in reverse.items()}


# --- the answer --------------------------------------------------------------------


def blast_radius(
    store: SymbolStore,
    target: str,
    *,
    file: str | None = None,
    direction: str = "dependents",
    depth: int = DEFAULT_DEPTH,
    limit: int = 100,
) -> dict[str, Any]:
    """What is affected by a change to `target`, or what `target` relies on.

    `target` is a definition name, or an indexed file path. `file` narrows a name
    that is defined in several places. A name shared by several definitions is not
    refused: they are all searched, listed under `targets`, and `ambiguous` says so -
    each edge's certainty already accounts for it.

    Counts are always complete. `limit` caps only the rows printed, and `omitted`
    says how many were left out, so a long answer never reads as a short one.
    """
    started = time.perf_counter()
    if direction not in DIRECTIONS:
        raise ValueError(
            f"direction must be one of {list(DIRECTIONS)}, got {direction!r}"
        )
    if depth < 1:
        raise ValueError(f"depth must be at least 1, got {depth}")
    if limit < 0:
        raise ValueError(f"limit must not be negative, got {limit}")

    store.require_indexed("run `jspec index <root> --profile <name>` first")
    graph = _Graph(store)
    mode, named, extra = _resolve_target(graph, target, file, direction)

    reached, stopped = _walk(graph.expander(mode, direction), named + extra, depth)

    # One row per node. A node reached both ways is certain: a certain chain exists.
    best: dict[Node, tuple[State, _Step]] = {}
    for state, step in reached.items():
        node, tainted = state
        if step.previous is None:
            continue
        held = best.get(node)
        if held is None or (held[0][1] and not tainted):
            best[node] = (state, step)

    rows: list[dict[str, Any]] = []
    for node, (state, step) in best.items():
        assert step.edge is not None  # only seeds lack one, and they were skipped
        user = node if direction == "dependents" else step.previous[0]  # type: ignore[index]
        rows.append(
            {
                **node.to_dict(),
                "depth": step.depth,
                "certainty": "possible" if state[1] else "certain",
                "resolution": step.edge.resolution,
                "candidates": step.edge.candidates,
                "link": f"{user.file}:{step.edge.line}",
                "chain": [n.label for n in _chain(reached, state, direction)],
            }
        )
    rows.sort(
        key=lambda r: (
            r["certainty"] != "certain",
            r["depth"],
            r["file"],
            r["line"],
            r["name"],
        )
    )

    certain = sum(1 for r in rows if r["certainty"] == "certain")
    by_module: dict[str, dict[str, int]] = {}
    by_depth: dict[int, dict[str, int]] = {}
    files: dict[str, dict[str, Any]] = {}
    for r in rows:
        for table, key in ((by_module, r["module"]), (by_depth, r["depth"])):
            table.setdefault(key, {"certain": 0, "possible": 0})[r["certainty"]] += 1
        held = files.setdefault(
            r["file"],
            {
                "file": r["file"],
                "module": r["module"],
                "certainty": "possible",
                "nodes": 0,
            },
        )
        held["nodes"] += 1
        if r["certainty"] == "certain":
            held["certainty"] = "certain"
    file_rows = sorted(
        files.values(), key=lambda f: (f["certainty"] != "certain", f["file"])
    )

    reached_depth = max((r["depth"] for r in rows), default=0)
    complete = stopped is None
    total = len(rows)
    label = named[0].label if len(named) == 1 else f"{target} ({len(named)} definitions)"
    summary = (
        f"{certain} certain and {total - certain} possible {direction} of {label}, "
        f"{reached_depth} hop(s) deep; "
        + (
            "the search ran out of graph, so this is everything the index can see."
            if complete
            else f"STOPPED by the {stopped} limit - more exist beyond this."
        )
    )

    counts = store.counts()
    index_files = store.files()
    limits = [
        (
            "Edges are calls and imports only: a function passed as a value, a decorator, "
            "an inheritance link or a type reference leaves none."
        ),
        "A call through a computed expression has no usable name and cannot be followed.",
    ]
    if mode == "file":
        limits.append(
            "An import is matched to a file by its path text; an alias or a dynamic "
            "import that is not a plain path is reported under `external`."
        )

    return {
        "target": target,
        "mode": mode,
        "direction": direction,
        "root": counts["root"],
        "summary": summary,
        "targets": {
            "definitions": [n.to_dict() for n in named],
            "ambiguous": len(named) > 1,
            "members_included": len(extra),
        },
        "depth": {
            "limit": depth,
            "reached": reached_depth,
            "complete": complete,
            "stopped_by": stopped,
        },
        "counts": {
            "certain": certain,
            "possible": total - certain,
            "total": total,
            "files": len(file_rows),
            "by_module": dict(sorted(by_module.items())),
            "by_depth": [{"depth": d, **by_depth[d]} for d in sorted(by_depth)],
        },
        "affected": rows[:limit],
        "omitted": max(total - limit, 0),
        "files": file_rows[:limit],
        "files_omitted": max(len(file_rows) - limit, 0),
        "external": {
            "total": sum(len(v) for v in graph.external.values()),
            "distinct": len(graph.external),
            "top": [
                {"name": name, "count": len(places)}
                for name, places in sorted(
                    graph.external.items(), key=lambda kv: (-len(kv[1]), kv[0])
                )[:_EXTERNAL_SHOWN]
            ],
        }
        if direction == "dependencies"
        else None,
        "unresolved_calls_in_reach": len(graph.unresolved)
        if direction == "dependencies"
        else None,
        "index": {
            "files": counts["files"],
            "unresolved_calls": counts["by_resolution"].get("unresolved", 0),
            "files_with_parse_errors": sum(1 for f in index_files if f["parse_error"]),
            "files_unreadable": sum(1 for f in index_files if f["error"]),
        },
        "limits": limits,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


__all__ = [
    "CALLABLE_KINDS",
    "DEFAULT_DEPTH",
    "DIRECTIONS",
    "MAX_STATES",
    "Edge",
    "Node",
    "TraverseError",
    "blast_radius",
    "imported_by",
]
