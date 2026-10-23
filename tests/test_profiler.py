"""C-26 project profiler tests.

The component guide's acceptance criteria, each one a class below:

1. `TestThreeDifferentRepositories` - a usable draft for three repositories that share
   almost nothing: a Python service, a TypeScript end-to-end suite whose "source" is
   mostly tests, and a JavaScript library whose tests sit beside its code.
2. `TestEveryFieldSaysHowItWasReached` - found, inferred, guessed, confirmed or
   unknown, with evidence. The distinction is the component's whole value: "tests are
   in tests/ because the config says so" and "probably tests/ because of its name" must
   not read alike.
3. `TestCorrectionsAreNeverAskedTwice` - a `--set` value is confirmed and survives every
   later draft, whatever detection would now say.
4. `TestItNeverInventsAValue` - an empty folder, a language JSpec cannot read, a
   placeholder test script and a missing lockfile. Unknown stays unknown.

And what is specific to how it was built:

5. `TestAcceptIsGuarded` - an unknown required field and an unconfirmed guess both stop
   it, and what it writes must load.
6. `TestLayoutInference` - the folder rules, including the overlap bug the first run on
   this very repository found (`core/` and `core/src/` both listed).
7. `TestTheRulesAreData` - no ecosystem is named in code, and a typo in the rule table
   is an error rather than a rule that never fires.
8. `TestWritesNothingIntoTheRepository` - profiling someone's checkout must not alter it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jspec.cli import EXIT_ANSWER_IS_NO, EXIT_OK, EXIT_USAGE, main
from jspec.contracts import KINDS
from jspec.contracts.profile import Basis, Finding, ProfileDraft
from jspec.graph.extract import load_languages
from jspec.graph.store import SymbolStore
from jspec.profiler import ProfilerError, accept, parse_correction, profile_repo
from jspec.profiles import load as load_profile

from jspec import profiler

# --- three repositories that share almost nothing ----------------------------------

PY_SERVICE = {
    "pyproject.toml": """\
[project]
name = "shop"
version = "0.1.0"
dependencies = ["flask>=3", "Requests"]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff", "mypy"]

[tool.ruff]
line-length = 90

[tool.mypy]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
    "src/shop/__init__.py": "",
    "src/shop/app.py": "def run():\n    return 1\n",
    "tests/conftest.py": "",
    "tests/test_app.py": "def test_run():\n    assert True\n",
}

TS_E2E = {
    "package.json": json.dumps(
        {
            "name": "e2e",
            "scripts": {"test": "playwright test --workers=1", "lint": "eslint ."},
            "devDependencies": {
                "@playwright/test": "^1.50",
                "typescript": "^5",
                "eslint": "^9",
            },
        }
    ),
    "pnpm-lock.yaml": "lockfileVersion: 9\n",
    "tsconfig.json": "{}",
    "playwright.config.ts": "export default { testDir: './tests' };\n",
    "tests/login.spec.ts": "export const a = 1;\n",
    "tests/cart.spec.ts": "export const b = 2;\n",
    "page-objects/loginPage.ts": "export class LoginPage {}\n",
    "page-objects/cartPage.ts": "export class CartPage {}\n",
    "support/util.ts": "export const u = 1;\n",
}

JS_LIB = {
    "package.json": json.dumps(
        {
            "name": "slug",
            "scripts": {"test": "node --test"},
            "dependencies": {"left-pad": "1"},
        }
    ),
    "lib/slug.js": "export function slug() {}\n",
    "lib/slug.test.js": "export const t = 1;\n",
    "lib/text.js": "export function text() {}\n",
    "lib/text.test.js": "export const t = 2;\n",
}


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def repo(tmp_path: Path, files: dict[str, str], name: str = "subject") -> Path:
    return write_tree(tmp_path / name, files)


def fields(draft: ProfileDraft) -> dict[str, Finding]:
    return {f.field: f for f in draft.findings}


# --- 1 -----------------------------------------------------------------------------


class TestThreeDifferentRepositories:
    def test_a_python_service(self, tmp_path: Path) -> None:
        draft = profile_repo(repo(tmp_path, PY_SERVICE, "shop"))
        f = fields(draft)

        assert f["languages"].value == ["python"]
        assert f["source_dirs"].value == ["src/"]
        assert f["test_dirs"].value == ["tests/"]
        assert f["validation.test"].value == "pytest"
        assert f["validation.lint"].value == "ruff check ."
        assert f["validation.format"].value == "ruff format --check ."
        assert f["validation.typecheck"].value == "mypy ."

    def test_a_typescript_suite_whose_source_is_mostly_tests(
        self, tmp_path: Path
    ) -> None:
        """Nothing here matches the Python service: another language, another runner, and
        the tests folder is not source because page objects and helpers are."""
        draft = profile_repo(repo(tmp_path, TS_E2E, "e2e"))
        f = fields(draft)

        assert f["languages"].value == ["typescript"]
        assert f["source_dirs"].value == ["page-objects/", "support/"]
        assert f["test_dirs"].value == ["tests/"]
        assert f["validation.test"].value == "pnpm run test"
        assert f["validation.lint"].value == "pnpm run lint"
        assert f["validation.typecheck"].value == "npx tsc --noEmit"

    def test_a_library_whose_tests_sit_beside_its_code(self, tmp_path: Path) -> None:
        draft = profile_repo(repo(tmp_path, JS_LIB, "slug"))
        f = fields(draft)

        assert f["languages"].value == ["javascript"]
        assert f["source_dirs"].value == ["lib/"]
        assert f["test_dirs"].value == [], (
            "half the files are tests; that is not a test folder"
        )
        assert "beside the code" in f["test_dirs"].evidence[0]

    @pytest.mark.parametrize(
        "files", [PY_SERVICE, TS_E2E, JS_LIB], ids=["py", "ts", "js"]
    )
    def test_every_draft_is_usable_as_a_real_profile(
        self, tmp_path: Path, files
    ) -> None:
        """'Usable' means it survives the real contract, not that it looks plausible."""
        profile = profile_repo(repo(tmp_path, files)).to_profile()

        assert profile.languages and profile.source_dirs and profile.validation.test

    def test_the_draft_is_itself_a_registered_artifact_kind(self) -> None:
        assert KINDS["profile_draft"] is ProfileDraft


# --- 2 -----------------------------------------------------------------------------


class TestEveryFieldSaysHowItWasReached:
    def test_a_command_the_project_wrote_down_is_found(self, tmp_path: Path) -> None:
        f = fields(profile_repo(repo(tmp_path, TS_E2E)))

        assert f["validation.test"].basis is Basis.FOUND
        assert "scripts.test" in f["validation.test"].evidence[0]

    def test_a_command_assumed_from_a_config_is_inferred_not_found(
        self, tmp_path: Path
    ) -> None:
        f = fields(profile_repo(repo(tmp_path, PY_SERVICE)))

        assert f["validation.lint"].basis is Basis.INFERRED
        assert "tool.ruff" in f["validation.lint"].evidence[0]

    def test_a_test_folder_a_config_names_is_found_one_inferred_from_contents_is_not(
        self, tmp_path: Path
    ) -> None:
        declared = fields(profile_repo(repo(tmp_path, PY_SERVICE, "a")))["test_dirs"]
        no_config = {k: v for k, v in PY_SERVICE.items() if k != "pyproject.toml"}
        inferred = fields(profile_repo(repo(tmp_path, no_config, "b")))["test_dirs"]

        assert declared.basis is Basis.FOUND
        assert inferred.basis is Basis.INFERRED
        assert inferred.value == ["tests/"], (
            "same answer, different strength of evidence"
        )

    def test_a_folder_named_like_tests_with_no_tests_in_it_is_only_a_guess(
        self, tmp_path: Path
    ) -> None:
        files = {"src/a.py": "x = 1\n", "tests/helpers.py": "y = 2\n"}
        f = fields(profile_repo(repo(tmp_path, files)))["test_dirs"]

        assert f.basis is Basis.GUESSED
        assert "no file in it matches a test pattern" in f.evidence[0]

    def test_a_language_with_no_manifest_behind_it_is_inferred(
        self, tmp_path: Path
    ) -> None:
        f = fields(profile_repo(repo(tmp_path, {"src/a.py": "x = 1\n"})))["languages"]

        assert f.basis is Basis.INFERRED

    def test_a_language_a_manifest_agrees_with_is_found(self, tmp_path: Path) -> None:
        f = fields(profile_repo(repo(tmp_path, PY_SERVICE)))["languages"]

        assert f.basis is Basis.FOUND
        assert any("pyproject.toml" in e for e in f.evidence)

    def test_every_field_that_has_a_value_carries_evidence(
        self, tmp_path: Path
    ) -> None:
        for files in (PY_SERVICE, TS_E2E, JS_LIB):
            for finding in profile_repo(
                repo(tmp_path, files, f"r{id(files)}")
            ).findings:
                if finding.basis is not Basis.UNKNOWN:
                    assert finding.evidence, finding.field

    def test_a_finding_without_evidence_cannot_be_constructed(self) -> None:
        """Evidence or silence, enforced by the contract rather than by discipline."""
        with pytest.raises(ValueError, match="needs evidence"):
            Finding(field="languages", value=["python"], basis=Basis.FOUND)

    def test_an_unknown_finding_cannot_carry_a_value(self) -> None:
        with pytest.raises(ValueError, match="basis unknown but a value"):
            Finding(field="languages", value=["python"], basis=Basis.UNKNOWN)

    def test_attention_lists_every_guess_and_every_empty_field(
        self, tmp_path: Path
    ) -> None:
        files = {"src/a.py": "x = 1\n", "tests/helpers.py": "y = 2\n"}
        attention = profiler.attention(profile_repo(repo(tmp_path, files)))

        assert {a["field"] for a in attention} >= {"test_dirs", "validation.lint"}
        assert {a["basis"] for a in attention} <= {"guessed", "unknown"}


# --- 3 -----------------------------------------------------------------------------


class TestCorrectionsAreNeverAskedTwice:
    def test_a_correction_is_confirmed_and_replaces_the_detected_value(
        self, tmp_path: Path
    ) -> None:
        draft = profile_repo(
            repo(tmp_path, PY_SERVICE), corrections={"validation.test": "tox -e unit"}
        )
        f = fields(draft)["validation.test"]

        assert (f.value, f.basis) == ("tox -e unit", Basis.CONFIRMED)

    def test_a_confirmed_field_survives_the_next_draft(self, tmp_path: Path) -> None:
        root = repo(tmp_path, PY_SERVICE)
        first = profile_repo(root, corrections={"validation.test": "tox -e unit"})
        second = profile_repo(root, previous=first)

        f = fields(second)["validation.test"]
        assert (f.value, f.basis) == ("tox -e unit", Basis.CONFIRMED)

    def test_detection_does_not_overwrite_a_confirmed_field_even_when_it_now_disagrees(
        self, tmp_path: Path
    ) -> None:
        """The repo gains a different test config later. The person's word still stands."""
        root = repo(tmp_path, PY_SERVICE)
        first = profile_repo(root, corrections={"validation.lint": "flake8"})
        (root / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")

        assert (
            fields(profile_repo(root, previous=first))["validation.lint"].value
            == "flake8"
        )

    def test_unconfirmed_fields_are_redetected_each_time(self, tmp_path: Path) -> None:
        root = repo(tmp_path, PY_SERVICE)
        first = profile_repo(root)
        (root / "ruff.toml").unlink(missing_ok=True)
        (root / "src" / "extra").mkdir()
        (root / "src" / "extra" / "m.py").write_text("x = 1\n", encoding="utf-8")

        again = profile_repo(root, previous=first)
        assert fields(again)["source_dirs"].basis is Basis.INFERRED

    def test_a_field_accepted_into_a_profile_comes_back_confirmed(
        self, tmp_path: Path
    ) -> None:
        root = repo(tmp_path, PY_SERVICE, "shop")
        drafts, profiles = tmp_path / "drafts", tmp_path / "profiles"
        draft = profile_repo(root)
        assert accept(draft, profiles_directory=profiles, drafts_directory=drafts)[
            "accepted"
        ]

        later = profile_repo(root, accepted=load_profile("shop", profiles))
        assert {f.basis for f in later.findings} == {Basis.CONFIRMED}

    def test_a_correction_can_say_there_is_none(self, tmp_path: Path) -> None:
        """Confirmed absent is an answer; `unknown` would ask again."""
        draft = profile_repo(
            repo(tmp_path, PY_SERVICE), corrections={"validation.lint": ""}
        )
        f = fields(draft)["validation.lint"]

        assert f.value is None and f.basis is Basis.CONFIRMED
        assert draft.unknown_required() == []

    def test_lists_are_comma_separated(self) -> None:
        assert parse_correction("source_dirs", "src/, lib/") == ["src/", "lib/"]
        assert parse_correction("test_dirs", "") == []

    def test_a_required_field_cannot_be_blanked(self) -> None:
        with pytest.raises(ProfilerError, match="cannot be blank"):
            parse_correction("validation.test", "  ")
        with pytest.raises(ProfilerError, match="cannot be blank"):
            parse_correction("languages", "")

    def test_a_misspelled_field_names_the_real_ones(self) -> None:
        with pytest.raises(ProfilerError, match=r"validation\.test"):
            parse_correction("validation.tests", "x")


# --- 4 -----------------------------------------------------------------------------


class TestItNeverInventsAValue:
    def test_an_empty_folder_yields_unknowns_not_plausible_defaults(
        self, tmp_path: Path
    ) -> None:
        draft = profile_repo(repo(tmp_path, {"README.md": "hello\n"}, "empty"))

        assert draft.unknown_required() == [
            "languages",
            "source_dirs",
            "validation.test",
        ]
        with pytest.raises(ValueError, match="unknown required fields"):
            draft.to_profile()

    def test_a_language_jspec_cannot_read_is_named_and_not_indexed(
        self, tmp_path: Path
    ) -> None:
        files = {
            "go.mod": "module x\n",
            "main.go": "package main\n",
            "main_test.go": "package main\n",
        }
        draft = profile_repo(repo(tmp_path, files, "svc"))
        f = fields(draft)

        assert f["languages"].basis is Basis.UNKNOWN
        assert any("no reading rules" in o for o in draft.observations)
        # The test command is still drafted: it is true of the repository either way.
        assert f["validation.test"].value == "go test ./..."

    def test_the_placeholder_test_script_is_not_a_test_command(
        self, tmp_path: Path
    ) -> None:
        """`npm init` writes a `test` script that exits 1 on purpose."""
        manifest = {
            "name": "x",
            "scripts": {"test": 'echo "Error: no test specified" && exit 1'},
        }
        files = {
            "package.json": json.dumps(manifest),
            "lib/a.js": "export const a = 1;\n",
        }
        f = fields(profile_repo(repo(tmp_path, files)))["validation.test"]

        assert f.basis is Basis.UNKNOWN and f.value is None

    def test_a_script_without_a_lockfile_is_not_claimed_as_found(
        self, tmp_path: Path
    ) -> None:
        """The script was read; the program that runs it was assumed. The draft says so."""
        f = fields(profile_repo(repo(tmp_path, JS_LIB)))["validation.test"]

        assert f.value == "npm run test"
        assert f.basis is Basis.INFERRED
        assert any("no lockfile found" in e for e in f.evidence)

    def test_a_manifest_that_cannot_be_parsed_is_a_note_not_a_crash(
        self, tmp_path: Path
    ) -> None:
        files = {"package.json": "{not json", "lib/a.js": "export const a = 1;\n"}
        draft = profile_repo(repo(tmp_path, files))

        assert any("not valid JSON" in o for o in draft.observations)
        assert fields(draft)["languages"].value == ["javascript"]

    def test_a_manifest_in_a_subfolder_is_reported_as_unread(
        self, tmp_path: Path
    ) -> None:
        """'No linter configured' and 'a linter we did not look for' are different."""
        files = {"core/pyproject.toml": "[tool.ruff]\n", "core/src/a.py": "x = 1\n"}
        draft = profile_repo(repo(tmp_path, files))

        assert fields(draft)["validation.lint"].basis is Basis.UNKNOWN
        assert any(
            "core/pyproject.toml exists but only the repository root" in o
            for o in draft.observations
        )

    def test_a_language_with_a_few_stray_files_is_left_out_and_said_so(
        self, tmp_path: Path
    ) -> None:
        files = {f"src/m{i}.ts": "export const a = 1;\n" for i in range(40)}
        files["tsconfig.json"] = "{}"
        files["scripts/one.js"] = "x = 1;\n"
        draft = profile_repo(repo(tmp_path, files))

        assert fields(draft)["languages"].value == ["typescript"]
        assert any("also saw 1 javascript file" in o for o in draft.observations)

    def test_an_unreadable_name_still_yields_a_valid_id(self) -> None:
        assert profiler.slug("My Cool_Repo!!") == "my-cool-repo"
        assert len(profiler.slug("x" * 40)) <= 16
        assert len(profiler.slug("ab")) >= 3
        assert len(profiler.slug("---")) >= 3


# --- 5 -----------------------------------------------------------------------------


class TestAcceptIsGuarded:
    @pytest.fixture
    def dirs(self, tmp_path: Path) -> tuple[Path, Path]:
        return tmp_path / "drafts", tmp_path / "profiles"

    def test_it_writes_a_profile_that_loads_and_matches_the_draft(
        self, tmp_path: Path, dirs
    ) -> None:
        drafts, profiles = dirs
        draft = profile_repo(repo(tmp_path, PY_SERVICE, "shop"))
        result = accept(draft, profiles_directory=profiles, drafts_directory=drafts)

        assert result["accepted"] is True
        assert load_profile("shop", profiles) == draft.to_profile()

    def test_the_written_file_says_how_each_field_was_reached(
        self, tmp_path: Path, dirs
    ) -> None:
        drafts, profiles = dirs
        draft = profile_repo(repo(tmp_path, PY_SERVICE, "shop"))
        accept(draft, profiles_directory=profiles, drafts_directory=drafts)
        text = (profiles / "shop.yaml").read_text(encoding="utf-8")

        header = text.split("\n\n")[0]
        assert "validation.lint" in header and "inferred" in header
        assert "test_dirs" in header and "found" in header
        assert str(tmp_path) not in text, (
            "a machine-specific path must not reach a shared file"
        )

    def test_an_unknown_required_field_blocks_it(self, tmp_path: Path, dirs) -> None:
        drafts, profiles = dirs
        draft = profile_repo(repo(tmp_path, {"README.md": "x\n"}, "empty"))
        result = accept(draft, profiles_directory=profiles, drafts_directory=drafts)

        assert result["accepted"] is False
        assert "unknown required fields" in result["blockers"][0]
        assert not (profiles / "empty.yaml").exists()

    def test_a_guess_blocks_it_until_it_is_accepted_by_name(
        self, tmp_path: Path, dirs
    ) -> None:
        drafts, profiles = dirs
        files = {
            "src/a.py": "x = 1\n",
            "tests/helpers.py": "y = 2\n",
            "pytest.ini": "[pytest]\n",
        }
        draft = profile_repo(repo(tmp_path, files, "guessy"))
        assert draft.guessed() == ["test_dirs"]

        blocked = accept(draft, profiles_directory=profiles, drafts_directory=drafts)
        assert (
            blocked["accepted"] is False
            and "--accept-guesses" in blocked["blockers"][0]
        )

        taken = accept(
            draft,
            profiles_directory=profiles,
            drafts_directory=drafts,
            accept_guesses=True,
        )
        assert taken["accepted"] is True

    def test_accepting_a_guess_records_it_as_confirmed_so_it_is_not_asked_again(
        self, tmp_path: Path, dirs
    ) -> None:
        drafts, profiles = dirs
        files = {
            "src/a.py": "x = 1\n",
            "tests/helpers.py": "y = 2\n",
            "pytest.ini": "[pytest]\n",
        }
        draft = profile_repo(repo(tmp_path, files, "guessy"))
        accept(
            draft,
            profiles_directory=profiles,
            drafts_directory=drafts,
            accept_guesses=True,
        )

        saved = profiler.load_draft("guessy", drafts)
        assert saved is not None and saved.guessed() == []
        assert fields(saved)["test_dirs"].basis is Basis.CONFIRMED

    def test_it_will_not_overwrite_an_existing_profile_by_surprise(
        self, tmp_path: Path, dirs
    ) -> None:
        drafts, profiles = dirs
        draft = profile_repo(repo(tmp_path, PY_SERVICE, "shop"))
        assert accept(draft, profiles_directory=profiles, drafts_directory=drafts)[
            "accepted"
        ]
        before = (profiles / "shop.yaml").read_text(encoding="utf-8")

        again = accept(draft, profiles_directory=profiles, drafts_directory=drafts)
        assert again["accepted"] is False and "--overwrite" in again["blockers"][0]
        assert (profiles / "shop.yaml").read_text(encoding="utf-8") == before

        forced = accept(
            draft, profiles_directory=profiles, drafts_directory=drafts, overwrite=True
        )
        assert forced["accepted"] is True

    def test_what_it_writes_that_fails_to_load_is_removed_not_left_behind(
        self, tmp_path: Path, dirs
    ) -> None:
        """A bad value the contract rejects: uppercase language ids. It must not leave a
        profile on disk that fails later in someone else's session."""
        drafts, profiles = dirs
        draft = profile_repo(
            repo(tmp_path, PY_SERVICE, "shop"), corrections={"languages": "Python"}
        )
        result = accept(draft, profiles_directory=profiles, drafts_directory=drafts)

        assert result["accepted"] is False
        assert "lowercase" in " ".join(result["blockers"])
        assert not (profiles / "shop.yaml").exists()

    def test_a_profile_that_is_written_but_will_not_load_is_removed(
        self, tmp_path: Path, dirs, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The post-write check: what was written must load, or it is deleted and the
        error propagates. The contract normally rejects a bad value first, so this path
        is reached only when the file on disk disagrees with the object in memory -
        simulated here, because that is the case the check exists for."""
        drafts, profiles = dirs

        def refuse(*_: object) -> None:
            raise ProfilerError("simulated: the file on disk does not load")

        monkeypatch.setattr("jspec.profiler.load_profile", refuse)
        draft = profile_repo(repo(tmp_path, PY_SERVICE, "shop"))

        with pytest.raises(ProfilerError, match="does not load"):
            accept(draft, profiles_directory=profiles, drafts_directory=drafts)
        assert not (profiles / "shop.yaml").exists(), (
            "a broken profile must not be left behind"
        )

    def test_a_hand_edited_draft_is_validated_on_load(
        self, tmp_path: Path, dirs
    ) -> None:
        drafts, _ = dirs
        draft = profile_repo(repo(tmp_path, PY_SERVICE, "shop"))
        path = profiler.save_draft(draft, drafts)
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("basis: found", "basis: certain", 1), encoding="utf-8"
        )

        with pytest.raises(ProfilerError, match="not a valid draft"):
            profiler.load_draft("shop", drafts)

    def test_a_saved_draft_round_trips(self, tmp_path: Path, dirs) -> None:
        drafts, _ = dirs
        draft = profile_repo(repo(tmp_path, TS_E2E, "e2e"))
        profiler.save_draft(draft, drafts)

        assert profiler.load_draft("e2e", drafts) == draft
        assert profiler.load_draft("nothing-here", drafts) is None


# --- 6 -----------------------------------------------------------------------------


class TestLayoutInference:
    def test_a_conventional_container_is_the_source_root_and_the_leftovers_are_reported(
        self, tmp_path: Path
    ) -> None:
        """The bug this repository's own first draft found: `core/` AND `core/src/` were
        both listed, so four files in `core/scripts/` read as source."""
        files = {
            "core/src/pkg/a.py": "x = 1\n",
            "core/scripts/tool.py": "y = 1\n",
            "tests/test_a.py": "def test_a():\n    pass\n",
        }
        draft = profile_repo(repo(tmp_path, files))

        assert fields(draft)["source_dirs"].value == ["core/src/"]
        assert any("core/ also holds 1 source file" in o for o in draft.observations)

    def test_code_in_a_docs_folder_is_not_source(self, tmp_path: Path) -> None:
        files = {
            "src/a.py": "x = 1\n",
            "docs/conf.py": "y = 1\n",
            "tests/test_a.py": "pass\n",
        }
        draft = profile_repo(repo(tmp_path, files))

        assert fields(draft)["source_dirs"].value == ["src/"]
        assert any("docs/" in o and "left out" in o for o in draft.observations)

    def test_a_flat_repository_is_its_own_source_root(self, tmp_path: Path) -> None:
        files = {"a.py": "x = 1\n", "b.py": "y = 1\n"}
        f = fields(profile_repo(repo(tmp_path, files)))["source_dirs"]

        assert f.value == ["."]

    def test_a_repository_that_is_only_tests_treats_the_suite_as_the_code(
        self, tmp_path: Path
    ) -> None:
        files = {"tests/test_a.py": "pass\n", "tests/test_b.py": "pass\n"}
        draft = profile_repo(repo(tmp_path, files))

        assert fields(draft)["source_dirs"].value == ["tests/"]
        assert fields(draft)["test_dirs"].value == ["tests/"]

    def test_hidden_and_excluded_folders_are_never_walked(self, tmp_path: Path) -> None:
        files = {
            "src/a.py": "x = 1\n",
            ".hidden/b.py": "y = 1\n",
            "node_modules/dep/c.py": "z = 1\n",
        }
        f = fields(profile_repo(repo(tmp_path, files)))

        assert f["languages"].evidence[0].startswith("1 python files")

    def test_a_config_naming_a_test_folder_that_does_not_exist_is_ignored(
        self, tmp_path: Path
    ) -> None:
        files = {"pytest.ini": "[pytest]\ntestpaths = ghosts\n", "src/a.py": "x = 1\n"}
        f = fields(profile_repo(repo(tmp_path, files)))["test_dirs"]

        assert f.basis is not Basis.FOUND and f.value == []

    def test_the_most_imported_folder_is_reported_from_the_index(
        self, tmp_path: Path
    ) -> None:
        """Layout from the symbol index (C-07): an observation, because no profile field
        can hold it yet."""
        root = repo(
            tmp_path,
            {
                "lib/shared.ts": "export const s = 1;\n",
                "app/a.ts": 'import { s } from "../lib/shared";\nexport const a = s;\n',
                "app/b.ts": 'import { s } from "../lib/shared";\nexport const b = s;\n',
            },
        )
        from jspec.contracts.profile import Profile, Validation

        profile = Profile(
            name="idx-test",
            description="fixture",
            languages=["typescript"],
            source_dirs=["lib/", "app/"],
            validation=Validation(test="x"),
        )
        with SymbolStore(tmp_path / "index" / "i.db") as store:
            store.refresh(root, profile, patterns=())
            draft = profile_repo(root, index=store)

        assert any("lib (2 files)" in o for o in draft.observations)


# --- 7 -----------------------------------------------------------------------------


def _condition_keys(node: object) -> set[str]:
    """Every key used in a `when` or declared-test-dir condition anywhere in the rules."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(key)
            found |= _condition_keys(value)
    elif isinstance(node, list):
        for item in node:
            found |= _condition_keys(item)
    return found


class TestTheRulesAreData:
    def test_the_rule_table_loads_and_has_every_section(self) -> None:
        rules = profiler.load_rules()

        assert {"manifests", "runners", "languages", "checks", "layout"} <= set(rules)

    def test_every_condition_in_the_rules_is_one_the_evaluator_understands(
        self,
    ) -> None:
        rules = profiler.load_rules()
        used = _condition_keys(
            [c["when"] for cs in rules["checks"].values() for c in cs]
        )
        used |= _condition_keys([k["evidence"] for k in rules["languages"]["known"]])

        assert used <= {"file", "toml", "dep", "script", "any"}

    def test_every_rule_claims_found_or_inferred_and_never_a_guess(self) -> None:
        """`guessed` is reserved for a folder name and nothing else."""
        for candidates in profiler.load_rules()["checks"].values():
            assert {c["basis"] for c in candidates} <= {"found", "inferred"}

    def test_a_typo_in_a_rule_is_an_error_not_a_rule_that_never_fires(self) -> None:
        facts = profiler.Facts(names=[])
        with pytest.raises(ProfilerError, match="unknown condition"):
            profiler._holds({"fle": "x"}, facts)

    def test_the_rules_do_not_redeclare_extensions_the_reading_rules_own(self) -> None:
        """One authority for what a language's files look like (rule 2)."""
        readable = set(load_languages())
        for known in profiler.load_rules()["languages"]["known"]:
            if "extensions" in known:
                assert known["id"] not in readable, known["id"]

    def test_every_readable_language_with_a_rule_has_evidence_to_attach(self) -> None:
        by_id = {k["id"]: k for k in profiler.load_rules()["languages"]["known"]}
        for language in load_languages():
            assert language in by_id, (
                f"{language} is readable but the profiler cannot say why"
            )


# --- 8 -----------------------------------------------------------------------------


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {
        p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
    }


class TestWritesNothingIntoTheRepository:
    def test_profiling_leaves_the_tree_byte_for_byte_alone(
        self, tmp_path: Path
    ) -> None:
        root = repo(tmp_path, TS_E2E, "e2e")
        before = _snapshot(root)

        profile_repo(root)

        assert _snapshot(root) == before


# --- the command line --------------------------------------------------------------


@pytest.fixture
def cli_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Drafts and profiles in a tmp folder - the real `profiles/` is never touched."""
    drafts, profiles = tmp_path / "drafts", tmp_path / "profiles"
    monkeypatch.setattr("jspec.profiler.drafts_dir", lambda *_: drafts)
    monkeypatch.setattr("jspec.profiles.profiles_dir", lambda *_: profiles)
    return drafts, profiles


def run(capsys, *argv: str) -> tuple[int, dict, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    payload = json.loads(captured.out) if captured.out.strip() else {}
    return code, payload, captured.err


class TestTheCommand:
    def test_draft_then_accept(self, capsys, tmp_path: Path, cli_dirs) -> None:
        _, profiles = cli_dirs
        root = repo(tmp_path, PY_SERVICE, "shop")

        code, out, _ = run(capsys, "profile", "draft", str(root))
        assert code == EXIT_OK
        assert out["name"] == "shop" and out["summary"]["unknown"] == 0
        assert out["saved_to"].endswith("shop.yaml")

        code, out, _ = run(capsys, "profile", "accept", "shop")
        assert code == EXIT_OK and out["accepted"] is True
        assert load_profile("shop", profiles).validation.test == "pytest"

    def test_a_correction_is_kept_on_the_next_draft(
        self, capsys, tmp_path: Path, cli_dirs
    ) -> None:
        root = repo(tmp_path, PY_SERVICE, "shop")
        run(
            capsys,
            "profile",
            "draft",
            str(root),
            "--set",
            "validation.test=tox -e unit",
        )
        _, out, _ = run(capsys, "profile", "draft", str(root))

        found = {f["field"]: f for f in out["findings"]}["validation.test"]
        assert found["value"] == "tox -e unit" and found["basis"] == "confirmed"

    def test_a_refusal_is_exit_one_with_every_blocker(
        self, capsys, tmp_path: Path, cli_dirs
    ) -> None:
        root = repo(tmp_path, {"README.md": "x\n"}, "empty")
        run(capsys, "profile", "draft", str(root))
        code, out, _ = run(capsys, "profile", "accept", "empty")

        assert code == EXIT_ANSWER_IS_NO
        assert out["accepted"] is False and out["blockers"]

    def test_accepting_with_no_draft_names_the_command_that_makes_one(
        self, capsys, cli_dirs
    ) -> None:
        code, _, err = run(capsys, "profile", "accept", "ghost")

        assert code == EXIT_USAGE and "profile draft" in err

    def test_a_malformed_set_is_a_usage_error(
        self, capsys, tmp_path: Path, cli_dirs
    ) -> None:
        root = repo(tmp_path, PY_SERVICE, "shop")
        code, _, err = run(
            capsys, "profile", "draft", str(root), "--set", "no-equals-sign"
        )

        assert code == EXIT_USAGE and "field=value" in err

    def test_use_index_without_an_index_says_so_instead_of_failing(
        self, capsys, tmp_path: Path, cli_dirs, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "jspec.graph.store.index_dir", lambda *_: tmp_path / "no-index"
        )
        root = repo(tmp_path, PY_SERVICE, "shop")
        code, out, _ = run(capsys, "profile", "draft", str(root), "--use-index")

        assert code == EXIT_OK
        assert any("no index used" in o for o in out["observations"])

    def test_a_missing_folder_is_a_usage_error(
        self, capsys, tmp_path: Path, cli_dirs
    ) -> None:
        code, _, err = run(capsys, "profile", "draft", str(tmp_path / "nope"))

        assert code == EXIT_USAGE and "not a directory" in err

    def test_yaml_drafts_are_human_editable(
        self, capsys, tmp_path: Path, cli_dirs
    ) -> None:
        drafts, _ = cli_dirs
        run(capsys, "profile", "draft", str(repo(tmp_path, PY_SERVICE, "shop")))
        text = (drafts / "shop.yaml").read_text(encoding="utf-8")

        assert text.startswith("#") and "jspec profile accept shop" in text
        assert yaml.safe_load(text)["findings"][0]["field"] == "name"
