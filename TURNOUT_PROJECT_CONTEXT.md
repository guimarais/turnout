# Turnout — Project Context

> **Purpose:** This document captures the decisions, goals, constraints, and technical discussion established so far. It is intended to be added to the project repository as shared context for future planning and implementation.
>
> **Status:** Initial project context; some technical choices remain to be validated.

## 1. Project identity

- **Project name:** Turnout
- **Suggested repository name:** `turnout-mcp` (the repository has already been created; use its actual name if different)
- **Project type:** Model railway layout MCP server
- **Initial CAD integration:** XTrackCAD only
- **Primary purpose:** Allow MCP-compatible AI assistants to inspect, analyse, create, and modify XTrackCAD layouts through natural-language interaction.

The project was previously discussed under the names TrackBrain and other alternatives. The current and authoritative project name is **Turnout**.

Do not use the previous names in new project documentation, code, package metadata, or user-facing descriptions.

## 2. Product vision

Turnout should provide a reliable bridge between AI assistants and XTrackCAD.

A user should eventually be able to ask an assistant questions and give it instructions such as:

- Describe this layout.
- How many track sections and turnouts does it contain?
- What are the overall layout dimensions?
- Which track sections are disconnected?
- Calculate the total length of track.
- Add a passing loop.
- Add or replace a turnout.
- Connect two track sections.
- Modify an existing section of the layout.
- Check whether the layout fits within a specified space.
- Produce a parts list or visual preview.

Turnout must translate these requests into explicit, structured, and validated operations on an XTrackCAD layout.

**XTrackCAD is the initial and only supported CAD application.** The internal architecture should avoid unnecessary coupling to XTrackCAD-specific concepts where practical, but support for other CAD applications is not part of the initial scope.

## 3. Target platforms

The project is being started on **Linux**, but it must be designed with future support for:

- Linux
- Windows
- macOS (Intel and Apple Silicon where practical)

Cross-platform support is an architectural requirement, not an afterthought.

Prefer portable Rust libraries and avoid unnecessary operating-system-specific dependencies. File paths, process launching, configuration locations, packaging, and MCP client setup must be considered across all target platforms.

## 4. Language and technology direction

### Current recommendation: Rust

Rust was recommended as the primary implementation language because:

- It can produce native executables for Linux, Windows, and macOS.
- It is suitable for reliable parsing and writing of structured native files.
- Strong types and memory safety are useful for a geometry-heavy application.
- There is an existing Rust XTrackCAD parser that may provide a starting point.
- A standalone executable can avoid requiring end users to install a Python or Node.js runtime.

This is the current technical direction, but it should be validated with a small proof of concept before it is treated as irrevocable.

Python may be used for development scripts, test utilities, or experiments, but the intended product should not require Python at runtime if the Rust approach proves viable.

### Candidate technology stack

| Area | Candidate |
|---|---|
| Main language | Rust |
| MCP SDK | `rmcp` / official Rust MCP SDK |
| Async runtime | Tokio |
| Serialization | Serde |
| Tests | Cargo test |
| Build | Cargo |
| Cross-platform CI | GitHub Actions or equivalent |
| Layout preview | SVG export |
| Native layout format | XTrackCAD `.xtc` |

The Rust MCP SDK's capabilities and maturity should be checked against the project's requirements during the proof of concept. Do not assume that every MCP feature available in the Python or TypeScript SDKs is necessarily available or equally mature in Rust.

## 5. XTrackCAD file-format strategy

Native XTrackCAD file compatibility is one of the project's largest technical risks.

An existing Rust project has been identified:

- Repository: <https://github.com/RobertPHeller/xtrakcad_parser>
- Documentation: <https://docs.rs/xtrakcad_parser/latest/xtrakcad_parser/>
- XTrackCAD layout-file reference: <https://sourceforge.net/p/xtrkcad-fork/wiki/LayoutFile/>

The existing parser is a potential foundation for **reading** XTrackCAD files. Its exact coverage, maintenance status, compatibility, and suitability must be evaluated against real sample files.

Important distinctions:

- Do not assume the existing parser can write native XTrackCAD files.
- Native `.xtc` writing is a separate capability that must be investigated and implemented if needed.
- Do not claim complete file-format support without testing.
- Preserve unknown or unsupported objects whenever possible.
- Never silently discard data that the implementation does not understand.
- Test generated files by opening them in XTrackCAD itself.

Collect representative `.xtc` sample files early, ideally including simple and more complex layouts, and keep suitable fixtures in the test suite if licensing and privacy permit.

### 5.1 Track systems and parameter libraries

Track systems provide catalogues of reusable parts: straights, curves, turnouts, crossings, and other features. In XTrackCAD these definitions are stored in `.xtp` parameter files. A track system may span multiple files, and a layout may use parts from multiple systems or custom libraries.

Keep the **placed track instance** in a layout distinct from the **part definition** in a parameter library. XTrackCAD copies turnout and structure definitions into the `.xtc` file when they are placed; the original parameter file is not required to inspect those instances. Consequently, a layout alone does not necessarily identify the original library or contain the complete catalogue needed to design an extension.

After a layout is loaded, Turnout must be able to resolve relevant parameter libraries and retrieve their available part definitions through MCP. This is a prerequisite for designing a complete layout using actual catalogue parts. Use explicitly configured library files or directories; report missing or ambiguous matches and allow explicit library selection. Do not assume one library per layout or infer an entire catalogue from the parts already placed.

The required behaviour, proposed MCP workflow, and acceptance cases are recorded in [Track parameter catalogue retrieval](docs/track-parameter-catalog.md). This is a follow-on capability to the initial read-only inspection feature, and is not implemented by its existing tools.

Format reference: [XTrackCAD parameter file information](https://sourceforge.net/p/xtrkcad-fork/wiki/ParameterFileInformation/).

## 6. Core product capabilities

The long-term product should cover the following areas.

### 6.1 Read and inspect layouts

- Open supported native `.xtc` files.
- Read layout metadata.
- Enumerate supported layout objects.
- Identify track sections and turnouts.
- Read positions, orientations, and geometry.
- Read supported connections.
- Determine layout bounds and dimensions.
- Report unsupported or malformed data clearly.

### 6.2 Analyse layouts

- Count track objects and turnouts.
- Calculate track lengths where the source data permits reliable calculation.
- Inspect connectivity.
- Identify disconnected or isolated track sections where detectable.
- Analyse layout bounds.
- Produce structured summaries and reports.

### 6.3 Geometry and connectivity

The geometry model should support, as a minimum:

- Straight track.
- Curved track.
- Turnouts.
- Track endpoints and orientations.
- Track-to-track connections.
- Geometric continuity checks.

Geometry operations must use explicit units and tolerances. Avoid arbitrary hardcoded tolerances or assumptions about one scale.

### 6.4 Create and modify layouts

Eventually support:

- Creating a new layout.
- Adding track sections.
- Removing track sections.
- Moving and rotating track sections.
- Adding supported turnouts.
- Connecting compatible track sections.
- Modifying existing layout configurations.
- Saving changes in a native format that XTrackCAD can open.

Creation and modification should be implemented only after the file reader, internal model, and geometry foundations are reliable.

### 6.5 Validation

Provide checks for supported conditions such as:

- Invalid or incomplete geometry.
- Incompatible track connections.
- Disconnected sections.
- Geometric discontinuities.
- Objects outside defined layout bounds.
- Other constraints established as the implementation develops.

Validation results should distinguish errors, warnings, and informational findings.

### 6.6 Export

Useful output formats include:

- SVG layout preview.
- Track inventory / parts list.
- Structured layout report (for example JSON or CSV).

SVG is a useful early visualisation target; it is not a replacement for the native XTrackCAD file.

### 6.7 Retrieve track-system catalogues

- Read supported `.xtp` parameter libraries from configured sources.
- Resolve candidate libraries after opening a layout, preserving uncertainty about their relationship to placed parts.
- List and search available parts, including parts not yet placed in the layout.
- Retrieve part identity, manufacturer, catalogue number, scale, and supported geometry, endpoints, and routes.
- Report units, provenance, unsupported definitions, and missing information explicitly.
- Support multiple libraries, custom parts, and explicit selection when automatic resolution is insufficient.
- Keep layout inspection available when the original parameter libraries are absent.

Library retrieval is read-only. Placement, connection, and native writing remain separate capabilities.

## 7. Scales, gauges, and units

Turnout must not be hardcoded for a single model railway scale.

The design should support common scales, including (but not limited to):

- Z
- N
- TT
- HO
- OO
- O
- G

It must also allow custom scales and gauges.

Important concepts must remain distinct:

- Model scale ratio.
- Prototype dimensions.
- Model dimensions.
- Track gauge.
- Measurement units.

Support metric and imperial measurements. Use explicit conversions and a consistent internal coordinate convention. Region-specific standards and nominal gauges should be verified before being encoded as defaults.

## 8. MCP interface

The main user-facing integration is the Model Context Protocol (MCP).

The initial implementation is expected to use **STDIO transport**, subject to verification with the intended MCP clients and their current connection mechanisms.

The design should expose narrowly scoped tools with structured inputs and outputs. Candidate tools include:

| Tool | Purpose |
|---|---|
| `open_layout` | Open a supported XTrackCAD layout |
| `get_layout_info` | Return layout metadata and dimensions |
| `list_tracks` | List supported track objects |
| `get_track_details` | Inspect one track object |
| `list_track_libraries` | Return available libraries and their resolution status for the open layout |
| `select_track_libraries` | Explicitly select libraries for the open layout |
| `list_track_parts` | Search available part definitions in selected libraries |
| `get_track_part` | Retrieve a part definition with supported geometry and provenance |
| `validate_layout` | Check supported geometry and connectivity rules |
| `create_layout` | Create a new layout |
| `add_straight` | Add a straight track section |
| `add_curve` | Add a curved track section |
| `add_turnout` | Add a supported turnout |
| `connect_tracks` | Connect compatible track sections |
| `delete_track` | Remove a track object |
| `save_layout` | Save a validated layout |
| `export_parts_list` | Export a track inventory |
| `export_svg` | Export an SVG preview |

These are candidate names and capabilities, not a frozen API. Tool contracts should be designed after the internal layout model and first read-only workflows are understood.

The project has discussed use with ChatGPT and Claude Desktop. Validate the actual MCP configuration and packaging requirements for each client rather than assuming their setup procedures are identical.

## 9. Safety and data integrity

Safety is a core requirement, especially once editing is implemented.

Turnout should:

- Preserve the original layout by default.
- Work on a copy or an explicit working version when making changes.
- Create backups before destructive operations.
- Require explicit approval before overwriting an existing file.
- Validate modifications before saving.
- Clearly report failed or partially completed operations.
- Avoid silently applying incomplete or unvalidated changes.
- Provide a preview or summary of intended changes before committing them.

Read-only analysis must never modify the source layout.

## 10. Suggested architecture

Keep the code modular. A possible Rust module structure is:

```text
src/
├── main.rs
├── lib.rs
├── mcp/
│   ├── mod.rs
│   ├── server.rs
│   └── tools/
├── xtc/
│   ├── mod.rs
│   ├── reader.rs
│   ├── writer.rs
│   └── adapter.rs
├── layout/
│   ├── mod.rs
│   ├── model.rs
│   └── operations.rs
├── geometry/
│   ├── mod.rs
│   ├── straight.rs
│   ├── curve.rs
│   ├── turnout.rs
│   └── connections.rs
├── validation/
│   ├── mod.rs
│   └── validator.rs
├── scales/
│   ├── mod.rs
│   └── registry.rs
└── export/
    ├── mod.rs
    └── svg.rs

tests/
├── fixtures/
├── parser_tests.rs
├── geometry_tests.rs
├── connection_tests.rs
└── writer_tests.rs
```

This is a starting point, not a requirement to create every module immediately. Prefer a small working vertical slice over scaffolding a large number of empty modules.

The internal layout model should be separated from the XTrackCAD parser so that parser implementation details do not leak throughout the application.

## 11. Development roadmap

### Milestone 1 — Repository and technical proof of concept

- Inspect the repository and existing Spec-Kit setup.
- Establish Rust project conventions and CI.
- Identify the target XTrackCAD version.
- Obtain representative `.xtc` files.
- Evaluate the existing Rust parser.
- Verify that the Rust MCP SDK supports the required server and STDIO workflow.
- Build a minimal executable exposing a read-only `get_layout_info` tool.
- Confirm a client can launch and call the server.

**Exit criterion:** A native Rust executable can start as an MCP server, read a representative XTrackCAD file, and return useful structured information to an MCP client.

### Milestone 2 — Reliable read-only support

- Build the internal layout representation.
- Parse supported objects.
- Add parser fixtures and regression tests.
- Report unsupported features.
- Implement layout summaries, track listing, and basic connectivity inspection.

**Exit criterion:** An assistant can inspect a real layout without modifying it.

### Milestone 2a — Track parameter catalogue retrieval

- Specify and implement configured `.xtp` library sources and explicit library selection.
- Resolve relevant library candidates when a layout is opened, without assuming a unique original source.
- Expose catalogue search and part details through MCP, including unplaced parts.
- Preserve scale, units, endpoints, routes, source identity, and diagnostic information.
- Add fixtures for mixed libraries, custom parts, missing libraries, ambiguous matches, and unsupported definitions.

**Exit criterion:** After opening a layout, an assistant can retrieve supported parts from the selected track-system libraries, including parts absent from the layout; missing or ambiguous libraries are reported without preventing layout inspection.

### Milestone 3 — Geometry and validation

- Implement coordinate and unit conventions.
- Implement straight and curved geometry.
- Model turnout geometry.
- Implement track endpoint and connectivity logic.
- Add validation and SVG preview.

**Exit criterion:** TrackBrain can analyse and visualise supported layout geometry with tested results.

### Milestone 4 — Creation and editing

- Implement layout creation.
- Use retrieved parameter-library definitions for catalogue part placement; do not invent dimensions or substitute similarly named parts silently.
- Implement track insertion, deletion, movement, and rotation.
- Implement supported turnout and connection operations.
- Design and implement native file writing.
- Validate generated files by opening them in XTrackCAD.
- Add backup and approval workflows.

**Exit criterion:** Turnout can safely produce native layouts that XTrackCAD opens successfully.

### Milestone 5 — Cross-platform packaging and release

- Build and test on Linux, Windows, and macOS.
- Automate builds and release artifacts.
- Document MCP client configuration.
- Document supported XTrackCAD versions and file features.
- Publish examples and usage documentation.

**Exit criterion:** Users can install and configure Turnout on each supported platform using documented steps.

## 12. Initial acceptance criteria

The first meaningful product milestone is read-only layout inspection.

It is complete when:

1. Turnout starts as an MCP server using the chosen transport.
2. An MCP client can connect and invoke its tools.
3. Turnout can open a valid representative `.xtc` file.
4. It can report supported layout metadata.
5. It can enumerate supported track objects.
6. It can identify supported turnouts.
7. It can report layout bounds or dimensions where available.
8. It can inspect supported track connectivity.
9. Unsupported or malformed data is reported clearly.
10. Read-only operations leave the original file unchanged.
11. Automated tests cover the implemented parser behaviour.

Do not make native editing a prerequisite for the first milestone.

## 13. Open questions to resolve

These questions should be addressed through Spec-Kit clarification and planning before the relevant implementation begins.

1. Which XTrackCAD version is the initial compatibility target?
2. Which XTrackCAD versions should eventually be supported?
3. Can the existing Rust parser be used directly as a library, or will an adapter/fork be needed?
4. What objects and file features does the parser actually support?
5. Can unknown objects be preserved during a read-modify-write cycle?
6. What is the native file-writing strategy?
7. Which track libraries should be supported first, and which configured files or directories will provide them? See [catalogue retrieval requirements](docs/track-parameter-catalog.md).
8. What should the first editing release support beyond basic track, curves, and turnouts?
9. What exact MCP clients and versions should be included in the initial compatibility tests?
10. Which target architectures should be included in the first cross-platform release?

## 14. Working principles for future contributors and AI coding agents

- Treat this document as project context, not as a substitute for the formal Spec-Kit specification.
- Keep the initial scope limited to XTrackCAD.
- Prefer evidence from actual XTrackCAD files and tests over assumptions about the file format.
- Do not invent or assume undocumented XTrackCAD semantics.
- Keep native file I/O isolated behind an adapter.
- Keep geometry and units explicit.
- Make read-only inspection reliable before implementing editing.
- Do not overwrite user files without explicit approval.
- Design for Linux, Windows, and macOS from the beginning.
- Prefer small, testable increments and working end-to-end demonstrations.
- Update this document when a decision is made that materially changes the project direction.

---

## 15. Short project summary

**Turnout** is a cross-platform Rust-based MCP server intended to let AI assistants inspect, analyse, create, and modify model railway layouts in XTrackCAD. It starts with Linux development and must be designed for future Windows and macOS support. Its first priority is reliable read-only parsing and layout analysis; geometry, validation, native file writing, and editing follow in later milestones. It must support multiple scales, gauges, and measurement units, preserve user data, and never silently discard unsupported layout information.

Before catalogue-based layout creation, Turnout must retrieve the reusable part definitions in the relevant XTrackCAD `.xtp` parameter libraries after a layout is loaded. Placed instances and available catalogue parts are separate concepts; unavailable libraries must not prevent inspection.
