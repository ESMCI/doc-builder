#!/usr/bin/env python3

"""Unit test driver for _fix_command_for_missing_subids and the retry logic in run_build_command"""

import subprocess
import unittest
from argparse import Namespace
from unittest.mock import patch

# pylint: disable=import-error
from doc_builder.build_docs import _fix_command_for_missing_subids, run_build_command

# Allow names that pylint doesn't like, because otherwise I find it hard
# to make readable unit test names
# pylint: disable=invalid-name


class TestFixCommandForMissingSubids(unittest.TestCase):
    """Test the _fix_command_for_missing_subids function"""

    def test_removes_U_suffix_from_mount(self):
        """The :U suffix should be removed from volume mount arguments"""
        command = [
            "podman",
            "run",
            "--name",
            "foo",
            "--user",
            "37083:1000",
            "-v",
            "/path/to/repo:/home/user/mounted_home:U",
            "--workdir",
            "/home/user/mounted_home/doc",
            "-t",
            "--rm",
            "ghcr.io/escomp/ctsm/ctsm-docs:v1.0.1",
            "make",
            "html",
        ]
        result = _fix_command_for_missing_subids(command)
        self.assertIn("/path/to/repo:/home/user/mounted_home", result)
        self.assertNotIn("/path/to/repo:/home/user/mounted_home:U", result)

    def test_changes_user_to_root(self):
        """--user should be changed to 0:0"""
        command = [
            "podman",
            "run",
            "--name",
            "foo",
            "--user",
            "37083:1000",
            "-v",
            "/path/to/repo:/home/user/mounted_home:U",
            "ghcr.io/escomp/ctsm/ctsm-docs:v1.0.1",
            "make",
            "html",
        ]
        result = _fix_command_for_missing_subids(command)
        user_idx = result.index("--user")
        self.assertEqual(result[user_idx + 1], "0:0")

    def test_preserves_other_args(self):
        """Arguments that aren't --user or :U mounts should be unchanged"""
        command = [
            "podman",
            "run",
            "--name",
            "foo",
            "--user",
            "37083:1000",
            "-v",
            "/path/to/repo:/home/user/mounted_home:U",
            "--workdir",
            "/home/user/mounted_home/doc",
            "-t",
            "--rm",
            "-e",
            "current_version=None",
            "ghcr.io/escomp/ctsm/ctsm-docs:v1.0.1",
            "make",
            "html",
        ]
        result = _fix_command_for_missing_subids(command)
        expected = [
            "podman",
            "run",
            "--name",
            "foo",
            "--user",
            "0:0",
            "-v",
            "/path/to/repo:/home/user/mounted_home",
            "--workdir",
            "/home/user/mounted_home/doc",
            "-t",
            "--rm",
            "-e",
            "current_version=None",
            "ghcr.io/escomp/ctsm/ctsm-docs:v1.0.1",
            "make",
            "html",
        ]
        self.assertEqual(expected, result)

    def test_no_U_suffix_unchanged(self):
        """A command without :U mount should only change --user"""
        command = [
            "podman",
            "run",
            "--user",
            "37083:1000",
            "--mount",
            "type=bind,source=/path,target=/home/user/mounted_home",
            "image:latest",
            "make",
            "html",
        ]
        result = _fix_command_for_missing_subids(command)
        self.assertEqual(result[result.index("--user") + 1], "0:0")
        self.assertIn("type=bind,source=/path,target=/home/user/mounted_home", result)


def _make_options():
    """Create a minimal options Namespace for run_build_command"""
    return Namespace(
        version_display_name=None,
        static_path="_static",
        templates_path="_templates",
        versions=False,
        build_in_container=True,
    )


_BASE_COMMAND = [
    "podman",
    "run",
    "--name",
    "foo",
    "--user",
    "37083:1000",
    "-v",
    "/path/to/repo:/home/user/mounted_home:U",
    "--workdir",
    "/home/user/mounted_home/doc",
    "-t",
    "--rm",
    "ghcr.io/escomp/ctsm/ctsm-docs:v1.0.1",
    "make",
    "html",
]


@patch("doc_builder.build_docs.start_container_software")
class TestRunBuildCommandRetry(unittest.TestCase):
    """Test that run_build_command retries with fixed args on chown failure"""

    @patch("doc_builder.build_docs.subprocess.check_call")
    @patch("doc_builder.build_docs.subprocess.run")
    def test_retries_on_chown_error(self, mock_run, mock_check_call, _mock_start):
        """On chown failure, should retry with :U removed and --user 0:0"""
        msg = b"Error: failed to chown recursively host path: lchown /some/path: invalid argument"
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=126,
            cmd=_BASE_COMMAND,
            output=b"",
            stderr=msg,
        )
        mock_check_call.return_value = 0

        run_build_command(
            build_command=list(_BASE_COMMAND),
            version="None",
            options=_make_options(),
        )

        mock_check_call.assert_called_once()
        retry_cmd = mock_check_call.call_args[0][0]
        user_idx = retry_cmd.index("--user")
        self.assertEqual(retry_cmd[user_idx + 1], "0:0")
        self.assertNotIn("/path/to/repo:/home/user/mounted_home:U", retry_cmd)
        self.assertIn("/path/to/repo:/home/user/mounted_home", retry_cmd)

    @patch("doc_builder.build_docs.subprocess.run")
    def test_raises_on_other_error(self, mock_run, _mock_start):
        """On non-chown failure, should re-raise the error"""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=_BASE_COMMAND,
            output=b"",
            stderr=b"Error: something else went wrong",
        )

        with self.assertRaises(subprocess.CalledProcessError):
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


if __name__ == "__main__":
    unittest.main()
