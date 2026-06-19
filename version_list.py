"""
Define the versions we want to build
"""
import sys
import os
# The doc_builder package may live in a "doc-builder" subdir (as in repos where doc-builder is a
# submodule) or directly alongside this file (as in the doc-builder repo itself). Add whichever
# exists to sys.path so "doc_builder" is importable either way.
dir2add = os.path.join(os.path.dirname(__file__), "doc-builder")
if not os.path.exists(dir2add):
    dir2add = os.path.dirname(__file__)
sys.path.insert(0, dir2add)
# pylint: disable=wrong-import-position,import-error
from doc_builder.docs_version import DocsVersion
from doc_builder.sys_utils import get_git_head_or_branch

# Branch name, tag, or commit SHA whose version of certain files we want to preserve
LATEST_REF = get_git_head_or_branch()

# List of version definitions
VERSION_LIST = [
    # Always keep this one! You can change short_name and display_name if you want.
    DocsVersion(
        short_name="latest",
        display_name="Latest development code",
        landing_version=True,
        ref=LATEST_REF,
    ),
    """
    This is provided as an example of an additional, frozen version of documentation. Here,
    ref="release-clm5.0" refers to the branch in the repo with the frozen docs. The short_name will
    show up in URL slugs and maybe elsewhere; it doesn't have to match the ref. display_name will
    be shown in the version picker drop-down.
    """
    # DocsVersion(
    #     short_name="release-clm5.0",
    #     display_name="CLM5.0",
    #     ref="release-clm5.0",
    # ),
]
# End version definitions (keep this comment; Sphinx is looking for it)
