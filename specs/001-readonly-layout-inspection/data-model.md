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
| `title` | Declared layout title | Optional; absence is explicit. |
| `format_version` | Declared source version | Optional; never inferred. |
| `scale` | Declared model-scale/map-scale data | Optional; distinguish scale from gauge. |
| `bounds` | Overall layout extent | Optional; only present when safely determined. |
| `track_count` | Supported returned track count | Equals `tracks.len()`. |
| `turnout_count` | Supported turnout count | Equals count of `Turnout` entries. |

## Bounds and coordinate values

`Bounds` contains `min_x`, `min_y`, `max_x`, and `max_y`; every value carries an explicit unit. The initial adapter preserves documented XTrackCAD inch values. Missing, non-finite, or inverted values do not become bounds and create a diagnostic.

## TrackObject

| Field | Description | Rules |
|---|---|---|
| `id` | Stable source-derived identity | Unique per session; never array-index derived. |
| `kind` | `straight`, `curve`, or `turnout` | Only these types are supported. |
| `position` | Anchor coordinate, when available | Explicit unit. |
| `orientation` | Angular direction, when available | Preserve native clockwise convention; contract declares it. |
| `endpoints` | Referenced connection ends | Unresolved references create diagnostics. |

Kind-specific data: a straight may include length; a curve may include radius and sweep; a turnout may include library/catalogue identity and endpoint data where the source exposes it. Fields cannot be populated from guesses.

## Diagnostic

| Field | Description | Rules |
|---|---|---|
| `severity` | `warning` or `error` | Errors prevent a usable open. |
| `code` | Stable machine-readable category | E.g. `unreadable_path`, `malformed_record`, `unsupported_record`, `unavailable_value`, `invalid_reference`. |
| `message` | Human-readable explanation | Identifies the affected path, record, or field where safe. |
| `location` | Optional source line/record reference | Present when available. |

An unsupported record is only a warning if the remaining supported data is demonstrably safe to inspect; otherwise it is an error.
