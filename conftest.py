# Empty on purpose. Its presence at the repo root is what makes pytest treat
# this directory as importable (so `from main import app` in tests/ resolves)
# when pytest is invoked directly -- e.g. `pytest tests/`, which is what CI
# actually runs. Without this, tests only pass locally via `python -m pytest`
# (which adds the cwd to sys.path itself) and fail in CI with
# `ModuleNotFoundError: No module named 'main'`. Found by testing both
# invocation styles, not assumed.
