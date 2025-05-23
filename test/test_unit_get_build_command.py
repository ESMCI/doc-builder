#!/usr/bin/env python3

"""Unit test driver for get_build_command function"""

import os
import unittest
from unittest.mock import patch
from doc_builder.build_commands import get_build_command  # pylint: disable=import-error

# Allow names that pylint doesn't like, because otherwise I find it hard
# to make readable unit test names
# pylint: disable=invalid-name

# pylint: disable=line-too-long


class TestGetBuildCommand(unittest.TestCase):
    """Test the get_build_command function"""

    def setUp(self):
        """Run this before each test"""

        # Get current user's UID and GID
        uid = os.getuid()
        gid = os.getgid()
        self.uid_gid = f"{uid}:{gid}"

    def test_basic(self):
        """Tests basic usage"""
        build_command = get_build_command(
            build_dir="/path/to/foo",
            run_from_dir="/irrelevant/path",
            build_target="html",
            num_make_jobs=4,
            docker_name=None,
            version="None",
        )
        expected = [
            "make",
            "SPHINXOPTS=-W --keep-going",
            "BUILDDIR=/path/to/foo",
            "-j",
            "4",
            "html",
        ]
        self.assertEqual(expected, build_command)

    def test_custom_conf_py_path(self):
        """Tests usage with --conf-py-path as file"""
        conf_py_path = os.path.join(os.path.dirname(__file__), "conf.py")
        build_command = get_build_command(
            build_dir="/path/to/foo",
            run_from_dir="/irrelevant/path",
            build_target="html",
            num_make_jobs=4,
            docker_name=None,
            version="None",
            conf_py_path=conf_py_path,
        )
        expected = [
            "make",
            f"SPHINXOPTS=-W --keep-going -c '{os.path.dirname(conf_py_path)}'",
            "BUILDDIR=/path/to/foo",
            "-j",
            "4",
            "html",
        ]
        self.assertEqual(expected, build_command)

    def test_custom_conf_py_path_dir(self):
        """Tests usage with --conf-py-path as directory"""
        conf_py_path = os.path.dirname(__file__)
        build_command = get_build_command(
            build_dir="/path/to/foo",
            run_from_dir="/irrelevant/path",
            build_target="html",
            num_make_jobs=4,
            docker_name=None,
            version="None",
            conf_py_path=conf_py_path,
        )
        expected = [
            "make",
            f"SPHINXOPTS=-W --keep-going -c '{conf_py_path}'",
            "BUILDDIR=/path/to/foo",
            "-j",
            "4",
            "html",
        ]
        self.assertEqual(expected, build_command)

    @patch("os.path.expanduser")
    def test_docker(self, mock_expanduser):
        """Tests usage with use_docker=True"""
        mock_expanduser.return_value = "/path/to/username"
        conf_py_path = os.path.join(os.path.dirname(__file__), "conf.py")
        build_command = get_build_command(
            build_dir="/path/to/username/foorepos/foodocs/versions/main",
            run_from_dir="/path/to/username/foorepos/foocode/doc",
            build_target="html",
            num_make_jobs=4,
            docker_name="foo",
            version="None",
            conf_py_path=conf_py_path,
            container_cli_tool="abc123",
        )
        expected = [
            "abc123",
            "run",
            "--name",
            "foo",
            "--user",
            self.uid_gid,
            "--mount",
            "type=bind,source=/path/to/username,target=/home/user/mounted_home",
            "--workdir",
            "/home/user/mounted_home/foorepos/foocode/doc",
            "-t",
            "--rm",
            "-e",
            "current_version=None",
            "ghcr.io/escomp/ctsm/ctsm-docs:v1.0.1",
            "make",
            f"SPHINXOPTS=-W --keep-going -c '{os.path.dirname(conf_py_path)}'",
            "BUILDDIR=/home/user/mounted_home/foorepos/foodocs/versions/main",
            "-j",
            "4",
            "html",
        ]
        print("build_command: +", " ".join(build_command))
        self.assertEqual(expected, build_command)

    @patch("os.path.expanduser")
    def test_docker_relpath(self, mock_expanduser):
        """Tests usage with use_docker=True, with a relative path to build_dir"""
        mock_expanduser.return_value = "/path/to/username"
        build_command = get_build_command(
            build_dir="../../foodocs/versions/main",
            run_from_dir="/path/to/username/foorepos/foocode/doc",
            build_target="html",
            num_make_jobs=4,
            docker_name="foo",
            version="None",
            container_cli_tool="abc123",
        )
        expected = [
            "abc123",
            "run",
            "--name",
            "foo",
            "--user",
            self.uid_gid,
            "--mount",
            "type=bind,source=/path/to/username,target=/home/user/mounted_home",
            "--workdir",
            "/home/user/mounted_home/foorepos/foocode/doc",
            "-t",
            "--rm",
            "-e",
            "current_version=None",
            "ghcr.io/escomp/ctsm/ctsm-docs:v1.0.1",
            "make",
            "SPHINXOPTS=-W --keep-going",
            "BUILDDIR=/home/user/mounted_home/foorepos/foodocs/versions/main",
            "-j",
            "4",
            "html",
        ]
        self.assertEqual(expected, build_command)

    @patch("os.path.expanduser")
    def test_docker_builddir_not_in_home(self, mock_expanduser):
        """If build_dir is not in the user's home directory, should raise an exception"""
        mock_expanduser.return_value = "/path/to/username"
        with self.assertRaisesRegex(
            RuntimeError, "build directory must reside under your home directory"
        ):
            _ = get_build_command(
                build_dir="/path/to/other/foorepos/foodocs/versions/main",
                run_from_dir="/path/to/username/foorepos/foocode/doc",
                build_target="html",
                num_make_jobs=4,
                docker_name="foo",
                version="None",
            )

    @patch("os.path.expanduser")
    def test_docker_runfromdir_not_in_home(self, mock_expanduser):
        """If run_from_dir is not in the user's home directory, should raise an exception"""
        mock_expanduser.return_value = "/path/to/username"
        with self.assertRaisesRegex(
            RuntimeError,
            "build_docs must be run from somewhere in your home directory",
        ):
            _ = get_build_command(
                build_dir="/path/to/username/foorepos/foodocs/versions/main",
                run_from_dir="/path/to/other/foorepos/foocode/doc",
                build_target="html",
                num_make_jobs=4,
                docker_name="foo",
                version="None",
            )


if __name__ == "__main__":
    unittest.main()
