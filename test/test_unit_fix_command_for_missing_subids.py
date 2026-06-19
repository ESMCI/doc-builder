#!/usr/bin/env python3

"""Unit test driver for _fix_command_for_missing_subids and the retry logic in run_build_command"""

import subprocess
from argparse import Namespace
from unittest.mock import patch, MagicMock

# pylint: disable=import-error,attribute-defined-outside-init
from doc_builder.build_docs import _fix_command_for_missing_subids, run_build_command
from doc_builder.build_commands import DEFAULT_IMAGE

import pytest

# Allow names that pylint doesn't like, because otherwise I find it hard
# to make readable unit test names
# pylint: disable=invalid-name

# Build commands to be tested
_BASE_VOLUME_STR = "/path/to/repo:/home/user/mounted_home:U"
_FIXED_VOLUME_STR = "/path/to/repo:/home/user/mounted_home"
_BASE_USER_STR = "37083:1000"
_FIXED_USER_STR = "0:0"
_BASE_COMMAND = [
    "podman",
    "run",
    "--name",
    "foo",
    "--user",
    _BASE_USER_STR,
    "-v",
    _BASE_VOLUME_STR,
    "--workdir",
    "/home/user/mounted_home/doc",
    "-t",
    "--rm",
    DEFAULT_IMAGE,
    "make",
    "html",
]
_FIXED_COMMAND = []
for x in _BASE_COMMAND:
    if x == _BASE_VOLUME_STR:
        _FIXED_COMMAND.append(_FIXED_VOLUME_STR)
    elif x == _BASE_USER_STR:
        _FIXED_COMMAND.append(_FIXED_USER_STR)
    else:
        _FIXED_COMMAND.append(x)


class TestFixCommandForMissingSubids():
    """Test the _fix_command_for_missing_subids function"""

    def setup_method(self):
        """To run at the beginning of each test"""
        self.result = _fix_command_for_missing_subids(list(_BASE_COMMAND))

    def test_removes_U_suffix_from_mount(self):
        """The :U suffix should be removed from volume mount arguments"""
        assert "/path/to/repo:/home/user/mounted_home" in self.result
        assert "/path/to/repo:/home/user/mounted_home:U" not in self.result

    def test_changes_user_to_root(self):
        """--user should be changed to 0:0"""
        user_idx = self.result.index("--user")
        assert self.result[user_idx + 1] == _FIXED_USER_STR

    def test_preserves_other_args(self):
        """Arguments that aren't --user or :U mounts should be unchanged"""
        assert _FIXED_COMMAND == self.result

    def test_no_U_suffix_only_changes_user(self):
        """A command without :U mount should only change --user"""
        command = [
            "podman",
            "run",
            "--user",
            _BASE_USER_STR,
            "--mount",
            "type=bind,source=/path,target=/home/user/mounted_home",
            "image:latest",
            "make",
            "html",
        ]
        result = _fix_command_for_missing_subids(command)
        assert result[result.index("--user") + 1] == _FIXED_USER_STR
        assert "type=bind,source=/path,target=/home/user/mounted_home" in result


def _make_options():
    """Create a minimal options Namespace for run_build_command"""
    return Namespace(
        version_display_name=None,
        static_path="_static",
        templates_path="_templates",
        versions=False,
        build_in_container=True,
        verbose=True,
    )


@patch("doc_builder.build_docs.start_container_software")
class TestRunBuildCommandRetry():
    """Test that run_build_command retries with fixed args on chown failure"""

    @patch("doc_builder.build_docs.subprocess.run")
    def test_retries_on_chown_error(self, mock_run, _mock_start):
        """On chown failure, should retry with :U removed and --user 0:0"""
        msg = b"Error: failed to chown recursively host path: lchown /some/path: invalid argument"
        mock_run.side_effect = [
            subprocess.CalledProcessError(
                returncode=126,
                cmd=_BASE_COMMAND,
                output=b"",
                stderr=msg,
            ),
            MagicMock(returncode=0),  # second call succeeds
        ]

        run_build_command(
            build_command=list(_BASE_COMMAND),
            version="None",
            options=_make_options(),
        )

        assert mock_run.call_count == 2
        retry_cmd = mock_run.call_args_list[1][0][0]
        user_idx = retry_cmd.index("--user")
        assert retry_cmd[user_idx + 1] == _FIXED_USER_STR
        assert "/path/to/repo:/home/user/mounted_home:U" not in retry_cmd
        assert "/path/to/repo:/home/user/mounted_home" in retry_cmd

    @patch("doc_builder.build_docs.subprocess.run")
    def test_raises_on_other_error(self, mock_run, _mock_start):
        """On non-chown failure, should re-raise the error"""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=_BASE_COMMAND,
            output=b"",
            stderr=b"Error: something else went wrong",
        )

        with pytest.raises(subprocess.CalledProcessError):
            run_build_command(
                build_command=list(_BASE_COMMAND),
                version="None",
                options=_make_options(),
            )

    @patch("doc_builder.build_docs.subprocess.run")
    def test_succeeds_without_retry(self, mock_run, _mock_start):
        """On success, should not retry"""
        mock_run.return_value = None

        run_build_command(
            build_command=list(_BASE_COMMAND),
            version="None",
            options=_make_options(),
        )

        mock_run.assert_called_once()
