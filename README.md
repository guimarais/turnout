# Turnout

Turnout is a read-only [Model Context Protocol](https://modelcontextprotocol.io/) server for inspecting XTrackCAD layout files.

## Requirements

- Rust stable (install with [rustup](https://rustup.rs/)).
- A plain-text XTrackCAD `.xtc` layout file.

## Build and run

Build the server from the repository root:

```sh
cargo build --release
```

MCP clients launch Turnout as a subprocess using STDIO. For example, a generic client configuration is:

```json
{
  "mcpServers": {
    "turnout": {
      "command": "/absolute/path/to/turnout/target/release/turnout",
      "args": []
    }
  }
}
```

Replace the command with the absolute path to the built executable. Turnout does not take a layout path at startup; call its `open_layout` tool with the path to the `.xtc` file.

## Available tools

- `open_layout`: open a plain-text `.xtc` file for read-only inspection.
- `get_layout_info`: return the summary for the currently open layout.
- `list_tracks`: list supported track objects and their available endpoints.

The initial compatibility fixture is [`layouts/mrkln_sample.xtc`](layouts/mrkln_sample.xtc). Format-12 straight, circular-curve, and compound turnout records are supported, including connected/open endpoints and UTF-8 catalogue labels. Turnout S/C track segments contribute to geometry; known decorative segments do not. Unsupported features are reported in diagnostics.

Call `open_layout` with an absolute path, for example `{"path":"/absolute/path/to/turnout/layouts/mrkln_sample.xtc"}`. Then call `get_layout_info` or `list_tracks` with no arguments. Responses include structured JSON content plus equivalent JSON text for client compatibility. Expected file failures return `ok: false` and diagnostics; a failed open clears the prior session.

The summary separates the numeric layout format version from the producing application's version string. Only format **12** is accepted. Other format numbers return `unsupported_version`; missing or malformed declarations return `malformed_record`. A newer application version alone does not cause rejection.

Room dimensions are reported separately from track centerline bounds. Coordinates and lengths identify inches; directions identify degrees, clockwise from positive Y. Bounds include curve extrema and transformed turnout segments. If any track geometry cannot be interpreted, an unknown object might be track, or there are no tracks, `bounds` is null with `bounds_unavailable`. Partial extents are never presented as complete. Optional unavailable fields are explicitly null.

## Tests

Run the complete suite with:

```sh
cargo test
```

The suite covers parser failures and compatibility rules, analytical bounds, UTF-8 data, endpoint references, source byte/mtime preservation, tool discovery, invalid requests, session clearing, and real executable STDIO calls. Process tests use absolute fixture paths, run from outside the repository, and enforce request/shutdown timeouts and child cleanup.

Run `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, and `cargo test --locked` for the required validation. Rust uses the rolling stable channel; record `rustc --version` and `cargo --version` when reporting results. Cargo needs network access for uncached dependencies.

## Limitations

- Input is read-only; Turnout does not modify or save layouts.
- Plain-text `.xtc` is the supported format; `.xtce` archives are not supported.
- The first tested producer is XTrackCAD 5.3.1GA using native format 12. Coverage is constrained to fixture-proven record shapes; advanced geometry such as Bezier tracks remains unsupported.
- Helix total length and traversal sweep are unsupported and return null with `unsupported_geometry`. XY bounds are returned only when at least one full turn establishes the complete circle; fractional-turn helix bounds are unavailable.
- The first supported runtime platform is Linux; Windows/macOS release certification is deferred.
- MCP clients connect over STDIO.
- External `.xtp` parameter-library lookup is not implemented. The [catalogue retrieval requirements](docs/track-parameter-catalog.md) describe the planned MCP capability for finding available track-system parts after loading a layout.
