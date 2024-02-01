"""Hacth custom hook module."""
# pylint: disable=import-error,too-few-public-methods,wrong-import-position

import os
import sys

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

sys.path.append(os.path.dirname(__file__))


class CustomWheelHook(BuildHookInterface):
    """Custom wheel hook to set correct build data."""

    def initialize(self, _, build_data):
        """Will be called before creating the source archive."""

        build_data['infer_tag'] = True
        build_data['artifacts'] = [
            os.path.join('qrkey', 'ui', 'build'),
        ]
