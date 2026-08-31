"""
Namespace package marker for the ``apps`` directory.

All domain-specific Django apps (inventory, taxes, suppliers, projects, ...)
live under this directory rather than at the project root. This file makes
``apps`` importable as a regular Python package so that ``construction/settings.py``
can add it to ``sys.path`` and register each sub-app in INSTALLED_APPS using its
short name (e.g. ``"inventory"``) instead of a verbose dotted path.
"""
