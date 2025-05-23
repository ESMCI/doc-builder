#!/usr/bin/env python3

"""Unit test driver for command-line arg parsing"""

import unittest

import os
from doc_builder.build_docs import is_web_url, commandline_options  # pylint: disable=import-error


class TestCmdlineArgs(unittest.TestCase):
    """Test the command-line arguments and parsing"""

    # Allow long method names
    # pylint: disable=invalid-name

    def setUp(self):
        """Run this before each test"""
        self.fake_builddir = ["-b", "abc"]
        self.fake_abspath = os.path.sep + os.path.join("some", "abs", "path")
        self.fake_relpath = os.path.join(os.pardir, "some", "rel", "path")
        self.fake_url = "https://www.google.com"

    def test_is_web_url(self):
        """Ensure that all these are valid web URLs, even if they don't exist"""
        urls = [
            "https://www.google.com",
            "http://example.com",
            "ftp://fileserver.com",
            "https://www.google.com/path/to/resource?query=string#fragment",
            "https://user:password@www.example.com:8080/path/to/resource?query=string#fragment",
        ]
        for url in urls:
            print(url)
            self.assertTrue(is_web_url(url))

    def test_isnt_web_url(self):
        """Ensure that all these are NOT valid web URLs"""
        urls = [
            "www.example.com",
            "invalid url",
            self.fake_abspath,
            self.fake_relpath,
        ]

        for url in urls:
            print(url)
            self.assertFalse(is_web_url(url))

    def test_no_versions_no_siteroot(self):
        """Ensure no error when you don't provide --versions or --siteroot"""
        commandline_options(self.fake_builddir)

    def test_versions_and_siteroot_abs(self):
        """Ensure no error when you provide --versions and an absolute path for --site-root"""
        commandline_options(self.fake_builddir + ["--versions", "--site-root", self.fake_abspath])

    def test_versions_and_siteroot_url(self):
        """Ensure no error when you provide --versions and a URL for --site-root"""
        commandline_options(self.fake_builddir + ["--versions", "--site-root", self.fake_url])

    def test_versions_and_siteroot_rel_error(self):
        """Ensure error when you provide --versions and a valid relative path for --site-root"""
        msg = "--site-root is neither a web URL nor an absolute path"
        with self.assertRaisesRegex(RuntimeError, msg):
            commandline_options(
                self.fake_builddir + ["--versions", "--site-root", self.fake_relpath]
            )

    def test_versions_and_siteroot_neither_error(self):
        """Ensure error when you provide --versions and just some string for --site-root"""
        msg = "--site-root is neither a web URL nor an absolute path"
        with self.assertRaisesRegex(RuntimeError, msg):
            commandline_options(self.fake_builddir + ["--versions", "--site-root", "abc123"])

    def test_versions_but_no_siteroot_error(self):
        """Ensure error when you provide --versions but not --site-root"""
        msg = "--site-root must be provided when --versions is enabled"
        with self.assertRaisesRegex(RuntimeError, msg):
            commandline_options(self.fake_builddir + ["--versions"])


if __name__ == "__main__":
    unittest.main()
