"""Shared test setup: tell JSpec where its own root is.

**Why this file exists.** `jspec.paths.find_up` locates `profiles/` and `.sdd/` by
looking at an explicit argument, then `$JSPEC_ROOT`, then by walking up from the
package's own location. That last fallback works from a source checkout and from an
editable install, and **not** from a real one: CI runs `pip install ./core[dev,graph]`
without `-e`, so `jspec/config.py` lives in `site-packages`, and walking up from there
finds no `.sdd/` and no `profiles/`.

Every test that resolves a root explicitly - `load(name, SHIPPED)`,
`extract_tree(tmp_path, ..., patterns=())` - is unaffected either way, which is why
this went unnoticed until a test called `exclude_patterns()` with no argument.

Setting the variable here is not a workaround for the tests' benefit: it is exactly
what production does. `jspec/.mcp.json` sets `JSPEC_ROOT` for the MCP server, and the
plugin is the only context where the package is installed rather than run from source.
The tests now resolve the root the same way the shipped thing does.

`setdefault`, not assignment: a caller who deliberately points the suite at another
tree keeps their choice.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("JSPEC_ROOT", str(REPO_ROOT))
