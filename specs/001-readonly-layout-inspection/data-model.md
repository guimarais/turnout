# Data Model: Read-Only Layout Inspection

All types are application-owned; native XTrackCAD parse records are mapped into these types before MCP tools return them.

## LayoutSource

| Field | Description | Rules |
|---|---|---|
| `path` | Client-supplied filesystem path | Must name a readable regular `.xtc` file. |
| `format` | Detected layout format | Initial value: `xtrackcad-xtc-text`. |
| `fingerprint` | Read-time source identity | Capture a testable fingerprint; never modify the file. |

## InspectionSession

| Field | Description | Rules |
|---|---|---|
| `source` | Selected source | Required after a successful open. |
| `layout` | Parsed application layout | Required after a successful open. |
| `diagnostics` | Warnings from opening | May be empty. |

State transitions: `Empty` → `Opening` → `Open` on a usable result; `Empty` → `Failed` on a failed open. A failed attempt clears any earlier `Open` state. `get_layout_info` and `list_tracks` require `Open`.

## LayoutSummary

| Field | Description | Rules |
|---|---|---|
| `titles` | Declared layout title lines | Preserve each valid UTF-8 title verbatim and in source order; absence is explicit. |
| `format_version` | Native layout format number | Required validated integer 12; never inferred from an application version. |
| `application_version` | Application version in the VERSION record | Required source text; informational, independent of format acceptance. |
| `scale` | Declared model-scale/map-scale data | Optional; distinguish scale from gauge. |
| `room_dimensions` | Declared width and height | Object with `width`, `height`, and `unit: inch`, or null when unavailable. Values must be finite and positive. |
| `bounds` | Complete track centerline extent | Bounds object only if all track geometry is understood; otherwise null with `bounds_unavailable`. |
| `track_count` | Supported returned track count | Equals `tracks.len()`. |
| `turnout_count` | Supported turnout count | Equals count of `Turnout` entries. |

## Bounds and coordinate values

`Bounds` contains finite `min_x`, `min_y`, `max_x`, and `max_y` values plus `unit: inch`. Minima must not exceed maxima. These are track centerline extents, independent of room dimensions and decorative segments. Include curve extrema and transformed compound turnout track segments, not just endpoints. No tracks, unknown potentially-track objects, or incomplete geometry require null bounds and a diagnostic. Unsupported decorative objects known not to be tracks do not invalidate track bounds. No partial bounds are published.

## TrackObject

| Field | Description | Rules |
|---|---|---|
| `id` | Stable source-derived identity | Unique per session; never array-index derived. |
| `kind` | `straight`, `curve`, or `turnout` | Only these types are supported. |
| `position` | Anchor coordinate, when available | Explicit unit. |
| `orientation` | Angular direction, when available | Preserve native clockwise convention; contract declares it. |
| `endpoints` | Referenced connection ends | Preserve whether each end connects to another track or is open; unresolved references create diagnostics. |

Kind-specific data: a straight may include length; a curve may include radius and sweep; a turnout includes its source identity, UTF-8 library/catalogue label when present, and endpoint data. A turnout's internal visual segments are safely traversed to its segment terminator but are not exposed as separate `TrackObject` entries in this milestone. Fields cannot be populated from guesses.

Position and endpoint coordinates use `{x, y, unit: inch}`; orientation uses `{value, unit: degree, clockwise: true}` with zero pointing along positive Y. A curve stores its center, signed radius in inches, and enough start/sweep information to determine its actual arc. Turnouts retain interpreted S/C centerline segments with their source transform for complete bounds; decorative L/A segments do not contribute. Unknown track segments make bounds unavailable. Duplicate IDs fail opening; unresolved endpoint references emit `invalid_reference` with the source location.

All optional result fields use explicit null rather than omission. Geometry values are finite; unsupported or unavailable geometry is never represented by a fabricated zero.

## Diagnostic

| Field | Description | Rules |
|---|---|---|
| `severity` | `warning` or `error` | Errors prevent a usable open. |
| `code` | Stable machine-readable category | E.g. `unreadable_path`, `malformed_record`, `unsupported_record`, `unavailable_value`, `invalid_reference`. |
| `message` | Human-readable explanation | Identifies the affected path, record, or field where safe. |
| `location` | Optional source line/record reference | Present when available. |

An unsupported record is only a warning if the remaining supported data is demonstrably safe to inspect; otherwise it is an error.
