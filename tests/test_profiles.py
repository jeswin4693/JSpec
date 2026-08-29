"""Profile contract and loader tests.

Two things are being proven here, and the second is the one that matters.

1. A malformed profile fails at load, naming the problem. Every test in
   `TestFailsLoudly` is a way a profile could otherwise half-load and leave the
   caller running the wrong commands against the wrong directories while reporting
   success.

2. A new kind of project can be added by writing only data. `TestShippedProfiles`
   loads two deliberately unalike profiles through identical code. If a future
   change makes one of them need special handling, that test is where it shows up -
   which is the whole point of C-25 (constitution rule 20, D-011).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml
from jspec.contracts import KINDS, json_schema
from jspec.contracts.profile import Profile, Validation
from jspec.profiles import ProfileError, available, load

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED = REPO_ROOT / "profiles"

MINIMAL = """
    name: {name}
    description: A profile for testing.
    languages: [python]
    source_dirs: [src/]
    validation:
      test: pytest
"""


def write(directory: Path, name: str, body: str) -> Path:
    """Write a profile file, dedented, and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.yaml"
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return path


class TestShippedProfiles:
    """The examples must load, and must not resemble each other."""

    def test_every_shipped_profile_loads(self) -> None:
        names = available(SHIPPED)
        assert names, "no profiles shipped"
        for name in names:
            assert load(name, SHIPPED).name == name

    def test_both_worked_examples_ship(self) -> None:
        """The acceptance test asks for two DIFFERENT examples, not one and a copy."""
        assert {"python-service", "playwright-e2e"} <= set(available(SHIPPED))

    def test_the_examples_are_genuinely_unalike(self) -> None:
        """If these ever converge, one has stopped being a second example."""
        py = load("python-service", SHIPPED)
        pw = load("playwright-e2e", SHIPPED)
        assert py.languages != pw.languages
        assert py.source_dirs != pw.source_dirs
        assert py.validation.test != pw.validation.test
        assert py.validation.lint != pw.validation.lint

    def test_this_repo_has_a_profile_for_itself(self) -> None:
        """Moved out of .sdd/config.yaml so the commands live in exactly one place."""
        me = load("jspec-self", SHIPPED)
        assert me.validation.test == "pytest"
        assert me.validation.typecheck is None  # not configured; stated honestly

    def test_config_yaml_no_longer_carries_validation_commands(self) -> None:
        """Constitution rule 2: the duplicate is what drifts."""
        config = yaml.safe_load((REPO_ROOT / ".sdd" / "config.yaml").read_text())
        assert "validation" not in config


class TestFailsLoudly:
    """Every one of these would otherwise be a silent wrong-configuration bug."""

    def test_missing_profile_names_the_alternatives(self, tmp_path: Path) -> None:
        write(tmp_path, "python-service", MINIMAL.format(name="python-service"))
        with pytest.raises(ProfileError) as exc:
            load("nonexistent", tmp_path)
        assert "python-service" in str(exc.value)

    def test_a_typo_suggests_the_closest_name(self, tmp_path: Path) -> None:
        write(tmp_path, "python-service", MINIMAL.format(name="python-service"))
        with pytest.raises(ProfileError, match="Did you mean"):
            load("python-servce", tmp_path)

    def test_malformed_yaml_is_reported_as_yaml(self, tmp_path: Path) -> None:
        write(tmp_path, "broken", "name: broken\n  bad: [indent")
        with pytest.raises(ProfileError, match="not valid YAML"):
            load("broken", tmp_path)

    def test_empty_profile_is_rejected(self, tmp_path: Path) -> None:
        write(tmp_path, "empty", "")
        with pytest.raises(ProfileError, match="is empty"):
            load("empty", tmp_path)

    def test_a_list_is_not_a_profile(self, tmp_path: Path) -> None:
        write(tmp_path, "listy", "- one\n- two")
        with pytest.raises(ProfileError, match="must contain a mapping"):
            load("listy", tmp_path)

    def test_missing_test_command_is_rejected(self, tmp_path: Path) -> None:
        """The important one.

        A profile with no test command lets C-19 run nothing and report success -
        a false green, which is worse than a crash because nobody investigates it.
        """
        write(
            tmp_path,
            "notest",
            """
            name: notest
            description: No test command.
            languages: [python]
            source_dirs: [src/]
            validation:
              lint: ruff check .
            """,
        )
        with pytest.raises(ProfileError, match="validation.test"):
            load("notest", tmp_path)

    def test_name_must_match_filename(self, tmp_path: Path) -> None:
        write(tmp_path, "on-disk", MINIMAL.format(name="something-else"))
        with pytest.raises(ProfileError, match="but the filename says"):
            load("on-disk", tmp_path)

    def test_unknown_field_is_rejected_not_ignored(self, tmp_path: Path) -> None:
        """A mistyped key that is silently dropped is a setting you think you set."""
        write(
            tmp_path,
            "extra",
            """
            name: extra
            description: Has a mistyped field.
            languages: [python]
            source_dirs: [src/]
            validaton: {}
            validation:
              test: pytest
            """,
        )
        with pytest.raises(ProfileError, match="validaton"):
            load("extra", tmp_path)

    def test_absolute_paths_are_rejected(self, tmp_path: Path) -> None:
        """A committed profile must not carry one machine's directory layout."""
        write(
            tmp_path,
            "abs",
            """
            name: abs
            description: Absolute source dir.
            languages: [python]
            source_dirs: ["/home/someone/repo/src"]
            validation:
              test: pytest
            """,
        )
        with pytest.raises(ProfileError, match="repo-relative"):
            load("abs", tmp_path)

    def test_windows_absolute_paths_are_rejected(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "winabs",
            """
            name: winabs
            description: Windows absolute source dir.
            languages: [python]
            source_dirs: ["C:/Users/someone/repo/src"]
            validation:
              test: pytest
            """,
        )
        with pytest.raises(ProfileError, match="repo-relative"):
            load("winabs", tmp_path)

    def test_uppercase_language_is_rejected(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "shouty",
            """
            name: shouty
            description: Uppercase language.
            languages: [Python]
            source_dirs: [src/]
            validation:
              test: pytest
            """,
        )
        with pytest.raises(ProfileError, match="lowercase"):
            load("shouty", tmp_path)

    def test_missing_directory_lists_nothing_rather_than_crashing(
        self, tmp_path: Path
    ) -> None:
        assert available(tmp_path / "does-not-exist") == []


class TestValidationOrdering:
    def test_configured_checks_run_cheapest_first(self) -> None:
        v = Validation(
            test="pytest",
            lint="ruff check .",
            typecheck="mypy src",
            format="ruff format",
        )
        assert [name for name, _ in v.commands()] == [
            "lint",
            "format",
            "typecheck",
            "test",
        ]

    def test_unconfigured_checks_are_omitted_not_faked(self) -> None:
        assert Validation(test="pytest").commands() == [("test", "pytest")]


class TestSchemaExport:
    def test_profile_is_registered_like_every_other_artifact(self) -> None:
        assert KINDS["profile"] is Profile

    def test_schema_marks_the_load_bearing_fields_required(self) -> None:
        required = set(json_schema("profile")["required"])
        assert {
            "name",
            "description",
            "languages",
            "source_dirs",
            "validation",
        } <= required
