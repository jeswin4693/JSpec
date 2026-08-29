"""Profile contract: the one place a project-specific fact may live.

Constitution rule 20 (D-011) says nothing Playwright-, M2M- or Aptean-specific
belongs in `core/`. That rule needs somewhere for those facts to go, or it just
pushes them into hiding - which is what happened: `.sdd/config.yaml` grew a
`validation.python` block holding this repo's own lint and test commands, under a
comment saying per-domain runners belong in a profile. This module is that home.

The boundary test, and the only one that matters: **can a new kind of project be
added by writing only data?** If onboarding a Go service needs a code change, the
generalisation boundary is in the wrong place.

Deliberately NOT here yet, each deferred until something reads it:

  - `extends` / override resolution - no profile inherits from another yet, and an
    inheritance system with one user is a configuration language nobody asked for.
  - `risk_signals` - C-16 is a stub; it should say what shape it needs.
  - `templates` - C-12 has 1 of 9 templates; same reason.
  - `shared_dirs` - C-16's correlation amplifier, which does not exist.

Adding a field later is cheap. Removing one that profiles already set is not, so
the bar for adding is a live consumer, not a plausible one.

Keep this module free of I/O and of model calls - loading lives in `jspec.profiles`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from jspec.contracts.base import Id


class Validation(BaseModel):
    """The commands that decide whether work is actually finished.

    Master plan §40: project-native commands only, never invented. Read them out of
    the repo - a `test` command that does not exist is worse than none, because it
    fails in a way that looks like a broken tool rather than a broken profile.
    """

    test: str = Field(
        min_length=1,
        description="Command that runs the tests. Required - see the validator below.",
    )
    lint: str | None = None
    format: str | None = None
    typecheck: str | None = None

    def commands(self) -> list[tuple[str, str]]:
        """Configured checks as (name, command), in the order they should run.

        Cheapest first: lint and format fail in seconds and catch whole classes of
        problem before the slow ones start. Tests run last because they cost the most.
        """
        ordered = (
            ("lint", self.lint),
            ("format", self.format),
            ("typecheck", self.typecheck),
            ("test", self.test),
        )
        return [(name, cmd) for name, cmd in ordered if cmd]


class Profile(BaseModel):
    """Everything JSpec is allowed to know about one specific project."""

    model_config = {"extra": "forbid"}

    name: Id
    description: str = Field(min_length=1)
    languages: list[str] = Field(
        min_length=1,
        description="Lowercase language ids. C-06 loads a parser per entry.",
    )
    source_dirs: list[str] = Field(
        min_length=1,
        description="Repo-relative roots holding the code under change.",
    )
    test_dirs: list[str] = Field(
        default_factory=list,
        description="Repo-relative roots holding tests. Empty is legal; a repo may "
        "keep tests beside sources.",
    )
    validation: Validation

    @field_validator("languages")
    @classmethod
    def _languages_are_lowercase(cls, v: list[str]) -> list[str]:
        """`Python` and `python` must not be two different languages.

        C-06 will look up a parser by this string. A case mismatch there surfaces as
        "no parser for Python" while the profile plainly says python, which is a
        genuinely confusing ten minutes.
        """
        wrong = [lang for lang in v if lang != lang.lower()]
        if wrong:
            raise ValueError(
                f"languages must be lowercase; got {wrong}. "
                f"Use {[lang.lower() for lang in wrong]}."
            )
        return v

    @field_validator("source_dirs", "test_dirs")
    @classmethod
    def _dirs_are_relative(cls, v: list[str]) -> list[str]:
        """Absolute paths in a profile are a machine-specific fact.

        A profile is committed and shared. `C:/Users/someone/repo/src` works on
        exactly one machine and breaks in CI, which is the pipeline-safety rule the
        parent ruleset states and this project inherits by good sense.
        """
        bad = [d for d in v if d.startswith(("/", "\\")) or (len(d) > 1 and d[1] == ":")]
        if bad:
            raise ValueError(
                f"paths must be repo-relative, not absolute; got {bad}. "
                f"An absolute path is machine-specific and will not survive CI."
            )
        return v


__all__ = [
    "Profile",
    "Validation",
]
