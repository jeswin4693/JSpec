"""The code graph: extract (C-06), store (C-07), traverse (C-08).

One package, because the three share a vocabulary - `Symbol`, `Reference`, and the
`module` and `resolution` columns - and splitting them across the flat module layout
would leave "where is the code graph?" with three answers. The contracts themselves
live in `jspec.contracts.graph`, alongside every other artifact contract, so nothing
here defines a shape.

C-06 is built. C-07 and C-08 are not: `jspec tools` names them as the blockers on
`blast_radius` and `find_existing`, and they stay blocked rather than returning a
plausible empty graph.
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

__all__ = [
    "ExtractError",
    "ExtractReport",
    "LanguageSpec",
    "extract_file",
    "extract_source",
    "extract_tree",
    "spec_for",
    "supported",
]
