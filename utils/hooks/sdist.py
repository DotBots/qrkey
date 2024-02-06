"""Hacth custom hook module."""
# pylint: disable=import-error,too-few-public-methods,wrong-import-position

import os
import shlex
import subprocess
import sys

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

sys.path.append(os.path.dirname(__file__))


NPM_INSTALL_CMD = 'npm install --no-progress'
NPM_BUILD_CMD = 'npm run build'


def build_ui(root):
    """Builds the ReactJS UI."""
    ui_dir = os.path.join(root, 'qrkey', 'ui')
    os.makedirs(os.path.join(ui_dir, 'build'), exist_ok=True)
    print('Building React frontend application...')
    subprocess.run(shlex.split(NPM_INSTALL_CMD), cwd=ui_dir, check=True)
    subprocess.run(shlex.split(NPM_BUILD_CMD), cwd=ui_dir, check=True)


class CustomBuildHook(BuildHookInterface):
    """Custom build hook that will build the React web frontend."""

    def initialize(self, _, build_data):
        """Will be called before creating the source archive."""
        build_ui(self.root)
        build_data['artifacts'] = [
            os.path.join('qrkey', 'ui', 'build'),
        ]
