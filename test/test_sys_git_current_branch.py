#!/usr/bin/env python3
"""Tests of git_current_branch

These are integration tests, since they interact with the OS and git,
and so are slower than typical unit tests.
"""

import tempfile
import shutil
import os

# pylint: disable=import-error,no-name-in-module,attribute-defined-outside-init
from test.test_utils.git_helpers import (
    make_git_repo,
    add_git_commit,
    checkout_git_branch,
    make_git_tag,
    checkout_git_ref,
)
from doc_builder.sys_utils import git_current_branch


class TestGitCurrentBranch():
    """Test the git_current_branch function"""

    # ------------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------------

    def setup_method(self):
        """To run at the beginning of each test"""
        self._return_dir = os.getcwd()
        self._tempdir = tempfile.mkdtemp()
        os.chdir(self._tempdir)

    def teardown_method(self):
        """To run after each test"""
        os.chdir(self._return_dir)
        shutil.rmtree(self._tempdir, ignore_errors=True)

    # ------------------------------------------------------------------------
    # Begin tests
    # ------------------------------------------------------------------------

    def test_not_git_repo(self):
        """If not a git repository, should return (False, '')"""
        branch_found, branch_name = git_current_branch()
        assert not branch_found
        assert "" == branch_name

    def test_on_branch(self):
        """If on a git branch, should return (True, branchname)"""
        make_git_repo()
        add_git_commit()
        checkout_git_branch("foo")
        branch_found, branch_name = git_current_branch()
        assert branch_found
        assert "foo" == branch_name

    def test_not_on_branch(self):
        """If in a git repository but not on a branch, should return (False, '')"""
        make_git_repo()
        add_git_commit()
        make_git_tag("mytag")
        checkout_git_ref("mytag")
        branch_found, branch_name = git_current_branch()
        assert not branch_found
        assert "" == branch_name
