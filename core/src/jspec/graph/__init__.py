"""The code graph: extract (C-06), store (C-07), traverse (C-08).

One package, because the three share a vocabulary - `Symbol`, `Reference`, and the
`module` and `resolution` columns - and splitting them across the flat module layout
would leave "where is the code graph?" with three answers. The contracts themselves
live in `jspec.contracts.graph`, alongside every other artifact contract, so nothing
here defines a shape.

All three are built. Traversal (`traverse.py`) answers over what the store holds and
never re-reads source: an unindexed root is an error, not an empty graph.
"""

from __future__ import annotations

from jspec.graph.extract import (
    ExtractError,
    ExtractReport,
    LanguageSpec,
    extract_file,
    extract_source,
    extract_tree,
    spec_for,
    supported,
)
from jspec.graph.traverse import blast_radius

__all__ = [
    "ExtractError",
    "ExtractReport",
    "LanguageSpec",
    "blast_radius",
    "extract_file",
    "extract_source",
    "extract_tree",
    "spec_for",
    "supported",
]
