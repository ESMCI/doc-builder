#!/usr/bin/env python3

"""Unit tests for check_image_published"""

import os
import subprocess
from subprocess import run as real_subprocess_run  # Not affected by patching subprocess.run
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# pylint: disable=import-error
from doc_builder.check_image_published import (
    classify_manifest_output,
    is_downstream,
    main,
    missing_downstream_message,
    ManifestStatus,
    EXIT_OK,
    EXIT_MISSING_DOWNSTREAM,
    EXIT_CHECK_ERROR,
    _DOC_BUILDER_ROOT,
)

_IMAGE = "ghcr.io/example/doc-build-container:v9.9.9"
_EXISTS_OUTPUT = (
    '{\n   "schemaVersion": 2,\n   "mediaType": "application/vnd.oci.image.index.v1+json"\n}\n'
)
_MISSING_OUTPUT = "manifest unknown\n"
_OTHER_OUTPUT = "Get https://ghcr.io/v2/: net/http: TLS handshake timeout\n"
_SUPERPROJECT = "/path/to/superproject"
_HOST_TOPLEVEL = "/path/to/host"

# Root of the doc-builder checkout being tested. Deliberately not taken from
# check_image_published._DOC_BUILDER_ROOT, which test_git_run_on_doc_builder_root checks.
_THIS_DOC_BUILDER = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
)


def _fake_run(docker_output="", docker_returncode=0, toplevel=_DOC_BUILDER_ROOT, superproject=""):
    """Return a stand-in for subprocess.run that gives canned docker and git results

    toplevel and superproject are what `git rev-parse --show-toplevel` and
    `git rev-parse --show-superproject-working-tree` print. If toplevel is None, git fails.
    """

    def run(cmd, **kwargs):
        if cmd[0] == "docker":
            return SimpleNamespace(returncode=docker_returncode, stdout=docker_output)
        if cmd[0] == "git":
            if toplevel is None:
                assert kwargs.get("check")
                raise subprocess.CalledProcessError(
                    128, cmd, output="", stderr="fatal: not a git repository\n"
                )
            stdout = toplevel if cmd[-1] == "--show-toplevel" else superproject
            return SimpleNamespace(returncode=0, stdout=stdout + "\n" if stdout else "")
        raise AssertionError(f"Unexpected command: {cmd}")

    return run


def _git_was_called(mock_run):
    """Return True if any call to the mocked subprocess.run ran git"""
    return any(args[0][0] == "git" for args, _ in mock_run.call_args_list)


@pytest.fixture(name="github_output")
def fixture_github_output(tmp_path, monkeypatch):
    """Point GITHUB_OUTPUT at a file in tmp_path"""
    path = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    return path


@pytest.fixture(name="no_github_output")
def fixture_no_github_output(monkeypatch):
    """Ensure GITHUB_OUTPUT is unset"""
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)


class TestClassifyManifestOutput:
    """Tests of classify_manifest_output"""

    def test_exists(self):
        """Output containing schemaVersion means the image exists"""
        assert classify_manifest_output(_EXISTS_OUTPUT) == ManifestStatus.EXISTS

    def test_missing(self):
        """Output that is exactly 'manifest unknown' means the image is missing"""
        assert classify_manifest_output("manifest unknown") == ManifestStatus.MISSING

    def test_manifest_unknown_with_extra_text_is_unknown(self):
        """'manifest unknown' must be the whole output to count as missing"""
        result = classify_manifest_output("Error: manifest unknown: something else")
        assert result == ManifestStatus.UNKNOWN

    def test_other(self):
        """Anything else is unknown"""
        assert classify_manifest_output(_OTHER_OUTPUT) == ManifestStatus.UNKNOWN

    def test_empty(self):
        """Empty output is unknown"""
        assert classify_manifest_output("") == ManifestStatus.UNKNOWN


class TestIsDownstream:
    """Tests of is_downstream, with git calls faked"""

    @patch("subprocess.run")
    def test_git_run_on_given_dir(self, mock_run):
        """git is pointed at the given directory with -C, not left to use the cwd"""
        mock_run.side_effect = _fake_run(toplevel=_HOST_TOPLEVEL)
        is_downstream(_HOST_TOPLEVEL)
        git_cmds = [args[0] for args, _ in mock_run.call_args_list if args[0][0] == "git"]
        assert git_cmds
        for cmd in git_cmds:
            assert cmd[1:3] == ["-C", _HOST_TOPLEVEL]

    @patch("subprocess.run")
    def test_own_toplevel_no_superproject(self, mock_run):
        """Top level of its own checkout, not a submodule: doc-builder itself"""
        mock_run.side_effect = _fake_run(toplevel=_DOC_BUILDER_ROOT, superproject="")
        assert not is_downstream(_DOC_BUILDER_ROOT)

    @patch("subprocess.run")
    def test_own_toplevel_with_superproject(self, mock_run):
        """Top level of its own checkout, which is a submodule: downstream"""
        mock_run.side_effect = _fake_run(toplevel=_DOC_BUILDER_ROOT, superproject=_SUPERPROJECT)
        assert is_downstream(_DOC_BUILDER_ROOT)

    @patch("subprocess.run")
    def test_other_toplevel(self, mock_run):
        """Inside some other repo's checkout (copied in): downstream"""
        mock_run.side_effect = _fake_run(toplevel=_HOST_TOPLEVEL, superproject="")
        assert is_downstream(_DOC_BUILDER_ROOT)

    @patch("subprocess.run")
    def test_unnormalized_path(self, mock_run):
        """Paths are compared after normalization"""
        mock_run.side_effect = _fake_run(toplevel=_DOC_BUILDER_ROOT, superproject="")
        assert not is_downstream(os.path.join(_DOC_BUILDER_ROOT, "doc_builder", os.pardir))

    @patch("subprocess.run")
    def test_git_failure_raises(self, mock_run):
        """If git fails, raise rather than guess"""
        mock_run.side_effect = _fake_run(toplevel=None)
        with pytest.raises(subprocess.CalledProcessError):
            is_downstream(_DOC_BUILDER_ROOT)


class TestMain:
    """Tests of main, with docker and git calls faked"""

    @patch("subprocess.run")
    def test_exists_builds(self, mock_run, github_output, capsys):
        """Existing image: exit 0, build=true to GITHUB_OUTPUT and stdout, no git"""
        mock_run.side_effect = _fake_run(_EXISTS_OUTPUT)
        assert main([], image=_IMAGE) == EXIT_OK
        assert github_output.read_text(encoding="utf-8") == "build=true\n"
        captured = capsys.readouterr()
        assert "build=true" in captured.out
        assert captured.err == ""
        assert not _git_was_called(mock_run)

    @patch("subprocess.run")
    @pytest.mark.usefixtures("no_github_output")
    def test_docker_command(self, mock_run):
        """docker manifest inspect is called on the given image, with stderr merged into stdout"""
        mock_run.side_effect = _fake_run(_EXISTS_OUTPUT)
        main([], image=_IMAGE)
        args, kwargs = mock_run.call_args_list[0]
        assert args[0] == ["docker", "manifest", "inspect", _IMAGE]
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.STDOUT

    @patch("subprocess.run")
    def test_missing_doc_builder_skips(self, mock_run, github_output, tmp_path, capsys):
        """Missing image in doc-builder itself: warn, build=false, exit 0, no log file"""
        log_file = tmp_path / "logs" / "build.log"
        mock_run.side_effect = _fake_run(_MISSING_OUTPUT, docker_returncode=1)
        assert main(["--log-file", str(log_file)], image=_IMAGE) == EXIT_OK
        assert github_output.read_text(encoding="utf-8") == "build=false\n"
        captured = capsys.readouterr()
        warning_lines = [line for line in captured.out.splitlines() if line.startswith("::warning")]
        assert len(warning_lines) == 1
        assert _IMAGE in warning_lines[0]
        assert "build=false" in captured.out
        assert captured.err == ""
        assert not log_file.exists()

    @pytest.mark.parametrize(
        "git_outputs",
        [{"superproject": _SUPERPROJECT}, {"toplevel": _HOST_TOPLEVEL}],
        ids=["submodule", "copied_in"],
    )
    @patch("subprocess.run")
    def test_missing_downstream_fails(self, mock_run, git_outputs, github_output, tmp_path, capsys):
        """Missing image downstream: nonzero exit, message to stderr and log, no GITHUB_OUTPUT"""
        log_file = tmp_path / "build-logs" / "build.log"
        mock_run.side_effect = _fake_run(_MISSING_OUTPUT, docker_returncode=1, **git_outputs)
        result = main(["--log-file", str(log_file)], image=_IMAGE)
        assert result == EXIT_MISSING_DOWNSTREAM
        captured = capsys.readouterr()
        assert captured.err == missing_downstream_message(_IMAGE)
        assert "::warning" not in captured.out
        assert log_file.read_text(encoding="utf-8") == captured.err
        assert not github_output.exists()

    @patch("subprocess.run")
    @pytest.mark.usefixtures("no_github_output")
    def test_missing_downstream_no_log_file(self, mock_run, capsys):
        """Missing image downstream without --log-file still fails and prints to stderr"""
        mock_run.side_effect = _fake_run(
            _MISSING_OUTPUT, docker_returncode=1, superproject=_SUPERPROJECT
        )
        assert main([], image=_IMAGE) == EXIT_MISSING_DOWNSTREAM
        assert _IMAGE in capsys.readouterr().err

    @patch("subprocess.run")
    def test_other_output_errors(self, mock_run, github_output, tmp_path, capsys):
        """Unrecognized docker output: error exit with output shown, no git"""
        log_file = tmp_path / "build.log"
        mock_run.side_effect = _fake_run(_OTHER_OUTPUT, docker_returncode=1)
        result = main(["--log-file", str(log_file)], image=_IMAGE)
        assert result == EXIT_CHECK_ERROR
        captured = capsys.readouterr()
        assert _OTHER_OUTPUT.strip() in captured.err
        assert _IMAGE in captured.err
        assert log_file.read_text(encoding="utf-8") == captured.err
        assert not github_output.exists()
        assert not _git_was_called(mock_run)

    @patch("subprocess.run")
    def test_undecodable_output_errors(self, mock_run, github_output, tmp_path, capsys):
        """docker output that isn't valid UTF-8 is unrecognized: error exit, not an exception"""
        log_file = tmp_path / "build.log"
        script = "import sys; sys.stdout.buffer.write(b'bad \\xff\\xfe bytes\\n'); sys.exit(1)"

        def run(cmd, check, **kwargs):
            """Stand in for docker with a real subprocess, so the output is decoded the way
            subprocess.run decodes it given the arguments the tool passes"""
            assert cmd[0] == "docker"
            return real_subprocess_run([sys.executable, "-c", script], check=check, **kwargs)

        mock_run.side_effect = run
        result = main(["--log-file", str(log_file)], image=_IMAGE)
        assert result == EXIT_CHECK_ERROR
        err = capsys.readouterr().err
        assert err.startswith(f"ERROR: Could not check whether container image {_IMAGE} exists:")
        assert "exited with code 1" in err
        assert "bad \ufffd\ufffd bytes" in err
        assert log_file.read_text(encoding="utf-8") == err
        assert not github_output.exists()
        assert [args[0][0] for args, _ in mock_run.call_args_list] == ["docker"]

    @patch("subprocess.run")
    def test_docker_not_found_errors(self, mock_run, github_output, capsys):
        """If docker can't be run, error"""
        mock_run.side_effect = FileNotFoundError(2, "No such file or directory", "docker")
        assert main([], image=_IMAGE) == EXIT_CHECK_ERROR
        assert "docker" in capsys.readouterr().err
        assert not github_output.exists()

    @patch("subprocess.run")
    @pytest.mark.usefixtures("no_github_output")
    def test_git_run_on_doc_builder_root(self, mock_run, tmp_path, monkeypatch):
        """With the image missing, git is pointed at this doc-builder's root with -C, even when the
        cwd at call time is elsewhere. (The module computes the root at import time, so the
        end-to-end system tests are what catch a root derived from the cwd at import.)"""
        monkeypatch.chdir(tmp_path)
        mock_run.side_effect = _fake_run(_MISSING_OUTPUT, docker_returncode=1)
        main([], image=_IMAGE)
        git_cmds = [args[0] for args, _ in mock_run.call_args_list if args[0][0] == "git"]
        assert git_cmds
        for cmd in git_cmds:
            assert cmd[1] == "-C"
            assert os.path.realpath(cmd[2]) == os.path.realpath(_THIS_DOC_BUILDER)

    @patch("subprocess.run")
    def test_git_failure_errors(self, mock_run, github_output, tmp_path, capsys):
        """If git can't tell whether we're downstream, error rather than guess.

        The message says the image is missing (not that the registry check failed) and shows git's
        error.
        """
        log_file = tmp_path / "build.log"
        mock_run.side_effect = _fake_run(_MISSING_OUTPUT, docker_returncode=1, toplevel=None)
        assert main(["--log-file", str(log_file)], image=_IMAGE) == EXIT_CHECK_ERROR
        err = capsys.readouterr().err
        assert err.startswith(f"ERROR: Container image not found on registry:\n    {_IMAGE}\n")
        assert "Could not determine whether this is doc-builder itself" in err
        assert "Could not check whether" not in err
        assert "not a git repository" in err
        assert log_file.read_text(encoding="utf-8") == err
        assert not github_output.exists()

    @patch("subprocess.run")
    def test_github_output_appends(self, mock_run, github_output):
        """GITHUB_OUTPUT is appended to, not overwritten"""
        github_output.write_text("other=thing\n", encoding="utf-8")
        mock_run.side_effect = _fake_run(_EXISTS_OUTPUT)
        main([], image=_IMAGE)
        assert github_output.read_text(encoding="utf-8") == "other=thing\nbuild=true\n"

    @pytest.mark.parametrize(
        "docker_output, superproject",
        [(_EXISTS_OUTPUT, ""), (_MISSING_OUTPUT, ""), (_MISSING_OUTPUT, _SUPERPROJECT)],
    )
    @patch("subprocess.run")
    @pytest.mark.usefixtures("no_github_output")
    def test_github_output_unset(
        self, mock_run, docker_output, superproject, tmp_path, monkeypatch
    ):
        """With GITHUB_OUTPUT unset, no file is written"""
        monkeypatch.chdir(tmp_path)
        mock_run.side_effect = _fake_run(docker_output, superproject=superproject)
        main([], image=_IMAGE)
        assert not list(tmp_path.iterdir())


def test_missing_downstream_message_wrapped():
    """The downstream message is hand-wrapped to fit in a code block in a PR comment"""
    for line in missing_downstream_message(_IMAGE).splitlines():
        assert len(line) <= 75, line
