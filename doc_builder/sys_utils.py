"""
Functions that wrap system calls, including calls to the OS, git, etc.
"""

import subprocess
import os


def check_permanent_file(filename):
    """
    Check a "permanent" file (one that we don't want to change between doc version builds)
    """

    # Ensure file exists
    if not os.path.exists(filename):
        raise FileNotFoundError(filename)

    # Error if file contains uncommitted changes
    cmd = f"git add . && git diff --quiet {filename} && git diff --cached --quiet {filename}"
    try:
        subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as exception:
        subprocess.check_output("git reset", shell=True)  # Unstage files staged by `git add`
        msg = f"Important file/submodule may contain uncommitted changes: '{filename}'"
        raise RuntimeError(msg) from exception


def get_git_head_or_branch():
    """
    Get the name of the current branch. If detached HEAD, get current commit SHA.
    """
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--short", "-q", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
    except subprocess.CalledProcessError:
        output = ""

    if not output:
        # Fallback to commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
        output = result.stdout.strip()

    return output


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
            branch_name = subprocess.check_output(cmd, stderr=devnull, universal_newlines=True)
        except subprocess.CalledProcessError:
            branch_found = False
            branch_name = ""
        else:
            branch_found = True
            branch_name = branch_name.strip()

    return branch_found, branch_name
