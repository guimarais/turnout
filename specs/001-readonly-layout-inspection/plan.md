# Implementation Plan: Read-Only Layout Inspection

**Branch**: `dev` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-readonly-layout-inspection/spec.md`

## Summary

Deliver Turnout's first safe vertical slice: an STDIO MCP server opens a user-selected plain-text XTrackCAD `.xtc` layout, returns a structured summary, lists supported straight, curve, and turnout objects, and reports diagnostics without altering the source. The server owns a narrow reader and application layout model; it does not directly depend on `xtrakcad_parser`, whose GPL-2.0 license is not automatically compatible with Turnout's GPL-3.0-only license. The official Rust MCP SDK (`rmcp`) supplies typed tools and STDIO transport.

## Technical Context

**Language/Version**: Rust, stable toolchain pinned in `rust-toolchain.toml` after an implementation-time SDK compatibility check

**Primary Dependencies**: `rmcp` (official Rust MCP SDK; server + STDIO features), Tokio, Serde, `schemars`; small error and test-only helpers chosen during implementation

**Storage**: Read-only user-supplied files; no persistent application storage

**Testing**: `cargo test`; unit/fixture parser tests plus an STDIO MCP subprocess integration test

**Target Platform**: Linux development target; portable filesystem and process boundaries for later Windows and macOS support

**Project Type**: Single Rust executable with a reusable library core

**Performance Goals**: Correctness and diagnostic completeness first; each committed representative fixture must complete deterministically in the automated suite. Production size and latency SLOs wait for a real compatibility corpus.

**Constraints**: STDIO only; accept only plain-text `.xtc` initially (not `.xtce` archives); never write, rename, or alter source files; recognize only fixture-proven file features; disclose unknown records and unavailable values; do not directly link GPL-2.0-only parser code without a licensing decision

**Scale/Scope**: One active inspection session per server process; header/metadata, bounds when available, and `STRAIGHT`, `CURVE`, and `TURNOUT` records with documented endpoint references; no editing, SVG, parts list, broad object support, or `.xtce` handling

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The checked-in constitution is still its uncustomized template, so it has no enforceable project-specific gates. This plan applies the explicit project-context gates:

- **Read-only integrity**: PASS. Tool paths only read; tests verify input bytes and modification time are unchanged.
- **Evidence-based format support**: PASS. Support is constrained to documented 5.3.1GA plain-text records proven by fixtures; other records become diagnostics.
- **XTrackCAD adapter isolation**: PASS. `xtc` contains native syntax; `layout` is owned application data.
- **Cross-platform design**: PASS. Use `PathBuf`, no production shell invocation, and SDK-provided STDIO.
- **Safe dependency licensing**: PASS. The external GPL-2.0 parser is not a direct dependency without a later licensing decision.

**Post-design re-check**: PASS. The data model, tool contract, and quickstart retain all five gates. Ratifying a real constitution remains a governance follow-up, not a blocker for this scoped proof of concept.

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
└── tasks.md                 # Later, from speckit-tasks
```

### Source Code (repository root)

```text
src/
├── main.rs                  # Starts the STDIO server
├── lib.rs                   # Public library boundary
├── mcp/
│   ├── mod.rs
│   ├── server.rs            # Tool router and inspection-session state
│   └── tools.rs             # Typed inputs and structured outputs
├── layout/
│   ├── mod.rs
│   └── model.rs             # Application-owned summary, tracks, diagnostics
└── xtc/
    ├── mod.rs
    ├── reader.rs            # Narrow text-format parser
    └── adapter.rs           # Maps parsed records to layout model

tests/
├── fixtures/
│   ├── authored/            # Original .xtc inputs and manifests
│   └── compatibility/       # Provenance-tracked, tool-produced corpus
├── parser_tests.rs
└── mcp_stdio_tests.rs
```

**Structure Decision**: Use one Cargo project. `xtc` is the only module that knows native record syntax; `layout` is the stable internal boundary for future CAD adapters and geometry work. The MCP layer never exposes parser-internal records directly.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | N/A | N/A |
