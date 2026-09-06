"""Code-graph contracts: what C-06 extracts, C-07 stores and C-08 traverses.

These three components share one vocabulary, so it is defined once here rather than
re-declared per module (constitution rule 2). C-07's table columns and C-08's
traversal both mirror `Symbol` and `Reference`; if this file changes, they change
with it, which is the point.

Two design choices carry most of the weight:

**Every row carries `module`** - the top-level sub-folder its file lives in. D-032
settled that the graph spans one root folder and every sub-folder in it, and that
the column exists **from the first migration** rather than being retrofitted. C-08
must be able to say *which sub-folder* a caller lives in; adding that later would
mean rewriting an index and every query over it.

**Every reference carries `resolution`** - how much the source text actually pins
down the target. `user.save()` cannot be resolved to a definite `save` without type
inference, and the two dishonest options are to drop the edge (understating blast
radius) or to link it to every `save` in the repo (drowning the answer). Recording
the edge *and* its certainty lets C-08 report "7 callers certain, 3 possible"
instead of one undifferentiated list. This is the same rule C-08 already applies to
its depth limit: a partial answer must never be shaped like a complete one.

Keep this module free of I/O and of model calls.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

ROOT_MODULE = "."
"""`module` for a file sitting directly in the index root, not in a sub-folder."""


class SymbolKind(str, Enum):
    """What a definition is.

    Deliberately coarse. Variables and constants are not here: they multiply row
    count by an order of magnitude and almost never answer "what breaks if I change
    this". Adding a kind is cheap; removing one that an index already contains means
    a re-index, so the bar is a component that reads it.
    """

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"


class ReferenceKind(str, Enum):
    """What kind of edge this is: one file pulling in another, or one thing calling
    another."""

    IMPORT = "import"
    CALL = "call"


class Resolution(str, Enum):
    """How much the source text pins down what a reference points at.

    This is a statement about *syntax*, not about the repository - C-06 sees one
    file at a time and cannot know which `save` is meant. Deciding that is C-07's
    and C-08's job, and they combine their own lookup with this flag.

      EXACT       a single bare identifier: `foo()`, `Foo()`, `import a.b`
      NAME_ONLY   a member on an unknown receiver: `user.save()` - the final name is
                  known, the owner is not
      UNRESOLVED  nothing usable was named: `handlers[i]()`, a computed import. Kept
                  rather than dropped so the edge count stays honest.
    """

    EXACT = "exact"
    NAME_ONLY = "name_only"
    UNRESOLVED = "unresolved"


class Symbol(BaseModel):
    """One definition, with the exact place it was found.

    `file` and `line` are what make every downstream answer checkable by hand. A
    graph that cannot be spot-checked is indistinguishable from a confident guess.
    """

    model_config = {"extra": "forbid"}

    kind: SymbolKind
    name: str = Field(min_length=1)
    file: str = Field(min_length=1, description="Root-relative, forward slashes.")
    module: str = Field(
        min_length=1,
        description="Top-level sub-folder of `file`, or '.' at the root (D-032).",
    )
    line: int = Field(ge=1, description="1-based first line of the definition.")
    end_line: int = Field(ge=1)
    parent: str | None = Field(
        default=None,
        description="Enclosing type name for a method; None for a top-level symbol.",
    )
    language: str = Field(min_length=1)


class Reference(BaseModel):
    """One edge: a call or an import, with where it was written and how sure we are.

    `from_symbol` is the definition the reference sits inside, or None at file
    level. Without it, an edge says a file touches a name but not which part of the
    file does, and C-08 can only ever answer at file granularity.
    """

    model_config = {"extra": "forbid"}

    kind: ReferenceKind
    name: str = Field(min_length=1, description="Callee name, or imported module path.")
    file: str = Field(min_length=1)
    module: str = Field(min_length=1)
    line: int = Field(ge=1)
    from_symbol: str | None = None
    resolution: Resolution
    language: str = Field(min_length=1)


class FileSymbols(BaseModel):
    """Everything one file yielded, including the reason it yielded nothing.

    A file that could not be read is recorded rather than dropped. Silence here is
    how an index ends up 3% short and nobody notices: the tool reports success, the
    blast radius is missing a caller, and the build breaks hours later.
    """

    model_config = {"extra": "forbid"}

    file: str = Field(min_length=1)
    module: str = Field(min_length=1)
    language: str = Field(min_length=1)
    symbols: list[Symbol] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    parse_error: bool = Field(
        default=False,
        description="The tree contains ERROR or MISSING nodes. Whatever did parse is "
        "still reported - error recovery means a broken file yields partial truth, "
        "which beats yielding none.",
    )
    error: str | None = Field(
        default=None,
        description="Set only when the file could not be read or parsed at all.",
    )


__all__ = [
    "ROOT_MODULE",
    "FileSymbols",
    "Reference",
    "ReferenceKind",
    "Resolution",
    "Symbol",
    "SymbolKind",
]
