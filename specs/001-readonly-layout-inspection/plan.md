# Implementation Plan: Read-Only Layout Inspection

**Branch**: `001-readonly-layout-inspection` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-readonly-layout-inspection/spec.md`

## Summary

Deliver Turnout's first safe vertical slice: an STDIO MCP server opens a user-selected plain-text XTrackCAD `.xtc` layout, returns a structured summary, lists supported straight, curve, and turnout objects, and reports diagnostics without altering the source. The server owns a narrow reader and application layout model; it does not directly depend on `xtrakcad_parser`, whose GPL-2.0 license is not automatically compatible with Turnout's GPL-3.0-only license. The official Rust MCP SDK (`rmcp`) supplies typed tools and STDIO transport.

## Technical Context

**Language/Version**: Rust 2024 edition; rolling `stable` channel in `rust-toolchain.toml`. This is a channel selection, not an exact compiler pin. Record the compiler version with validation results and commit `Cargo.lock` for dependency reproducibility.

**Primary Dependencies**: `rmcp` (official Rust MCP SDK; server + STDIO features), Tokio, Serde, `schemars`; small error and test-only helpers chosen during implementation

**Storage**: Read-only user-supplied files; no persistent application storage

**Testing**: `cargo test`; unit/fixture parser tests plus an STDIO MCP subprocess integration test

**Target Platform**: Linux development target; portable filesystem and process boundaries for later Windows and macOS support

**Project Type**: Single Rust executable with a reusable library core

**Performance Goals**: Correctness and diagnostic completeness first; each committed representative fixture must complete deterministically in the automated suite. Production size and latency SLOs wait for a real compatibility corpus.

**Constraints**: STDIO only; accept only plain-text `.xtc` initially (not `.xtce` archives); never write, rename, or alter source files; preserve valid UTF-8 labels; recognize only fixture-proven file features; disclose unknown records and unavailable values; do not directly link GPL-2.0-only parser code without a licensing decision

**Scale/Scope**: One active inspection session per server process; header/metadata, bounds when available, and `STRAIGHT`, `CURVE`, and `TURNOUT` records with documented endpoint references. The first regression fixture is `layouts/mrkln_sample.xtc`: four compound `TURNOUT` records with UTF-8 Märklin labels, `T4` connected endpoints, `E4` open endpoints, and visual subsegments terminating in `END$SEGS`; no editing, SVG, parts list, broad object support, or `.xtce` handling

**Compatibility policy**: Accept only layout format version 12. Reject every other declared format version with `unsupported_version`; reject missing, malformed, or conflicting version declarations with `malformed_record`. Keep the producing application version separate and informational. For example, `VERSION 12 5.2.0` declares format 12 and application version 5.2.0; the sample's producer comment is additional provenance.

**Bounds policy**: Room dimensions are declared metadata. Track bounds are a separate complete axis-aligned extent of track centerlines, excluding decorative lines, rail width, and room dimensions. Include straight endpoints, circular-arc interior extrema, and transformed turnout track segments. If any track geometry is unsupported, an unknown object cannot be established as non-track, or no tracks exist, return `bounds: null` plus `bounds_unavailable`. Never substitute room dimensions or endpoint-only extents for complete track bounds.

## Design workflow and acceptance gates

Phase 0 decisions are recorded in [research.md](./research.md); no product clarifications remain. Phase 1 contracts and entities are in [data-model.md](./data-model.md) and [contracts/read-only-tools.md](./contracts/read-only-tools.md).

Implementation proceeds through typed domain validation, fixture-based record parsing, geometry bounds, and MCP mapping. Native record offsets and angle conversion belong in `xtc.rs`; tools consume application-owned values. Validate finite coordinates, unique object IDs, complete segment blocks, and endpoint references before a layout becomes usable. Dangling references produce explicit diagnostics; duplicate IDs prevent opening because identity is ambiguous.

Acceptance requires analytical fixtures for arc extrema and rotated turnout segments, complete-versus-unavailable bounds, strict version acceptance/rejection, malformed paths and records, source integrity for every fixture, and actual executable STDIO calls. Tests sharing a file run sequentially during implementation. [quickstart.md](./quickstart.md) defines validation commands; this planning pass does not certify the current code as passing these gates.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The checked-in constitution is still its uncustomized template, so it has no enforceable project-specific gates. This plan applies the explicit project-context gates:

- **Read-only integrity**: PASS. Tool paths only read; tests verify input bytes and modification time are unchanged.
- **Evidence-based format support**: PASS. Support is constrained to documented 5.3.1GA plain-text records proven by fixtures; other records become diagnostics.
- **XTrackCAD adapter isolation**: PASS. `xtc` contains native syntax; `layout` is owned application data.
- **Cross-platform design**: PASS. Use `PathBuf`, no production shell invocation, and SDK-provided STDIO.
- **Safe dependency licensing**: PASS. The external GPL-2.0 parser is not a direct dependency without a later licensing decision.

**Post-design re-check**: PASS at design level. Strict format acceptance, conservative bounds availability, explicit units, source diagnostics, and immutable inputs preserve all five constraints. This is a design assessment, not evidence of implementation completion. The constitution remains an unratified template.

## Project Structure

### Documentation (this feature)

```text
specs/001-readonly-layout-inspection/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── read-only-tools.md
└── tasks.md                 # Existing implementation and convergence backlog
```

### Source Code (repository root)

```text
src/
├── main.rs                  # Starts the STDIO server
├── lib.rs                   # Public library boundary
├── mcp.rs                   # Typed tools, router, and inspection-session state
├── layout.rs                # Application-owned summary, geometry, diagnostics
└── xtc.rs                   # Narrow parser and adapter for the supported text format

tests/
├── fixtures/
│   ├── authored/            # Original .xtc inputs and manifests
│   └── compatibility/       # Future provenance-tracked, tool-produced corpus
├── parser_tests.rs
└── mcp_stdio_tests.rs

layouts/
└── mrkln_sample.xtc         # First committed compatibility fixture
```

**Structure Decision**: Use one Cargo project. `xtc` is the only module that knows native record syntax; `layout` is the stable internal boundary for future CAD adapters and geometry work. The MCP layer never exposes parser-internal records directly.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | N/A |
