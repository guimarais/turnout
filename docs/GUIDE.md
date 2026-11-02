# Turnout guide

[← Project introduction and quick start](../README.md)

Tool arguments, connection options, file semantics, geometry limits and
XTrackCAD compatibility checks for the current release.

- [Connection options](#installation-and-connection-options)
- [Repository structure](#repository-structure)
- [Tools and inspection](#tools)
- [Extend an existing layout](#extend-an-existing-layout)
- [Generate a closed oval](#generate-a-closed-oval)
- [Closed-loop builder scope](#closed-loop-builder-scope)
- [Checks and XTrackCAD acceptance](#checks-and-xtrackcad-acceptance)

## Installation and connection options

Run shell commands from the repository root. Requires Python 3.13+ and `uv`.

```sh
uv sync --locked
uv run --locked python -m turnout
```

`uv sync` installs this checkout as an editable package. Keep the checkout and
its data directories in place; standalone wheel installation is not supported.

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

Paths below are relative to the repository root.

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

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development checks and
[repository rules](REPOSITORY_RULES.md) for proposed GitHub protections and
further improvements. Hosted branch protection has to be configured separately.

## Tools

- `list_parts(query="", catalogue="mrklnhoc-de.xtp")`: search every track piece in
  the selected parameter file; return geometry summaries, paths and indexed
  endpoints in millimetres. Compound lengths sum rail segments, not usable routes.
- `build_layout(parts, width_mm=2000, height_mm=1200)`: attach an ordered sequence,
  validate it, centre it on the board, and save a new `layouts/layout-*.xtc`.
  Returns the absolute path, parts quantities, footprint and closure measurements.
- `inspect_layout(path)`: read a saved `.xtc` and return metadata, pieces, parts
  quantities, endpoint references, verified connected components, connection issues,
  and a unique labelled SVG in `previews/`. The source file is never modified.
- `attach_track(path, endpoint, part_number, entry_endpoint=0, catalogue="")`:
  attach one piece at an explicitly open endpoint and save a separate revision
  with a labelled SVG, parts delta and resulting endpoint references.

### Inspect a layout

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

## Extend an existing layout

The layout must use one track system. Inspection reports `track_system` by matching
all existing pieces against `.xtp` files directly inside `data/catalogues/`.
Matching checks embedded track geometry, endpoints, paths, title and scale, rather
than relying on part numbers alone. A missing or ambiguous match returns
`selection_required`; choose a catalogue by filename explicitly. Selection never
bypasses compatibility checks. No directory setting or cached layout state is used.

The bundled catalogue supports all 43 pieces: ordinary and curved turnouts,
three-way and double-slip turnouts, crossings, buffer ends, contact/switch tracks,
transition tracks and other special pieces. `list_parts` returns their indexed
endpoints. A transition piece listed in this catalogue is eligible; subsequent
pieces must still belong to the same catalogue.

For example:

```json
{
  "path": "examples/mrkln_sample.xtc",
  "endpoint": "4:2",
  "part_number": "24188",
  "entry_endpoint": 0
}
```

Call `attach_track` with these arguments, then use its returned revision path and
new endpoint `5:1` to attach another piece or a `24978` buffer stop. Selecting a
curve's other entry endpoint reverses its traversal. Turnouts and crossings leave
all other endpoints open; buffer stops have no remaining endpoint. Connections
are physical links, not a claim about routes under turnout settings.

Attachment requires complete inspection and consistent connections. It rejects
unknown records, altered catalogue geometry, nonmatching scales, invalid or
already connected endpoints, board overflow and newly introduced centreline
crossings/overlaps. Intentional intersections inside catalogue pieces are allowed.
Board checks use the centreline and a 0.1 mm tolerance, with no extra edge margin.
Existing track stays in place; existing geometric problems away from the addition
are not revalidated. Roadbed and vehicle clearance are not checked.

Only the chosen open-end record changes; new piece records are inserted before
`END$TRACKS`. Untouched bytes, comments, line endings and the UTF-8 BOM are
preserved. New pieces inherit the target piece's layer. Outputs are unique
`layouts/revision-*.xtc` files; the source is never overwritten. Inputs and revisions
are limited to 5 MB and attachment to 500 total pieces. Batch attachment,
removal/replacement and automatic gap filling remain deferred.

Catalogue support covers the bundled record forms: `S`/`C` rails, `P` paths
(including zero-separated routes), `E` endpoints, `L`/`A`/`F`/`G` artwork and the
optional double-slip flag. Artwork is exported in its 3D record form with zero
heights and preserved, while SVG previews continue to show rail centrelines.
Other `.xtp` files can be added under `data/catalogues/`; unsupported record forms
are reported and prevent editing rather than being silently discarded.

Restart Codex to discover `attach_track` and the updated `list_parts` schema.

## Generate a closed oval

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

## Closed-loop builder scope

- Reads ordinary straights and curves from `data/catalogues/mrklnhoc-de.xtp`; unsupported
  part numbers, including turnouts and special tracks, are rejected by `build_layout`.
  They are available through `list_parts` and `attach_track`.
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

The sample `examples/mrkln_sample.xtc` is a read-only format reference; attachment
uses it as a source and writes a separate revision.
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
catalogue-wide attachment through every entry endpoint, byte preservation,
system selection, repeated extension and rejection cases,
and a real stdio MCP client calling all four tools. The protocol test needs normal
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

Connected extension automated checks pass, including all 43 pieces at every entry
endpoint. GUI compatibility for this feature is **pending**. The representative
`tests/fixtures/connected-track-families.xtc` has 22 pieces in 11 independent pairs,
covering curves, compound geometry, crossings, double-slip, buffer artwork and
special tracks. Open it in XTrackCAD 5.3.1GA, confirm the intended connections,
Save As a separate file, close/reopen it, then inspect the saved copy. Expect
22 pieces, 11 components, no connection issues and a matched track system.
Also extend the sample using the example above, repeat with a buffer, and verify
that both separate revisions retain the original four pieces and their positions.
Do not run another XTrackCAD instance against a shared recovery directory while
an existing instance has unsaved work. `xtrackcad_verified` remains false.

The record conversions follow the upstream
[parameter format](https://sourceforge.net/p/xtrkcad-fork/wiki/ParameterFileInformation/)
and [compound format](https://sourceforge.net/p/xtrkcad-fork/wiki/CompoundElements/),
with matching polygon/circle records in the installed XTrackCAD examples.
