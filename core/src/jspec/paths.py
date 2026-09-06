"""Finding the project root. One walk-up, used by everything that needs one.

`jspec.profiles` had this logic first, to locate `profiles/`. `jspec.config` needs
the same walk to locate `.sdd/`, and a second copy would drift the moment one of
them learned about a new environment variable (constitution rule 2). So it moved
here and both call it.

The resolution order is the interesting part, and it is the same for every caller:

  1. an explicit argument      - tests pass a tmp_path, and a caller analysing
                                 another repository passes its root
  2. `$JSPEC_ROOT`             - set by the plugin's .mcp.json
  3. walk up from this file    - so a source checkout with no environment set up
                                 works, which is how development and CI run it

Note what this resolves: **JSpec's own root**, not the root of whatever repository
is being analysed. `profiles/` and `.sdd/config.yaml` are JSpec's configuration and
travel with JSpec. The tree being indexed is always passed in explicitly.
"""

from __future__ import annotations

import os
from pathlib import Path


class RootNotFound(Exception):
    """No project root could be located. The message names every place that was tried."""


def find_up(marker: str, root: Path | None = None) -> Path:
    """Locate `marker` (a directory or file name) at the project root.

    Returns the path to the marker itself, not to the directory containing it, so
    callers get `<root>/profiles` or `<root>/.sdd` directly.
    """
    if root is not None:
        return Path(root) / marker

    env_root = os.environ.get("JSPEC_ROOT")
    if env_root:
        return Path(env_root) / marker

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / marker
        if candidate.exists():
            return candidate

    raise RootNotFound(
        f"cannot locate {marker!r}: no root argument, no $JSPEC_ROOT, and nothing "
        f"found walking up from {here}"
    )


__all__ = [
    "RootNotFound",
    "find_up",
]
