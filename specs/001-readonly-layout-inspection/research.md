# Research: Read-Only Layout Inspection

## MCP server and STDIO transport

**Decision**: Use the official Rust MCP SDK, `rmcp`, with its server-side STDIO transport, typed tool declarations, Tokio, Serde, and generated JSON Schema.

**Rationale**: The official SDK documents server-side STDIO transport and macro-based tools (`#[tool]` and `#[tool_router]`), which generate structured schemas from typed input and output. Its child-process client transport supports a true end-to-end test that starts the compiled Turnout binary and calls its tools over STDIO. Pin a stable SDK release compatible with the selected Rust MSRV at implementation time; do not depend on the SDK main branch. Expected file failures should be structured diagnostic results, while protocol-invalid requests use MCP errors.

**Alternatives considered**: Implement MCP framing directly (unnecessary protocol burden); use a non-Rust runtime (conflicts with the native executable direction).

**Sources**: [Rust SDK README](https://github.com/modelcontextprotocol/rust-sdk/blob/main/README.md), [transport implementation](https://github.com/modelcontextprotocol/rust-sdk/blob/main/crates/rmcp/src/transport.rs), [server examples](https://github.com/modelcontextprotocol/rust-sdk/blob/main/examples/servers/README.md), [client examples](https://github.com/modelcontextprotocol/rust-sdk/blob/main/examples/clients/README.md).

## Native format boundary and compatibility target

**Decision**: Target XTrackCAD 5.3.1GA plain-text `.xtc` files first. Support documented headers/metadata and only `STRAIGHT`, `CURVE`, and `TURNOUT` records proven by fixtures, including documented endpoint references. Explicitly reject `.xtce` archives.

**Rationale**: The official project identifies 5.3.1GA as current stable and documents the plain-text layout headers, version records, metadata, layers, `END$TRACKS`, track types, units, angular convention, and endpoint semantics. `.xtce` adds archive handling unrelated to the first vertical slice. The parser reports, rather than ignores, unrecognized top-level records and unsafe fields.

**Alternatives considered**: Accept `.xtce` now (unnecessary archive complexity); support historical versions without fixtures (unverifiable); infer geometry from rendered output (lossy).

**Sources**: [current release](https://sourceforge.net/p/xtrkcad-fork/wiki/DownloadInstall/), [layout-file reference](https://sourceforge.net/p/xtrkcad-fork/wiki/LayoutFile/), [layout elements](https://sourceforge.net/p/xtrkcad-fork/wiki/LayoutElements/), [concepts](https://sourceforge.net/p/xtrkcad-fork/wiki/Concepts/).

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
