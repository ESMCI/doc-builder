#!/usr/bin/env python3
"""Tests of get_toplevel_git_dir

These are integration tests, since they interact with the OS and git,
and so are slower than typical unit tests.
"""

import tempfile
import shutil
import os

# pylint: disable=import-error,no-name-in-module,attribute-defined-outside-init
from test.test_utils.git_helpers import (
    make_git_repo,
    add_file,
)
from doc_builder.sys_utils import get_toplevel_git_dir


class TestGetToplevelGitDir:
    """Test the get_toplevel_git_dir function"""

    # ------------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------------

    def setup_method(self):
        """To run at the beginning of each test"""
        self._return_dir = os.getcwd()
        self._tempdir = os.path.realpath(tempfile.mkdtemp())
        os.chdir(self._tempdir)

    def teardown_method(self):
        """To run after each test"""
        os.chdir(self._return_dir)
        shutil.rmtree(self._tempdir, ignore_errors=True)

    # ------------------------------------------------------------------------
    # Begin tests
    # ------------------------------------------------------------------------

    def test_not_git_repo_file(self):
        """If file not in a git repository, should return None"""
        filename = add_file()
        assert get_toplevel_git_dir(filename) is None
        assert os.getcwd() == self._tempdir  # Should still be in original directory

    def test_not_git_repo_dir(self):
        """If dir not in a git repository, should return None"""
        dir_name = "some_dir"
        os.makedirs(dir_name)
        assert get_toplevel_git_dir(dir_name) is None
        assert os.getcwd() == self._tempdir  # Should still be in original directory

    def test_not_git_repo_file_in_subdir(self):
        """If subdir's file not in a git repository, should return None"""
        dir_name = "some_dir"
        os.makedirs(dir_name)
        filename = os.path.join(dir_name, "some_file")
        add_file(filename)
        assert get_toplevel_git_dir(filename) is None
        assert os.getcwd() == self._tempdir  # Should still be in original directory

    def test_in_git_repo_file(self):
        """If file is in a git repository, should return self._temp_dir"""
        make_git_repo()
        filename = add_file()
        assert get_toplevel_git_dir(filename) == self._tempdir
        assert os.getcwd() == self._tempdir  # Should still be in original directory

    def test_in_git_repo_dir(self):
        """If dir is in a git repository, should return self._temp_dir"""
        make_git_repo()
        dir_name = "some_dir"
        os.makedirs(dir_name)
        assert get_toplevel_git_dir(dir_name) == self._tempdir
        assert os.getcwd() == self._tempdir  # Should still be in original directory

    def test_in_git_repo_file_in_subdir(self):
        """If subdir's file is in a git repository, should return self._temp_dir"""
        make_git_repo()
        dir_name = "some_dir"
        os.makedirs(dir_name)
        filename = os.path.join(dir_name, "some_file")
        add_file(filename)
        assert get_toplevel_git_dir(filename) == self._tempdir
        assert os.getcwd() == self._tempdir  # Should still be in original directory

    def test_in_git_repo_file_in_subdir_from_subdir(self):
        """
        If subdir's file is in a git repository, should return self._temp_dir, even if called from
        subdir
        """
        make_git_repo()
        dir_name = "some_dir"
        os.makedirs(dir_name)
        os.chdir(dir_name)
        filename = "some_file"
        add_file(filename)
        assert get_toplevel_git_dir(filename) == self._tempdir
        expected = os.path.join(self._tempdir, dir_name)
        assert os.getcwd() == expected  # Should still be in original directory(
