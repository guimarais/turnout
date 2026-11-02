# Contributing

Turnout is a local Python MCP server. Keep changes focused on a concrete user
workflow and use the standard library or existing MCP dependency where possible.

## Setup and checks

Use Python 3.13+ and uv; CI uses the version in `.python-version`.
From the checkout root:

```sh
uv sync --locked
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m turnout
```

The final command runs the stdio server and waits for an MCP client. Installation
is editable and checkout-based: keep `data/`, `examples/`, and the checkout in
place. Standalone wheel distribution is outside the current scope.

## Changes and pull requests

- Work on a short-lived branch and open a focused PR with a descriptive title.
- Explain the behavior change and verification. Include a small regression test
  for changed geometry, parsing, validation, or protocol behavior.
- Run the full checks above before requesting merge. CI includes a real MCP client
  testing the package entry point from outside the checkout.
- Commit dependency changes in `pyproject.toml` and `uv.lock` together; use
  `uv lock` after intentional dependency edits. Do not hand-edit the lockfile.
- Keep catalogue/reference inputs under `data/catalogues/` and `examples/`.
  Keep regression layouts in `tests/fixtures/`. Do not commit generated `layouts/`,
  `previews/`, virtual environments, credentials, or local client configuration.
- Never overwrite an input layout. Preserve units, geometry tolerances, explicit
  connections, and honest reporting of unsupported XTrackCAD content.
- Changes to exported records or geometry need a representative fixture and an
  XTrackCAD open/save/reopen check. Record the version and result in the PR;
  Python tests alone cannot establish GUI compatibility.
- Update documentation when commands, paths, supported records, or tool behavior
  change. Split modules when a concrete change benefits from that boundary.

## Repository policy

See [repository rules](docs/REPOSITORY_RULES.md) for proposed GitHub settings and
optional next steps. Hosted settings require a separate configuration change;
committing the workflow and this guide does not enable branch protection.
