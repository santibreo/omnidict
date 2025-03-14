"""Defines package version dynamically"""

import re
import sys
import subprocess
from pathlib import Path
from packaging.version import Version


_PATTERN = re.compile(r"(def _get_version_from_git_tags\(default: str = )'.*'(\):)")


def _get_version_from_git_tags(default: str = '1.0.0a4'):

    def set_version_as_default(version: str):
        content = Path(__file__).read_text()
        new_content = re.sub(_PATTERN, r'\1' + f"{version!r}" + r'\2', content)
        Path(__file__).write_text(new_content)

    cmd = subprocess.run(['git', 'tag'], capture_output=True)
    versions = sorted(map(Version, cmd.stdout.decode().splitlines()))
    if not versions:
        if not default:
            raise SystemError('Cannot resolve package version')
        return default
    set_version_as_default(version := str(versions[-1]))
    return version


# If you do following line, function is called everytime package is imported
# but using class approach, only when accessing `__version__` function is called

#  __version__ = _get_version_from_git_tags()


class This(sys.__class__):

    @property
    def __version__(self) -> str:
        return _get_version_from_git_tags()


sys.modules[__name__].__class__ = This
