#!/usr/bin/env python3
"""System tests of check_image_published

These run real subprocesses: a fake docker executable put on PATH, and git on real repos made in
temporary directories. The end-to-end tests run tools/check_image_published.py from a copy of this
doc-builder checkout placed in each repo layout the tool has to tell apart.

Everything runs with the cwd in a directory outside any git repo, so that a tool that looked at the
cwd instead of its own location would fail.
"""

import os
import shutil
import stat
import subprocess
import sys

# pylint: disable=import-error,no-name-in-module
from test.test_utils.git_helpers import make_git_repo, add_git_commit
from test.test_utils.test_helpers import check_call_suppress_output

import pytest

from doc_builder.build_commands import DEFAULT_IMAGE
from doc_builder.check_image_published import (
    is_downstream,
    missing_downstream_message,
    unknown_layout_message,
    EXIT_OK,
    EXIT_MISSING_DOWNSTREAM,
    EXIT_CHECK_ERROR,
)

# Fake docker script bodies
_DOCKER_MISSING = "echo 'manifest unknown' >&2\nexit 1\n"
_DOCKER_EXISTS = "printf '{\\n  \"schemaVersion\": 2\\n}\\n'\nexit 0\n"

# Root of the doc-builder checkout being tested. Deliberately not taken from
# check_image_published._DOC_BUILDER_ROOT, which the end-to-end tests are meant to check.
_THIS_DOC_BUILDER = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
)


def _git_toplevel(path):
    """Run `git -C path rev-parse --show-toplevel` and return the CompletedProcess"""
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _assert_outside_git(path):
    """Fail if path is inside a git repo, which would make tests that rely on it not being in one
    pass vacuously"""
    result = _git_toplevel(path)
    assert result.returncode != 0, (
        f"{path} is inside the git repo at {result.stdout.strip()}; this test needs a directory "
        "outside any git repo (is the temporary directory inside one?)"
    )


def _install_fake_docker(tmp_path, monkeypatch, script_body):
    """Put an executable named docker, running the given sh script body, at the front of PATH"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text("#!/bin/sh\n" + script_body, encoding="utf-8")
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])


def _init_repo(path, monkeypatch):
    """Make path (creating it if needed) a git repo with a test identity, and leave the cwd there"""
    path.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(path)
    make_git_repo()
    check_call_suppress_output("git config user.name 'Test User'")
    check_call_suppress_output("git config user.email 'test@example.com'")


def _make_repo(path, monkeypatch):
    """Make a git repo with one commit at path, and leave the cwd there"""
    _init_repo(path, monkeypatch)
    add_git_commit()


def _make_doc_builder_repo(path, monkeypatch):
    """Make a standalone doc-builder-like repo at path"""
    _make_repo(path, monkeypatch)
    os.mkdir("doc_builder")
    add_git_commit(os.path.join("doc_builder", "build_docs.py"))


def _commit_all():
    """Commit everything in the git repo at the cwd"""
    check_call_suppress_output("git add -A")
    check_call_suppress_output("git commit -m 'Add everything'")


def _copy_this_doc_builder(dest):
    """Copy the files git tracks in this doc-builder checkout to dest, as they are in the working
    tree (so uncommitted edits to them are included)"""
    result = subprocess.run(
        ["git", "-C", _THIS_DOC_BUILDER, "ls-files", "-z"],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    for rel_path in result.stdout.split("\0"):
        src = os.path.join(_THIS_DOC_BUILDER, rel_path)
        # Skips the empty string after the last \0, and anything deleted from the working tree
        if not rel_path or not os.path.isfile(src):
            continue
        dst = os.path.join(dest, rel_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    assert os.path.isfile(os.path.join(dest, "tools", "check_image_published.py"))


def _make_standalone_layout(tmp_path, monkeypatch):
    """doc-builder as its own git repo. Returns the doc-builder directory."""
    doc_builder_dir = tmp_path / "doc-builder"
    _copy_this_doc_builder(doc_builder_dir)
    _init_repo(doc_builder_dir, monkeypatch)
    _commit_all()
    return doc_builder_dir


def _make_submodule_layout(tmp_path, monkeypatch):
    """A host repo with doc-builder as a submodule at doc/doc-builder. Returns the doc-builder
    directory."""
    source_dir = tmp_path / "doc-builder-source"
    _copy_this_doc_builder(source_dir)
    _init_repo(source_dir, monkeypatch)
    _commit_all()

    host_dir = tmp_path / "host"
    _make_repo(host_dir, monkeypatch)
    check_call_suppress_output(
        f"git -c protocol.file.allow=always submodule add '{source_dir}' doc/doc-builder"
    )
    check_call_suppress_output("git commit -m 'Add doc-builder submodule'")
    doc_builder_dir = host_dir / "doc" / "doc-builder"
    assert (doc_builder_dir / ".git").is_file()
    return doc_builder_dir


def _make_copied_in_layout(tmp_path, monkeypatch):
    """A host repo with doc-builder's files committed as a plain directory at doc/doc-builder.
    Returns the doc-builder directory."""
    host_dir = tmp_path / "host"
    _make_repo(host_dir, monkeypatch)
    doc_builder_dir = host_dir / "doc" / "doc-builder"
    _copy_this_doc_builder(doc_builder_dir)
    _commit_all()
    assert not (doc_builder_dir / ".git").exists()
    return doc_builder_dir


def _make_no_repo_layout(tmp_path):
    """doc-builder's files in a plain directory that isn't in any git repo. Returns the
    doc-builder directory."""
    doc_builder_dir = tmp_path / "doc-builder"
    _copy_this_doc_builder(doc_builder_dir)
    _assert_outside_git(doc_builder_dir)
    return doc_builder_dir


def _run_tool(doc_builder_dir, cwd, log_file):
    """Run tools/check_image_published.py in doc_builder_dir from cwd, with --log-file"""
    return subprocess.run(
        [
            sys.executable,
            str(doc_builder_dir / "tools" / "check_image_published.py"),
            "--log-file",
            str(log_file),
        ],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


@pytest.fixture(name="github_output")
def fixture_github_output(tmp_path, monkeypatch):
    """Point GITHUB_OUTPUT at a file in tmp_path"""
    path = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    return path


@pytest.fixture(name="log_file")
def fixture_log_file(tmp_path):
    """Path for the tool's --log-file, in a directory that doesn't exist yet"""
    return tmp_path / "build-logs" / "build.log"


@pytest.fixture(name="outside_dir")
def fixture_outside_dir(tmp_path):
    """An empty directory that isn't in any git repo"""
    path = tmp_path / "outside"
    path.mkdir()
    _assert_outside_git(path)
    return path


@pytest.fixture(name="no_pythonpath")
def fixture_no_pythonpath(monkeypatch):
    """Unset PYTHONPATH, so the tool can only import doc_builder via its own sys.path setup"""
    monkeypatch.delenv("PYTHONPATH", raising=False)


@pytest.mark.usefixtures("no_pythonpath")
class TestToolEndToEnd:
    """Run tools/check_image_published.py from a copy of this doc-builder in each repo layout"""

    def test_standalone_missing_skips(
        self, tmp_path, monkeypatch, outside_dir, github_output, log_file
    ):
        """Image missing in doc-builder itself: warn, build=false, exit 0, no log file"""
        doc_builder_dir = _make_standalone_layout(tmp_path, monkeypatch)
        _install_fake_docker(tmp_path, monkeypatch, _DOCKER_MISSING)
        result = _run_tool(doc_builder_dir, outside_dir, log_file)
        assert result.returncode == EXIT_OK, result.stderr
        assert "::warning::" in result.stdout
        assert result.stderr == ""
        assert github_output.read_text(encoding="utf-8") == "build=false\n"
        assert not log_file.exists()

    def test_standalone_exists_builds(
        self, tmp_path, monkeypatch, outside_dir, github_output, log_file
    ):
        """Image exists: build=true, exit 0"""
        doc_builder_dir = _make_standalone_layout(tmp_path, monkeypatch)
        _install_fake_docker(tmp_path, monkeypatch, _DOCKER_EXISTS)
        result = _run_tool(doc_builder_dir, outside_dir, log_file)
        assert result.returncode == EXIT_OK, result.stderr
        assert "build=true" in result.stdout
        assert result.stderr == ""
        assert github_output.read_text(encoding="utf-8") == "build=true\n"
        assert not log_file.exists()

    @pytest.mark.parametrize(
        "make_layout",
        [_make_submodule_layout, _make_copied_in_layout],
        ids=["submodule", "copied_in"],
    )
    def test_downstream_missing_fails(
        self, make_layout, tmp_path, monkeypatch, outside_dir, github_output, log_file
    ):
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        """Image missing downstream: exit 1, message to stderr and log file, no GITHUB_OUTPUT"""
        doc_builder_dir = make_layout(tmp_path, monkeypatch)
        _install_fake_docker(tmp_path, monkeypatch, _DOCKER_MISSING)
        result = _run_tool(doc_builder_dir, outside_dir, log_file)
        assert result.returncode == EXIT_MISSING_DOWNSTREAM, result.stderr
        assert result.stderr == missing_downstream_message(DEFAULT_IMAGE)
        assert "::warning" not in result.stdout
        assert log_file.read_text(encoding="utf-8") == result.stderr
        assert not github_output.exists()

    def test_no_repo_missing_errors(
        self, tmp_path, monkeypatch, outside_dir, github_output, log_file
    ):
        """Image missing, doc-builder not in any git repo: exit 3, git's error in the message"""
        doc_builder_dir = _make_no_repo_layout(tmp_path)
        _install_fake_docker(tmp_path, monkeypatch, _DOCKER_MISSING)
        result = _run_tool(doc_builder_dir, outside_dir, log_file)
        assert result.returncode == EXIT_CHECK_ERROR, result.stderr
        # git's error text varies between versions, so check the fixed part of the message
        # exactly and that it ends with what git actually says here
        fixed_part = unknown_layout_message(DEFAULT_IMAGE, "")[: -len("\n")]
        assert result.stderr.startswith(fixed_part)
        git_error = _git_toplevel(doc_builder_dir).stderr.rstrip("\n")
        assert git_error
        assert result.stderr.endswith("\n" + git_error + "\n")
        assert log_file.read_text(encoding="utf-8") == result.stderr
        assert not github_output.exists()


class TestIsDownstream:
    """Tests of is_downstream against real git repos"""

    # pylint: disable=too-few-public-methods

    def test_standalone_via_symlink(self, tmp_path, monkeypatch, outside_dir):
        """A standalone doc-builder repo reached through a symlink is not downstream"""
        doc_builder_dir = tmp_path / "doc-builder"
        _make_doc_builder_repo(doc_builder_dir, monkeypatch)
        link = tmp_path / "link"
        link.symlink_to(doc_builder_dir, target_is_directory=True)
        monkeypatch.chdir(outside_dir)
        assert not is_downstream(str(link))
