"""Defines package version dynamically"""

import sys
import subprocess


def _get_version_from_git_tags(default='v0.0.1-alpha'):
    cmd = subprocess.run(['git', 'tag'], capture_output=True)
    try:
        return next(map(str.strip, cmd.stdout.decode().splitlines()), default)
    except StopIteration:
        return default


# If you do following line, function is called everytime package is imported
# but using class approach, only when accessing `__version__` function is called

#  __version__ = _get_version_from_git_tags()


class This(sys.__class__):

    @property
    def __version__(self) -> str:
        return _get_version_from_git_tags()


sys.modules[__name__].__class__ = This
