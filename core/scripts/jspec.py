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

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / "src"

# Drop this script's own directory. Python puts it at the front of sys.path, and it
# holds a file named jspec.py - which shadows the jspec *package*, so `import
# jspec.cli` resolves to this file and it imports itself.
sys.path[:] = [p for p in sys.path if pathlib.Path(p or ".").resolve() != HERE]

# Front, not merely present. An editable install puts core/src on the path already,
# further down; the earlier version of this file checked only whether it was there
# at all and skipped the insert, leaving the script's own directory ahead of it. The
# launcher then worked only while the package was NOT installed.
source = str(SRC)
if source in sys.path:
    sys.path.remove(source)
sys.path.insert(0, source)

# The import must follow the sys.path insertion above, not precede it.
from jspec.cli import main

if __name__ == "__main__":
    sys.exit(main())
