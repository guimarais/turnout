# Research: Read-Only Layout Inspection

## MCP server and STDIO transport

**Decision**: Use the official Rust MCP SDK, `rmcp`, with its server-side STDIO transport, typed tool declarations, Tokio, Serde, and generated JSON Schema.

**Rationale**: The official SDK documents server-side STDIO transport and macro-based tools (`#[tool]` and `#[tool_router]`), which generate structured schemas from typed input and output. Its child-process client transport supports a true end-to-end test that starts the compiled Turnout binary and calls its tools over STDIO. Pin a stable SDK release compatible with the selected Rust MSRV at implementation time; do not depend on the SDK main branch. Expected file failures should be structured diagnostic results, while protocol-invalid requests use MCP errors.

**Alternatives considered**: Implement MCP framing directly (unnecessary protocol burden); use a non-Rust runtime (conflicts with the native executable direction).

**Sources**: [Rust SDK README](https://github.com/modelcontextprotocol/rust-sdk/blob/main/README.md), [transport implementation](https://github.com/modelcontextprotocol/rust-sdk/blob/main/crates/rmcp/src/transport.rs), [server examples](https://github.com/modelcontextprotocol/rust-sdk/blob/main/examples/servers/README.md), [client examples](https://github.com/modelcontextprotocol/rust-sdk/blob/main/examples/clients/README.md).

## Native format boundary and compatibility target

**Decision**: Accept only plain-text `.xtc` layout format version 12, as clarified on 2026-10-31. The representative producer is XTrackCAD 5.3.1GA; application-version strings do not determine format acceptance. Reject any other declared format version with `unsupported_version`, and missing or malformed declarations with `malformed_record`. Support fixture-proven `STRAIGHT`, `CURVE`, and `TURNOUT` records and endpoint references; reject `.xtce` archives.

**Rationale**: The official project identifies 5.3.1GA as current stable and documents the plain-text layout headers, version records, metadata, layers, `END$TRACKS`, track types, units, angular convention, and endpoint semantics. `.xtce` adds archive handling unrelated to the first vertical slice. The parser reports, rather than ignores, unrecognized top-level records and unsafe fields.

**Alternatives considered**: Accept `.xtce` now (unnecessary archive complexity); support historical versions without fixtures (unverifiable); infer geometry from rendered output (lossy).

**Sources**: [current release](https://sourceforge.net/p/xtrkcad-fork/wiki/DownloadInstall/), [layout-file reference](https://sourceforge.net/p/xtrkcad-fork/wiki/LayoutFile/), [layout elements](https://sourceforge.net/p/xtrkcad-fork/wiki/LayoutElements/), [concepts](https://sourceforge.net/p/xtrkcad-fork/wiki/Concepts/).

## Committed representative layout

**Decision**: Treat `layouts/mrkln_sample.xtc` as the first compatibility fixture and minimum supported real-world layout. It is UTF-8 text produced by XTrackCAD 5.3.1GA with `VERSION 12`, two title fields, HO scale, a 96-by-48 room, and four compound `TURNOUT` records. Its SHA-256 is `917a8445d1aca4d7caec360477e5acc509d0c9434e72781e0d8f55c7c225a24f`.

**Rationale**: This fixture turns the initial format scope into a demonstrable contract. It requires that Turnout preserve non-ASCII Märklin catalogue names, recognise `T4` references between turnouts and `E4` open ends, and safely traverse visual subsegments (`S`, `C`, `L3`, `A3`) until `END$SEGS` without incorrectly reporting them as unsupported layout objects.

**Alternatives considered**: Treat the sample only as an ad-hoc manual test (rejected: it would not prevent regressions); reject compound turnout data (rejected: it excludes the first supplied representative layout).

## Existing Rust parser

**Decision**: Do not make `xtrakcad_parser` a direct production dependency. Use its documented behavior only as a comparison target during an isolated fixture spike; build the production reader behind Turnout's owned adapter boundary.

**Rationale**: `xtrakcad_parser` exposes a useful `Layout` API with layout summary accessors and straight, curve, and turnout iterators, so it can guide comparison tests. However, its repository states GPL-2.0 licensing, which is not automatically compatible with Turnout's GPL-3.0-only license, and its coverage is unproven against Turnout's corpus. No code or fixtures from it may be copied without a separate license review.

**Alternatives considered**: Directly link the crate (rejected pending compatible licensing and coverage evidence); fork it (same licensing/maintenance issue); write a full reader upfront (scope is intentionally narrow).

**Sources**: [`Layout` API](https://docs.rs/xtrakcad_parser/latest/xtrakcad_parser/struct.Layout.html), [element-listing example](https://docs.rs/xtrakcad_parser/latest/src/listallelements/main.rs.html), [repository README and license](https://github.com/RobertPHeller/xtrakcad_parser).

## Fixture strategy

**Decision**: Maintain compact self-authored `.xtc` layouts for exact parser/contract tests and a small XTrackCAD-5.3.1GA-produced compatibility corpus with a provenance manifest (producer version, origin, SHA-256, expected supported and unsupported records).

**Rationale**: Self-authored fixtures make expected behavior and licensing clear. Tool-produced inputs validate real interoperability. Neither user layouts nor upstream examples may be committed without documented provenance, permission, and compatible terms. Tests assert every inspection leaves source bytes unchanged and cover valid, malformed, and unsupported-feature inputs.

**Alternatives considered**: Commit arbitrary user layouts (privacy/copyright risk); use only hand-authored fixtures (misses serializer quirks); use only external corpus (fragile exact expectations).

**Sources**: [layout elements](https://sourceforge.net/p/xtrkcad-fork/wiki/LayoutElements/), [historical XTrackCAD documentation](https://sources.debian.org/src/xtrkcad/3.1.4-1/xtrkcad.help), [official project page](https://sourceforge.net/projects/xtrkcad-fork/).

## Complete track bounds

**Decision**: Keep room dimensions separate from complete track centerline bounds. Normalize understood geometry into world-space line segments and directed circular arcs. Bound lines by their endpoints; bound arcs by endpoints and each world cardinal angle included in the directed sweep. Full circles use circle bounds. For clockwise angles measured from positive Y, coordinates are `x = cx + r sin(angle)` and `y = cy + r cos(angle)` after conversion to a positive-radius internal arc.

Transform turnout S endpoints and C centers/directions from local coordinates before calculating bounds. Derive the rotation mapping from the native convention and prove it with asymmetric fixtures; rotating a local bounding rectangle overestimates the actual geometry. Preserve native signed-radius direction semantics until converted into an explicit sweep; never discard the sign without accounting for direction. If sweep or direction is ambiguous, return unavailable bounds.

**Rationale**: Endpoint-only extents can miss curve extrema, and room dimensions are not track extents. Unknown potentially-track objects, unsupported track segments, incomplete geometry, and empty layouts require `bounds: null` plus a diagnostic. Known decorative segments do not affect track bounds.

**Alternatives considered**: Partial bounds marked complete (misleading); endpoint-only bounds (inexact); room dimensions substituted for track bounds (different meaning); rejecting otherwise readable layouts solely because bounds are unavailable (unnecessary loss of inspection value).

**Sources**: [LayoutElements](https://sourceforge.net/p/xtrkcad-fork/wiki/LayoutElements/), [ParameterFileInformation](https://sourceforge.net/p/xtrkcad-fork/wiki/ParameterFileInformation/), [CompoundElements](https://sourceforge.net/p/xtrkcad-fork/wiki/CompoundElements/). The extrema algorithm is a mathematical design inference from the documented geometry conventions, not a claim of tested implementation coverage.

## Toolchain and module layout

**Decision**: Retain the repository's rolling Rust stable channel and current single-file modules `src/layout.rs`, `src/xtc.rs`, and `src/mcp.rs`. Record actual compiler versions in verification output and lock dependency versions with `Cargo.lock`.

**Rationale**: These choices match the existing project and keep the first feature small. Exact compiler reproducibility is not an initial acceptance requirement. The native adapter remains isolated even within a single source file.

**Alternatives considered**: Pin an exact compiler now (adds maintenance without a stated acceptance need); introduce nested modules immediately (unnecessary scaffolding for the current code size).
