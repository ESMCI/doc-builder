"""
Functions with the main logic needed to build the command to build the docs
"""

import os
import pathlib
from doc_builder import sys_utils

# The Docker image used to build documentation via Docker
DOCKER_IMAGE = "ctsm-docs-test09"

# The path in Docker's filesystem where the user's home directory is mounted
_DOCKER_HOME = "/home/user/mounted_home"

def get_build_dir(build_dir=None, repo_root=None, version=None):
    """Return a string giving the path to the build directory.

    If build_dir is specified, simply use that.

    Otherwise, repo_root must be given. If version is also given, then
    the build directory will be:
        os.path.join(repo_root, "versions", version).
    If version is not given, then determine version by getting the
    current git branch; then use the above path specification.

    Error-checking on directory existence:
    - If build_dir is given, then no error checking is done
    - Otherwise, we ensure that repo_root/versions exists
      - If version is not given, then we also ensure that
        repo_root/versions/version exists, for the determined version.
    """

    if build_dir is not None:
        if repo_root is not None:
            raise RuntimeError("Cannot specify both build-dir and repo-root")
        if version is not None:
            raise RuntimeError("Cannot specify both build-dir and version")
        return build_dir

    if repo_root is None:
        raise RuntimeError("Must specify either build-dir or repo-root")

    if version is None:
        version_explicit = False
        branch_found, version = sys_utils.git_current_branch()
        if not branch_found:
            raise RuntimeError("Problem determining version based on git branch; "
                               "set --version on the command line.")
    else:
        version_explicit = True

    build_dir_no_version = os.path.join(repo_root, "versions")
    if not os.path.isdir(build_dir_no_version):
        raise RuntimeError("Directory {} doesn't exist".format(build_dir_no_version))
    build_dir = os.path.join(build_dir_no_version, version)
    if not version_explicit:
        if not os.path.isdir(build_dir):
            message = """
Directory {build_dir} doesn't exist yet.
If this is where you really want to build the documentation, rerun adding the
command-line argument '--doc-version {version}'""".format(build_dir=build_dir,
                                                          version=version)
            raise RuntimeError(message)

    return build_dir

def get_build_command(build_dir, run_from_dir, build_target, num_make_jobs, docker_name=None,
                      warnings_as_warnings=False,
                      ):
    """Return a string giving the build command.

    Args:
    - build_dir: string giving path to directory in which we should build
        If this is a relative path, it is assumed to be relative to run_from_dir
    - run_from_dir: string giving absolute path from which the build_docs command was run
        This is needed when using Docker
    - build_target: string: target for the make command (e.g., "html")
    - num_make_jobs: int: number of parallel jobs
    - docker_name: string or None: if not None, uses a Docker container to do the build,
        with the given name
    """
    if docker_name is None:
        return _get_make_command(build_dir=build_dir,
                                 build_target=build_target,
                                 num_make_jobs=num_make_jobs,
                                 warnings_as_warnings=warnings_as_warnings,
                                 )

    # But if we're using Docker, we have more work to do to create the command....

    # Mount the user's home directory in the Docker image; this assumes that both
    # run_from_dir and build_dir reside somewhere under the user's home directory (we
    # check this assumption below).
    docker_mountpoint = os.path.expanduser('~')

    docker_workdir = _docker_path_from_local_path(
        local_path=run_from_dir,
        docker_mountpoint=docker_mountpoint,
        errmsg_if_not_under_mountpoint=
        "build_docs must be run from somewhere within your home directory")

    if os.path.isabs(build_dir):
        build_dir_abs = build_dir
    else:
        build_dir_abs = os.path.normpath(os.path.join(run_from_dir, build_dir))
    docker_build_dir = _docker_path_from_local_path(
        local_path=build_dir_abs,
        docker_mountpoint=docker_mountpoint,
        errmsg_if_not_under_mountpoint=
        "build directory must reside under your home directory")

    make_command = _get_make_command(build_dir=docker_build_dir,
                                     build_target=build_target,
                                     num_make_jobs=num_make_jobs,
                                     warnings_as_warnings=warnings_as_warnings,
                                     )

    docker_command = ["docker", "run",
                      "--name", docker_name,
                      "--mount", "type=bind,source={},target={}".format(
                          docker_mountpoint, _DOCKER_HOME),
                      "--workdir", docker_workdir,
                      "-t",  # "-t" is needed for colorful output
                      "--rm",
                      DOCKER_IMAGE] + make_command
    return docker_command

def _get_make_command(build_dir, build_target, num_make_jobs, warnings_as_warnings):
    """Return the make command to run (as a list)

    Args:
    - build_dir: string giving path to directory in which we should build
    - build_target: string: target for the make command (e.g., "html")
    - num_make_jobs: int: number of parallel jobs
    """
    builddir_arg = "BUILDDIR={}".format(build_dir)
    sphinxopts = "SPHINXOPTS="
    if not warnings_as_warnings:
        sphinxopts += "-W --keep-going"
    return ["make", sphinxopts, builddir_arg, "-j", str(num_make_jobs), build_target]

def _docker_path_from_local_path(local_path, docker_mountpoint, errmsg_if_not_under_mountpoint):
    """Given a path on the local file system, return the equivalent path in Docker space

    Args:
    - local_path: string: absolute path on local file system; this must reside under
        docker_mountpoint
    - docker_mountpoint: string: path on local file system that is mounted to _DOCKER_HOME
    - errmsg_if_not_under_mountpoint: string: message to print if local_path does not
        reside under docker_mountpoint
    """
    if not os.path.isabs(local_path):
        raise RuntimeError("Expect absolute path; got {}".format(local_path))

    local_pathobj = pathlib.Path(local_path)
    try:
        relpath = local_pathobj.relative_to(docker_mountpoint)
    except ValueError:
        raise RuntimeError(errmsg_if_not_under_mountpoint)

    # I think we need to do this conversion to a PosixPath for the sake of Windows
    # machines, where relpath is a Windows-style path, but we want Posix paths for
    # Docker. (But it may be that this is unnecessary.)
    relpath_posix = pathlib.PurePosixPath(relpath)

    # In the following, we deliberately hard-code "/" rather than using something like
    # os.path.join, because we need a path that works in Docker's file system, not the
    # native file system (in case the native file system is Windows).
    return _DOCKER_HOME + "/" + str(relpath_posix)
