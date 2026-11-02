# turnout

A local Python MCP server that helps an AI build flat Märklin C-track layouts
for XTrackCAD. Python computes geometry; the AI chooses an ordered sequence of
catalogue pieces. The only direct dependency is the official Python MCP SDK.

## Run and connect

Requires Python 3.13+ and `uv`.

```sh
uv sync --locked
uv run --locked main.py
```

The server uses stdio, so the second command waits for an MCP client rather than
showing an interactive prompt. Diagnostics go to stderr.

Register this checkout with Codex (run from the repository root):

```sh
codex mcp add turnout -- "$PWD/.venv/bin/python" "$PWD/main.py"
codex mcp get turnout
```

Restart the Codex client or open a new chat if the tools aren't visible. Moving
the checkout requires registering the new absolute paths. Alternatively, merge
this into your Codex MCP configuration, replacing both example paths:

```toml
[mcp_servers.turnout]
command = "/absolute/path/to/turnout/.venv/bin/python"
args = ["/absolute/path/to/turnout/main.py"]
```

See the [official Codex MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
The server does not call a model or require an API key.

## Tools

- `list_parts(query="")`: search supported catalogue pieces by part number or
  description; return lengths, radii, angles and endpoints in millimetres.
- `build_layout(parts, width_mm=2000, height_mm=1200)`: attach an ordered sequence,
  validate it, centre it on the board, and save a new `layouts/layout-*.xtc`.
  Returns the absolute path, parts quantities, footprint and closure measurements.

Example prompt for Codex:

> Use turnout to make a closed oval on a 2000 × 1200 mm board, using twelve
> Märklin 24130 curves and two 24188 straights. Put six curves, one straight,
> six curves, then the other straight. Return the file path and parts list.

The equivalent build arguments are:

```json
{
  "parts": ["24130", "24130", "24130", "24130", "24130", "24130", "24188",
            "24130", "24130", "24130", "24130", "24130", "24130", "24188"],
  "width_mm": 2000,
  "height_mm": 1200
}
```

That oval uses 14 pieces and has a centreline footprint of approximately
908.3 × 720 mm. The file embeds the catalogue geometry and reciprocal endpoint
connections, with conversion to inches only at export.

## Validation and current scope

- Reads ordinary straights and curves from `files/mrklnhoc-de.xtp`; unsupported
  part numbers, including turnouts and special tracks, are rejected.
- Traverses every piece from catalogue endpoint 0 to endpoint 1. Curves turn
  left; reversed traversal and mirrored pieces are not implemented.
- Requires a closed loop within 0.1 mm and 0.1°, allowing catalogue rounding.
  Pieces keep their catalogue dimensions; gaps are not filled by stretching.
- Checks full straight/arc centreline bounds, including arc extrema, with a
  fixed 50 mm board-edge margin. The layout is centred without trying alternative
  orientations. Width and height must be finite, greater than 100 mm, and at most
  100,000 mm.
- Rejects centreline crossings and overlaps, permitting only the intended
  adjacent connections within the positional tolerance. This is not a vehicle
  clearance or roadbed collision simulation.
- Accepts 3–500 pieces. Pairwise intersection checks are quadratic; no search
  engine or layout optimiser is included.
- Invalid designs return `ok: false` and errors identifying closure measurements,
  boundary excess, unsupported pieces, or intersecting piece indices (one-based).
  They create no layout file. Successful builds use unique filenames and never
  replace earlier layouts or the supplied sample.

The sample `files/mrkln_sample.xtc` is a format reference, not an input to edit.
The writer targets its `VERSION 12 5.2.0` format. See XTrackCAD's
[compound element format documentation](https://sourceforge.net/p/xtrkcad-fork/wiki/CompoundElements/).

## Checks and XTrackCAD acceptance

```sh
uv run --locked python -m unittest -v
```

The stdlib tests check catalogue filtering, dimensions, exported reciprocal
connections, preservation of prior outputs, failure cases, line/arc intersections,
and a real stdio MCP client calling both tools. The protocol test needs normal
local subprocess/thread I/O; restrictive agent sandboxes can block that I/O.

For the manual compatibility check, open the returned path:

```sh
xtrkcad /absolute/path/from/build_layout.xtc
```

Confirm that XTrackCAD loads without errors, the oval appears continuous, and
all 14 pieces have both ends connected. Save As a separate file, close it, and
reopen the saved copy. Check that the pieces and connections remain intact.

**Status:** first milestone accepted on 2026-11-02. Automated geometry and MCP
checks pass, and the user confirmed the generated test oval works in XTrackCAD
(`layouts/layout-w7r0lfkz.xtc`) after the requested open/save verification.
`xtrackcad_verified: false` in new build results still means that each generated
file needs its own application check; Python does not perform GUI verification.
