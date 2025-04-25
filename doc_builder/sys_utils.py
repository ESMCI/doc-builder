"""
Functions that wrap system calls, including calls to the OS, git, etc.
"""

import subprocess
import os


def git_current_branch():
    """Determines the name of the current git branch

    Returns a tuple, (branch_found, branch_name), where branch_found is
    a logical specifying whether a branch name was found for HEAD. (If
    branch_found is False, then branch_name is ''.) (branch_found will
    also be false if we're not in a git repository.)
    """
    cmd = ["git", "symbolic-ref", "--short", "-q", "HEAD"]
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        try:
            # Suppress stderr because we don't want to clutter output with
            # git's message, e.g., if we're not in a git repository.
            branch_name = subprocess.check_output(
                cmd, stderr=devnull, universal_newlines=True
            )
        except subprocess.CalledProcessError:
            branch_found = False
            branch_name = ""
        else:
            branch_found = True
            branch_name = branch_name.strip()

    return branch_found, branch_name
