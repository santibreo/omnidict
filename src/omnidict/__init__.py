"""Defines package version dynamically"""

import sys
import subprocess
from packaging.version import Version


def _get_version_from_git_tags(default='v0.0.1-alpha'):
    cmd = subprocess.run(['git', 'tag'], capture_output=True)
    versions = sorted(map(Version, cmd.stdout.decode().splitlines()))
    if not versions:
        return default
    return str(versions[-1])


# If you do following line, function is called everytime package is imported
# but using class approach, only when accessing `__version__` function is called

#  __version__ = _get_version_from_git_tags()


class This(sys.__class__):

    @property
    def __version__(self) -> str:
        return _get_version_from_git_tags()


sys.modules[__name__].__class__ = This
