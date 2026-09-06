"""Reading `.sdd/config.yaml`. Currently: the exclusion rules, and nothing else.

This module is deliberately thin, for the same reason C-25 shipped thin (D-030):
a config accessor grows one convenience property per component that touches it, and
the ones nobody reads still have to be kept true. So it exposes exactly what has a
consumer today - the patterns C-06 must not walk into - and grows when something
else actually reads something else.

WHY THE EXCLUSION LIST IS NOT DUPLICATED HERE
`config.yaml` already carries two lists that answer "do not read this":
`context.preferences.NEVER_INCLUDE` (build output, dependencies, caches) and
`security.never_send` (credentials, keys, the M2M repo's live API secrets). Writing
default patterns into this module would create a second authority, and the copy
nobody edits is the one that goes stale. There is no fallback list on purpose: a
missing config is an error with a path in it, not a silent switch to weaker rules.

Fail-closed, per `security.fail_closed` and master plan §46. If the exclusion rules
cannot be read, nothing is scanned - the alternative is walking into a `.env` and
finding out afterwards.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from jspec.paths import RootNotFound, find_up

SDD_DIR = ".sdd"
CONFIG_NAME = "config.yaml"


class ConfigError(Exception):
    """Configuration is missing or malformed. The message names the file and the fix."""


def config_path(root: Path | None = None) -> Path:
    """Locate `.sdd/config.yaml`."""
    try:
        return find_up(SDD_DIR, root) / CONFIG_NAME
    except RootNotFound as exc:
        raise ConfigError(str(exc)) from exc


def load(root: Path | None = None) -> dict[str, object]:
    """The whole config as a mapping. Every failure names the path."""
    path = config_path(root)
    if not path.is_file():
        raise ConfigError(f"no configuration at {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        kind = type(raw).__name__
        raise ConfigError(f"{path} must contain a mapping of sections, got {kind}")
    return raw


@lru_cache(maxsize=8)
def _cached_excludes(root_key: str | None) -> tuple[str, ...]:
    root = Path(root_key) if root_key else None
    raw = load(root)

    context = raw.get("context")
    never_include: list[str] = []
    if isinstance(context, dict):
        preferences = context.get("preferences")
        if isinstance(preferences, dict):
            value = preferences.get("NEVER_INCLUDE")
            if isinstance(value, list):
                never_include = [str(v) for v in value]

    security = raw.get("security")
    never_send: list[str] = []
    if isinstance(security, dict):
        value = security.get("never_send")
        if isinstance(value, list):
            never_send = [str(v) for v in value]

    if not never_include and not never_send:
        raise ConfigError(
            f"{config_path(root)} declares no exclusions: expected "
            f"context.preferences.NEVER_INCLUDE and/or security.never_send. "
            f"Refusing to scan rather than walk into .git, .venv or a .env file."
        )

    # Order is not meaningful - these are matched as a set - but sorting keeps the
    # value stable, which keeps anything that logs or hashes it stable too.
    return tuple(sorted(set(never_include) | set(never_send)))


def exclude_patterns(root: Path | None = None) -> tuple[str, ...]:
    """Glob patterns that must never be read, from both config lists combined.

    Merged because the distinction is about *why* a path is forbidden, not about
    when: `NEVER_INCLUDE` is noise, `never_send` is dangerous, and a scanner must
    walk into neither. Anything that needs to tell them apart should read `load()`.
    """
    return _cached_excludes(str(root) if root is not None else None)


__all__ = [
    "ConfigError",
    "config_path",
    "exclude_patterns",
    "load",
]
