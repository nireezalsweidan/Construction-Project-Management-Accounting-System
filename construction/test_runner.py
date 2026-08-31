"""
Custom test runner so plain ``manage.py test`` (no extra flags) works.

Domain apps live under BASE_DIR/apps (see settings.py's sys.path insert)
and are imported by their short name (``users``, ``inventory``, ...) --
that's also the name Django's app registry knows them by, since
INSTALLED_APPS lists them that way. But ``apps/`` itself has an
``__init__.py`` (needed elsewhere -- see its own docstring), which makes
it a real importable package too. Left to its own defaults, unittest's
test discovery walks from the project root, treats ``apps/`` as a
package, and imports each app's tests.py as e.g. ``apps.users.tests``
-- a second, different module identity for the same file than
``users.tests``. Django's app registry only recognizes the latter, so
any model class touched via the ``apps.*`` import path raises
"doesn't declare an explicit app_label and isn't in an application in
INSTALLED_APPS".

Pinning ``top_level`` to BASE_DIR/apps makes discovery compute each
test module's dotted name relative to that directory instead -- i.e.
``users.tests``, matching the import path everything else already uses.
Equivalent to always running ``manage.py test --top-level-directory=apps
apps``, without requiring everyone to remember those flags.
"""
from pathlib import Path

from django.test.runner import DiscoverRunner


class AppsDirTestRunner(DiscoverRunner):
    def __init__(self, *args, **kwargs):
        if kwargs.get('top_level') is None:
            kwargs['top_level'] = str(Path(__file__).resolve().parent.parent / 'apps')
        super().__init__(*args, **kwargs)

    def build_suite(self, test_labels=None, **kwargs):
        # Mirror the top-level pin onto the default label too: with no
        # labels given, DiscoverRunner defaults to ["."] (the project
        # root) -- that's an invalid start_dir once top_level_dir is
        # pinned to BASE_DIR/apps (start_dir must be inside top_level_dir,
        # not its parent). Only substitute when the caller hasn't named
        # specific labels/dirs of their own.
        if not test_labels:
            test_labels = ['apps']
        return super().build_suite(test_labels=test_labels, **kwargs)
