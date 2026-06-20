#!/usr/bin/env python3

"""Unit tests for run_build_command output behavior"""

import subprocess
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from io import StringIO

from doc_builder.build_docs import (  # pylint: disable=import-error
    run_build_command,
    _maybe_start_container,
    _MSG_BUILD_FAILED,
    _MSG_BUILD_COMPLETED_WITH_PROBLEMS,
    _SPHINX_BUILD_FINISHED_WITH_PROBLEMS,
)

import pytest

# A minimal options object for testing (non-container)
_BASE_OPTIONS = {
    "build_in_container": False,
    "version_display_name": None,
    "versions": False,
    "static_path": "_static",
    "templates_path": "_templates",
}

_FAKE_COMMAND = ["make", "SPHINXOPTS=", "BUILDDIR=/tmp/build", "-j", "4", "html"]
_FAKE_VERSION = "main"

# Simulated Sphinx output with warnings buried in noise
_SPHINX_STDOUT_WITH_WARNINGS = (
    "Running Sphinx v4.5.0\n"
    "building [html]: targets for 3 source files\n"
    "/path/to/file.rst:42: WARNING: toctree contains reference to nonexisting document 'missing'\n"
    "writing output... [100%] index\n"
    "WARNING: unknown config value 'bogus'\n"
)
_SPHINX_STDERR_WITH_ERROR = "/path/to/file.rst:42: ERROR: master file not found\n"
_SPHINX_STDERR_FINISHED_WITH_PROBLEMS = (
    "WARNING: unknown config value 'bogus'\n" + _SPHINX_BUILD_FINISHED_WITH_PROBLEMS + "\n"
)


def _make_options(verbose):
    """Create a test options namespace with the given verbose setting"""
    return SimpleNamespace(**_BASE_OPTIONS, verbose=verbose)


def _make_called_process_error(stdout_text, stderr_text):
    """Create a CalledProcessError with the given stdout/stderr"""
    err = subprocess.CalledProcessError(returncode=2, cmd=_FAKE_COMMAND)
    err.stdout = stdout_text.encode("utf-8")
    err.stderr = stderr_text.encode("utf-8")
    return err


class TestRunBuildCommandOutput:
    """Tests for run_build_command output in verbose vs. non-verbose mode"""

    @patch("subprocess.run")
    def test_non_verbose_prints_building_message(self, mock_run):
        """In non-verbose mode, prints 'Building documentation...' before building"""
        mock_run.return_value = MagicMock(returncode=0)
        opts = _make_options(verbose=False)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            run_build_command(_FAKE_COMMAND, _FAKE_VERSION, opts)
        assert "Building documentation..." in mock_stdout.getvalue()

    @patch("subprocess.run")
    def test_success_non_verbose_prints_complete_message(self, mock_run):
        """On success in non-verbose mode, prints completion message"""
        mock_run.return_value = MagicMock(returncode=0)
        opts = _make_options(verbose=False)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            run_build_command(_FAKE_COMMAND, _FAKE_VERSION, opts)
        assert "Done." in mock_stdout.getvalue()

    @patch("subprocess.run")
    def test_success_non_verbose_no_command_echo(self, mock_run):
        """On success in non-verbose mode, does not echo the build command"""
        mock_run.return_value = MagicMock(returncode=0)
        opts = _make_options(verbose=False)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            run_build_command(_FAKE_COMMAND, _FAKE_VERSION, opts)
        assert "make" not in mock_stdout.getvalue()

    @patch("subprocess.run")
    def test_success_verbose_echoes_command(self, mock_run):
        """On success in verbose mode, echoes the build command"""
        mock_run.return_value = MagicMock(returncode=0)
        opts = _make_options(verbose=True)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            run_build_command(_FAKE_COMMAND, _FAKE_VERSION, opts)
        assert "make" in mock_stdout.getvalue()

    @patch("subprocess.run")
    def test_failure_non_verbose_shows_only_complaints(self, mock_run):
        """On failure in non-verbose mode, shows only WARNING/ERROR lines"""
        mock_run.side_effect = _make_called_process_error(
            _SPHINX_STDOUT_WITH_WARNINGS, _SPHINX_STDERR_WITH_ERROR
        )
        opts = _make_options(verbose=False)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout, patch(
            "sys.stderr", new_callable=StringIO
        ) as mock_stderr:
            with pytest.raises(SystemExit):
                run_build_command(_FAKE_COMMAND, _FAKE_VERSION, opts)
        combined = mock_stdout.getvalue() + mock_stderr.getvalue()
        assert "WARNING: toctree contains reference" in combined
        assert "WARNING: unknown config value" not in combined  # Because WARNING at line start
        assert "ERROR: master file not found" in combined
        # Should NOT contain normal Sphinx noise
        assert "Running Sphinx" not in combined
        assert "building [html]" not in combined

    @patch("subprocess.run")
    def test_failure_non_verbose_shows_hint(self, mock_run):
        """On failure in non-verbose mode, shows hint to use --verbose"""
        mock_run.side_effect = _make_called_process_error(
            _SPHINX_STDOUT_WITH_WARNINGS, _SPHINX_STDERR_WITH_ERROR
        )
        opts = _make_options(verbose=False)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout, patch(
            "sys.stderr", new_callable=StringIO
        ) as mock_stderr:
            with pytest.raises(SystemExit):
                run_build_command(_FAKE_COMMAND, _FAKE_VERSION, opts)
        combined = mock_stdout.getvalue() + mock_stderr.getvalue()
        assert "--verbose" in combined

    @patch("subprocess.run")
    def test_failure_non_verbose_shows_failed_message(self, mock_run):
        """On hard failure (not 'finished with problems'), shows failed message"""
        mock_run.side_effect = _make_called_process_error(
            _SPHINX_STDOUT_WITH_WARNINGS, _SPHINX_STDERR_WITH_ERROR
        )
        opts = _make_options(verbose=False)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout, patch(
            "sys.stderr", new_callable=StringIO
        ) as mock_stderr:
            with pytest.raises(SystemExit):
                run_build_command(_FAKE_COMMAND, _FAKE_VERSION, opts)
        combined = mock_stdout.getvalue() + mock_stderr.getvalue()
        assert _MSG_BUILD_FAILED in combined
        assert _MSG_BUILD_COMPLETED_WITH_PROBLEMS not in combined

    @patch("subprocess.run")
    def test_failure_non_verbose_finished_with_problems(self, mock_run):
        """When Sphinx says 'build finished with problems', shows softer message"""
        mock_run.side_effect = _make_called_process_error(
            _SPHINX_STDOUT_WITH_WARNINGS, _SPHINX_STDERR_FINISHED_WITH_PROBLEMS
        )
        opts = _make_options(verbose=False)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout, patch(
            "sys.stderr", new_callable=StringIO
        ) as mock_stderr:
            with pytest.raises(SystemExit):
                run_build_command(_FAKE_COMMAND, _FAKE_VERSION, opts)
        combined = mock_stdout.getvalue() + mock_stderr.getvalue()
        assert _MSG_BUILD_COMPLETED_WITH_PROBLEMS in combined
        assert _MSG_BUILD_FAILED not in combined

    @patch("subprocess.run")
    def test_failure_verbose_shows_full_output(self, mock_run):
        """On failure in verbose mode, dumps full stdout and stderr"""
        mock_run.side_effect = _make_called_process_error(
            _SPHINX_STDOUT_WITH_WARNINGS, _SPHINX_STDERR_WITH_ERROR
        )
        opts = _make_options(verbose=True)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout, patch(
            "sys.stderr", new_callable=StringIO
        ) as mock_stderr:
            with pytest.raises(subprocess.CalledProcessError):
                run_build_command(_FAKE_COMMAND, _FAKE_VERSION, opts)
        combined = mock_stdout.getvalue() + mock_stderr.getvalue()
        # Verbose mode shows everything including normal lines
        assert "Running Sphinx" in combined
        assert "building [html]" in combined


class TestMaybeStartContainer:
    """Tests for _maybe_start_container output"""

    # pylint: disable=too-few-public-methods

    @patch("doc_builder.build_docs.start_container_software")
    def test_no_output(self, _mock_start):
        """Container startup should not print anything"""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            _maybe_start_container(["podman", "run", "image"])
        assert "" == mock_stdout.getvalue()
