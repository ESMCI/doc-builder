#!/usr/bin/env python3

"""Wrapper around doc_builder/check_image_published.

Checks whether the container image that build_docs pulls by default has been published, and tells
a GitHub Actions workflow whether to build the docs. Run with --help for details.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

# pylint: disable=import-error,wrong-import-position
from doc_builder import check_image_published

if __name__ == "__main__":
    sys.exit(check_image_published.main())
