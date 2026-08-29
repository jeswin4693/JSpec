"""Profile loading. The only component that reads `profiles/*.yaml`.

Every other component asks for a `Profile` and never touches the filesystem for one.
That keeps the number of places that know the directory layout at exactly one.

Everything here fails loudly. A profile that half-loads is worse than one that does
not load at all: the caller gets defaults, runs the wrong linter against the wrong
directories, and reports success. So a missing file, malformed YAML, an unknown
field or a failed constraint all raise `ProfileError` naming the file and the
problem - never a partial object, never a silent fallback.

Auto-detecting a profile for an unfamiliar repo is deliberately absent. That is
C-26's job (project profiler), and pre-empting it here with a weaker heuristic would
mean two detectors disagreeing.
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from jspec.contracts.profile import Profile

PROFILE_SUFFIX = ".yaml"


class ProfileError(Exception):
    """A profile could not be loaded. The message names the file and the fix."""


def profiles_dir(root: Path | None = None) -> Path:
    """Locate `profiles/`.

    Resolution order, first hit wins:
      1. the `root` argument - tests pass a tmp_path here
      2. `$JSPEC_ROOT` - set by the plugin's .mcp.json
      3. walk up from this file until a directory contains `profiles/`

    Step 3 exists so the package works from a source checkout with no environment
    set up, which is how it is run during development and in CI.
    """
    if root is not None:
        return Path(root)

    env_root = os.environ.get("JSPEC_ROOT")
    if env_root:
        return Path(env_root) / "profiles"

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "profiles"
        if candidate.is_dir():
            return candidate

    raise ProfileError(
        "cannot locate a profiles/ directory: no root argument, no $JSPEC_ROOT, "
        f"and nothing found walking up from {Path(__file__).resolve()}"
    )


def available(root: Path | None = None) -> list[str]:
    """Profile names on disk, sorted. Empty if the directory is missing."""
    directory = profiles_dir(root)
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob(f"*{PROFILE_SUFFIX}"))


def load(name: str, root: Path | None = None) -> Profile:
    """Load and validate one profile by name.

    Raises `ProfileError` for every failure mode, with the file path and, where the
    name is merely misspelled, the closest match. Guessing at the intended profile
    would be worse than saying so: running the Playwright commands against a Python
    service produces a confusing failure a long way from its cause.
    """
    directory = profiles_dir(root)
    path = directory / f"{name}{PROFILE_SUFFIX}"

    if not path.is_file():
        known = available(root)
        hint = ""
        close = difflib.get_close_matches(name, known, n=1)
        if close:
            hint = f" Did you mean {close[0]!r}?"
        elif known:
            hint = f" Available: {known}."
        else:
            hint = f" No profiles found in {directory}."
        raise ProfileError(f"no profile named {name!r} ({path}).{hint}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileError(f"{path} is not valid YAML: {exc}") from exc

    if raw is None:
        raise ProfileError(f"{path} is empty")
    if not isinstance(raw, dict):
        raise ProfileError(
            f"{path} must contain a mapping of fields, got {type(raw).__name__}"
        )

    # The filename is the identity. A profile whose `name` disagrees with its file
    # is loadable by one name and reports itself as another, which makes every log
    # line and error message ambiguous.
    declared = raw.get("name")
    if declared is not None and declared != name:
        raise ProfileError(
            f"{path} declares name {declared!r} but the filename says {name!r}; "
            f"rename the file or the field so they agree"
        )
    raw.setdefault("name", name)

    try:
        return Profile.model_validate(raw)
    except ValidationError as exc:
        problems = "\n".join(
            f"  {'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors()
        )
        raise ProfileError(f"{path} is not a valid profile:\n{problems}") from exc


__all__ = [
    "ProfileError",
    "available",
    "load",
    "profiles_dir",
]
