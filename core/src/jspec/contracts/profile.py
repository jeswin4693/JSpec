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

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

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


# --- the draft a profiler writes, before a person has agreed to it (C-26) -----------


class Basis(str, Enum):
    """How a drafted value came to be. The whole point of a draft is that this is
    never hidden: a reader who skims once will trust every line equally, so each line
    has to say how far it can be trusted.

      FOUND      read as written in a file of the repository
      INFERRED   derived by a rule from evidence that was found - a convention
                 applied to a real signal, not a lookup
      GUESSED    a folder or file *name* and nothing else
      CONFIRMED  a person said so. Detection never overwrites it
      UNKNOWN    no evidence. Left empty on purpose, never filled with a plausible value
    """

    FOUND = "found"
    INFERRED = "inferred"
    GUESSED = "guessed"
    CONFIRMED = "confirmed"
    UNKNOWN = "unknown"


REQUIRED_FIELDS = ("name", "description", "languages", "source_dirs", "validation.test")
"""Without these there is no valid `Profile`, so an unknown one blocks acceptance."""

OPTIONAL_FIELDS = (
    "test_dirs",
    "validation.lint",
    "validation.format",
    "validation.typecheck",
)
"""Absence is legal: a repo may have no linter, and a profile states what is true."""

LIST_FIELDS = ("languages", "source_dirs", "test_dirs")


class Finding(BaseModel):
    """One field of the draft, with the reason it holds the value it holds."""

    model_config = {"extra": "forbid"}

    field: str
    value: str | list[str] | None = None
    basis: Basis
    evidence: list[str] = Field(default_factory=list)
    note: str | None = Field(
        default=None, description="What a person should check, or why it is empty."
    )

    @model_validator(mode="after")
    def _evidence_or_silence(self) -> Finding:
        """Evidence or silence, as for every judgement in this system (rule 15).

        A value with no evidence is an invention; an `unknown` with a value is a
        contradiction. Either would let a draft look more certain than it is.
        """
        if self.basis is Basis.UNKNOWN:
            if self.value not in (None, [], ""):
                raise ValueError(f"{self.field}: basis unknown but a value is set")
        elif not self.evidence:
            raise ValueError(f"{self.field}: basis {self.basis.value} needs evidence")
        return self


class ProfileDraft(BaseModel):
    """A profile as detected, field by field, awaiting a person's say.

    Not a `Profile`: that contract requires a test command, and a draft for a
    repository with none must be able to say so instead of inventing one.
    """

    model_config = {"extra": "forbid"}

    root: str = Field(min_length=1, description="Where it was drafted from. Local only.")
    findings: list[Finding]
    observations: list[str] = Field(
        default_factory=list,
        description="Facts worth seeing that no profile field can hold (yet).",
    )

    @model_validator(mode="after")
    def _fields_are_known_and_unique(self) -> ProfileDraft:
        known = {*REQUIRED_FIELDS, *OPTIONAL_FIELDS}
        names = [f.field for f in self.findings]
        unknown = sorted(set(names) - known)
        duplicated = sorted({n for n in names if names.count(n) > 1})
        missing = sorted(known - set(names))
        problems = []
        if unknown:
            problems.append(f"unknown fields {unknown}")
        if duplicated:
            problems.append(f"duplicated fields {duplicated}")
        if missing:
            problems.append(f"missing fields {missing}")
        if problems:
            raise ValueError("; ".join(problems) + f"; expected exactly {sorted(known)}")
        return self

    def get(self, field: str) -> Finding:
        return next(f for f in self.findings if f.field == field)

    @property
    def name(self) -> str:
        value = self.get("name").value
        return value if isinstance(value, str) else ""

    def unknown_required(self) -> list[str]:
        return [f for f in REQUIRED_FIELDS if self.get(f).basis is Basis.UNKNOWN]

    def guessed(self) -> list[str]:
        return [f.field for f in self.findings if f.basis is Basis.GUESSED]

    def to_profile(self) -> Profile:
        """The draft as a real `Profile`, or an error naming every field that stops it.

        Raises `ValueError` rather than defaulting: a required field nobody knows
        must reach a person, not a linter run against the wrong directory.
        """
        blocked = self.unknown_required()
        if blocked:
            raise ValueError(f"cannot build a profile: unknown required fields {blocked}")

        def value(field: str) -> str | list[str] | None:
            return self.get(field).value

        validation: dict[str, object] = {"test": value("validation.test")}
        for check in ("lint", "format", "typecheck"):
            if value(f"validation.{check}"):
                validation[check] = value(f"validation.{check}")
        return Profile.model_validate(
            {
                "name": value("name"),
                "description": value("description"),
                "languages": value("languages"),
                "source_dirs": value("source_dirs"),
                "test_dirs": value("test_dirs") or [],
                "validation": validation,
            }
        )


__all__ = [
    "LIST_FIELDS",
    "OPTIONAL_FIELDS",
    "REQUIRED_FIELDS",
    "Basis",
    "Finding",
    "Profile",
    "ProfileDraft",
    "Validation",
]
