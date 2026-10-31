# MCP Tool Contract: Read-Only Inspection

Transport: MCP over standard input/output. Successful results are structured JSON objects. Expected file and format failures use `ok: false` with diagnostics; malformed tool arguments remain MCP protocol/tool validation errors.

## `open_layout`

Opens a file for read-only inspection and replaces any current session only after the new result is safe to use. An unsuccessful open leaves the session unavailable.

### Input

```json
{ "path": "/absolute/path/to/layout.xtc" }
```

`path` is required and must resolve to a readable regular plain-text `.xtc` file.

Only declared native format version 12 is accepted. Every other format number returns `ok: false` with `unsupported_version`; missing, malformed, or conflicting version declarations return `malformed_record`. The application-version string and producer comment are informational and never independently reject a file.

### Successful result

```json
{
  "ok": true,
  "source": { "path": "/absolute/path/to/layout.xtc", "format": "xtrackcad-xtc-text" },
  "summary": { "track_count": 12, "turnout_count": 2 },
  "diagnostics": []
}
```

### Expected failure result

```json
{
  "ok": false,
  "diagnostics": [
    { "severity": "error", "code": "malformed_record", "message": "Cannot safely parse record at line 27.", "location": { "line": 27 } }
  ]
}
```

## `get_layout_info`

Returns the `LayoutSummary` for the current inspection session. It takes no input. The result contains `ok: true`, `source`, `summary`, and session diagnostics. Optional fields are explicitly null when unavailable, consistently across all tools. With no usable open layout, return `ok: false` with `no_open_layout`.

Both `open_layout` and `get_layout_info` expose `summary.format_version` as integer 12 and `summary.application_version` as separate source text. `summary.room_dimensions` is `{width, height, unit: "inch"}` or null. `summary.bounds` is `{min_x, min_y, max_x, max_y, unit: "inch"}` or null. Track bounds encompass all track centerlines, including curve extrema and transformed turnout segments; room dimensions and decorative geometry do not contribute. Incomplete or unknown track geometry and empty layouts yield null bounds with a `bounds_unavailable` diagnostic. An otherwise inspectable layout can still return `ok: true` when bounds are unavailable. Open results include all inspection diagnostics immediately.

## `list_tracks`

Returns the supported `TrackObject` entries from the current inspection session. It takes no input.

```json
{
  "ok": true,
  "tracks": [
    {
      "id": "source:42",
      "kind": "straight",
      "position": { "x": 3.5, "y": 7.0, "unit": "inch" },
      "orientation": { "value": 90, "unit": "degree", "clockwise": true },
      "endpoints": []
    }
  ],
  "diagnostics": []
}
```

The server returns only `straight`, `curve`, and `turnout` entries. Compound visual segments inside a supported turnout are part of that turnout rather than separate track entries. If a file contains other top-level records, the result includes a diagnostic; it must not silently imply the list is complete. Valid UTF-8 labels are returned verbatim.

## Stability and safety rules

- Tool and diagnostic codes are stable contract fields; message wording is not.
- No tool writes, renames, or changes permissions of a source layout.
- Numeric geometry always identifies its unit. Angles document their rotation convention.
- Result ordering follows stable source order.
- Every position, endpoint, radius, and length identifies inches; every orientation and sweep identifies degrees and its direction convention. Zero direction points along positive Y, increasing clockwise.
- Duplicate track IDs fail with `malformed_record`; dangling endpoint references produce `invalid_reference` diagnostics with source locations.
