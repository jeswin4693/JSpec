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
from pathlib import Path

import yaml
from pydantic import ValidationError

from jspec.contracts.profile import Profile
from jspec.paths import RootNotFound, find_up

PROFILE_SUFFIX = ".yaml"
PROFILES_DIR_NAME = "profiles"


class ProfileError(Exception):
    """A profile could not be loaded. The message names the file and the fix."""


def profiles_dir(root: Path | None = None) -> Path:
    """Locate `profiles/`.

    The `root` argument names the profiles directory itself, not the project root -
    tests pass a tmp_path holding loose .yaml files. Everything else (`$JSPEC_ROOT`,
    then walking up from this file) is the shared search in `jspec.paths`, which
    `jspec.config` also uses; keeping a second copy of that walk here is how the two
    would end up disagreeing about where the project is.
    """
    if root is not None:
        return Path(root)

    try:
        return find_up(PROFILES_DIR_NAME)
    except RootNotFound as exc:
        raise ProfileError(str(exc)) from exc


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
