"""Zero-install launcher for the `jspec` command.

D-025 ships the tool surface as "Python scripts bundled ... invoked via Bash". The
implementation lives in `jspec.cli` so there is exactly one of it; this file only
puts `core/src` on the import path and hands over.

Why it exists at all: `core/pyproject.toml` declares a `jspec` console script, but
that only exists once the package is pip-installed. A skill must work in a checkout
where nothing has been installed - and in this repo pip is currently broken inside
the venv, so "just install it" is not available either. Two invocations, one code
path:

    jspec classify "..."                          # when pip-installed
    python core/scripts/jspec.py classify "..."   # anywhere, no install

Keep this file dependency-free and trivial. Logic added here would be logic that the
installed entry point does not run, which is how the two invocations start behaving
differently.
"""

from __future__ import annotations

import pathlib
import sys

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# The import must follow the sys.path insertion above, not precede it.
from jspec.cli import main

if __name__ == "__main__":
    sys.exit(main())
