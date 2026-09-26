# SPDX-License-Identifier: GPL-3.0-or-later
"""Prevent a nested event loop from starting the same operation twice."""

from functools import wraps


def single_run(function):
    """Prevent nested event loops from starting the same operation twice."""

    @wraps(function)
    def wrapped(self, *args, **kwargs):
        if getattr(self, "_operation_running", False):
            return

        self._operation_running = True

        try:
            # Qt's clicked(bool) signal may supply a checked-state argument.
            # Processing methods do not consume it.
            return function(self)
        finally:
            self._operation_running = False

    return wrapped
