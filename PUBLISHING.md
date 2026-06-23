# Publishing `pedra` to PyPI

The PyPI name `pedra` is available. The package builds with `hatchling`.

## One-time setup

1. Create a PyPI account and a project API token at https://pypi.org/manage/account/token/
   (scope it to the `pedra` project after the first upload, or use an account
   token for the very first upload).
2. Install the build/upload tools (ideally in a virtualenv):
   ```bash
   python -m pip install --upgrade build twine
   ```

## Test before publishing

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Build + upload

```bash
python -m build              # creates dist/pedra-<version>.tar.gz and .whl
twine check dist/*           # validates metadata + README rendering
twine upload dist/*          # prompts for token (use __token__ as username)
```

Tip: do a dry run against TestPyPI first:
```bash
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ pedra
```

## Releasing a new version

1. Bump `version` in `pyproject.toml` and `src/pedra/__init__.py` (`__version__`).
2. Update `CHANGELOG.md`.
3. `rm -rf dist && python -m build && twine upload dist/*`.
4. Tag the release: `git tag v<version> && git push --tags`.

## CI

`.github/workflows/ci.yml` runs the test suite on Python 3.8–3.12 for every push
and PR. Consider adding a publish job using PyPI Trusted Publishing (OIDC) gated
on tags.
