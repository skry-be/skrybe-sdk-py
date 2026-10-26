import re
from pathlib import Path

import skrybe

ROOT = Path(__file__).resolve().parent.parent


def test_version_matches_the_latest_released_changelog_heading():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    # The first versioned heading; "## [Unreleased]" has no number and is skipped.
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    assert match, "CHANGELOG.md has no released version heading"
    assert skrybe.VERSION == match.group(1)
    assert skrybe.__version__ == skrybe.VERSION


def test_pyproject_reads_the_version_from_the_package():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "skrybe-sdk"' in pyproject
    assert 'version = { attr = "skrybe._version.VERSION" }' in pyproject


def test_runtime_dependencies_are_requests_and_certifi():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    deps = re.search(r"^dependencies = \[(.*?)\]", pyproject, re.MULTILINE | re.DOTALL)
    assert deps and re.findall(r'"([a-zA-Z0-9_.-]+)', deps.group(1)) == ["requests", "certifi"]


def test_ships_a_py_typed_marker():
    assert (Path(skrybe.__file__).parent / "py.typed").is_file()


def test_public_exceptions_share_a_base():
    for name in ("AuthenticationError", "InvalidRequestError", "RateLimitError", "ConnectionError", "ApiError"):
        assert issubclass(getattr(skrybe, name), skrybe.SkrybeError)
