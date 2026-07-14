"""
Test package for ``podcast_helper``.

Marks ``tests/`` as an importable package so pytest can resolve
intra-suite imports and shared fixtures the same way in every runner
(local, tox, CI). Contains no test logic itself — the actual tests live
in the sibling ``test_*.py`` modules, and shared fixtures (when needed)
belong in ``tests/conftest.py``.

Author
------
Project maintainers.
"""
