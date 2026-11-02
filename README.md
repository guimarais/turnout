# turnout

A local Python MCP server that helps an AI build flat Märklin C-track layouts
for XTrackCAD. Python computes geometry; the AI chooses an ordered sequence of
catalogue pieces. The only direct dependency is the official Python MCP SDK.

See [roadmap](docs/ROADMAP.md) for the proposed feature plan and next milestone.

## Run and connect

Requires Python 3.13+ and `uv`.

```sh
uv sync --locked
uv run --locked python -m turnout
```

`uv sync` installs this checkout as an editable package. Keep the checkout and
its data directories in place; standalone wheel installation is not supported.
After pulling this reorganization, run `uv sync --locked` and re-register any MCP
client that previously launched the removed root script using the command below.

The server uses stdio, so the second command waits for an MCP client rather than
showing an interactive prompt. Diagnostics go to stderr.

Register this checkout with Codex (run from the repository root):

```sh
codex mcp add turnout -- "$PWD/.venv/bin/python" -m turnout
codex mcp get turnout
```

Restart the Codex client or open a new chat if the tools aren't visible. Moving
the checkout requires registering the new absolute paths. Alternatively, merge
this into your Codex MCP configuration, replacing the example Python path:

```toml
[mcp_servers.turnout]
command = "/absolute/path/to/turnout/.venv/bin/python"
args = ["-m", "turnout"]
```

See the [official Codex MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
The server does not call a model or require an API key.

## Repository structure

| Path | Purpose |
| --- | --- |
| `src/turnout/server.py` | Catalogue, geometry, layout inspection, and MCP tools |
| `tests/` | Automated unit and MCP protocol tests |
| `tests/fixtures/` | Committed regression layouts, including accepted ovals |
| `data/catalogues/` | Runtime track catalogue |
| `examples/` | Read-only example layouts |
| `docs/` | Feature roadmap and repository rules |
| `.github/` | CI, dependency updates, and contribution templates |
| `layouts/`, `previews/` | Local generated outputs, ignored by Git |

See [CONTRIBUTING.md](CONTRIBUTING.md) for development checks and
[repository rules](docs/REPOSITORY_RULES.md) for proposed GitHub protections and
further improvements. Hosted branch protection has to be configured separately.

## Tools

- `list_parts(query="")`: search supported catalogue pieces by part number or
  description; return lengths, radii, angles and endpoints in millimetres.
- `build_layout(parts, width_mm=2000, height_mm=1200)`: attach an ordered sequence,
  validate it, centre it on the board, and save a new `layouts/layout-*.xtc`.
  Returns the absolute path, parts quantities, footprint and closure measurements.
- `inspect_layout(path)`: read a saved `.xtc` and return metadata, pieces, parts
  quantities, endpoint references, verified connected components, connection issues,
  and a unique labelled SVG in `previews/`. The source file is never modified.

For example, ask Codex:

> Use turnout to inspect `examples/mrkln_sample.xtc`. Show the labelled preview,
> list its open endpoints, and explain any connection issues.

Paths may be absolute or relative to this checkout. References such as `4:2` mean
piece ID 4, endpoint 2 (zero-based order in the file); they identify this snapshot,
not a permanent ID across future XTrackCAD edits. All reported positions are mm;
angles follow XTrackCAD's clockwise-from-north convention.

Inspection reads embedded compound-track geometry, including all turnout segments,
without requiring the piece to be supported by the build tool's catalogue filter.
It currently supports the observed `VERSION 12 5.2.0` records. The preview shows
centrelines, board outline, piece/catalogue labels, orange explicit open ends and
red connection issues. Decorations, scenery and vehicle clearance are outside its
scope. Elevated or otherwise unsupported elements produce warnings.

Open ends are intentional file records, not automatically errors. Declared links
must have a unique reciprocal partner within 0.1 mm and 0.1° of opposing alignment.
Missing neighbours, nonreciprocal or ambiguous links, gaps and angle errors are
reported; nearby unconnected endpoints remain unconnected. Components use verified
links and do not describe routes available under particular turnout settings.

`status: complete` means the supported inspection was complete, not that the design
is valid. Check `connection_issues` separately. Unsupported elements produce
`status: incomplete`, warnings, and `topology_complete: false`; counts and previews
then cover only the supported subset. Unsupported format versions are not guessed
at, and unknown board dimensions are not drawn as a real board. Malformed supported
records return `ok: false` with an error and no preview. Inputs are limited to 5 MB.

After installing this feature, restart Codex to discover `inspect_layout`.

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

- Reads ordinary straights and curves from `data/catalogues/mrklnhoc-de.xtp`; unsupported
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

The sample `examples/mrkln_sample.xtc` is a format reference, not an input to edit.
The writer targets its `VERSION 12 5.2.0` format. See XTrackCAD's
[compound element format documentation](https://sourceforge.net/p/xtrkcad-fork/wiki/CompoundElements/).

## Checks and XTrackCAD acceptance

```sh
uv run --locked python -m unittest discover -s tests -v
```

The stdlib tests check catalogue filtering, dimensions, exported reciprocal
connections, preservation of prior outputs, failure cases, line/arc intersections,
read-only inspection of the unfinished sample and saved ovals, malformed and
unsupported records, broken/ambiguous connections, SVG label escaping,
and a real stdio MCP client calling all three tools. The protocol test needs normal
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
(`tests/fixtures/layout-w7r0lfkz.xtc` (originally `layouts/layout-w7r0lfkz.xtc`)) after the requested open/save verification.
`xtrackcad_verified: false` in new build results still means that each generated
file needs its own application check; Python does not perform GUI verification.

Layout inspection acceptance: the unfinished sample reports four pieces (including
turnout 24612), open endpoints `3:1`, `4:0`, `4:2`, and one component with no
connection issues. Generated and XTrackCAD-saved ovals report fourteen pieces,
zero open ends and one component. Both labelled previews have been visually checked.
