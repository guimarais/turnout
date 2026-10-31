# Feature Specification: Read-Only Layout Inspection

**Feature Branch**: `001-readonly-layout-inspection`

**Created**: 2026-10-31

**Status**: Implemented; Linux validation completed on 2026-10-31. See [verification results](quickstart.md#verified-implementation-results--2026-10-31).

**Input**: User description: "Design a plan for the initial implementations: a read-only XTrackCAD layout-inspection proof of concept."

## Clarifications

### Session 2026-10-31

- Q: How should Turnout handle files declaring a format version it has not been tested to read? → A: Accept format version 12; reject every other format version with `unsupported_version`. The XTrackCAD application version is informational and does not independently cause rejection.
- Q: What should Turnout report as layout bounds in this first release? → A: Report room dimensions separately from complete track bounds. Return track bounds only when all track geometry can be interpreted reliably; otherwise mark track bounds unavailable and provide a diagnostic.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect a Layout Summary (Priority: P1)

A model railway designer asks an MCP-compatible assistant to inspect an XTrackCAD layout file and receive a structured summary of the layout that can be safely used for further discussion.

**Why this priority**: This establishes the first end-to-end value: an assistant can obtain trustworthy information from a real layout without risking the original file.

**Independent Test**: Start the server, submit a representative valid layout file to the layout-information tool, and verify that the response identifies the opened layout and reports the supported metadata and dimensions that are available in the file.

**Acceptance Scenarios**:

1. **Given** a valid supported XTrackCAD layout file, **When** the user opens it and requests layout information, **Then** the assistant receives a structured summary containing the source path, layout identity, and every supported metadata and dimensions value available in that file.
2. **Given** a layout lacking an optional metadata or bounds value, **When** the user requests layout information, **Then** the response identifies that value as unavailable rather than inventing it.
3. **Given** a valid layout, **When** it is inspected, **Then** its contents and modification time remain unchanged.
4. **Given** `layouts/mrkln_sample.xtc`, **When** the user opens it and requests layout information, **Then** the assistant receives its two titles, HO scale, 96-by-48 inch room size, and a summary of four supported turnouts.
5. **Given** a nonempty layout whose track geometry can all be interpreted, **When** the user requests layout information, **Then** the result contains the complete axis-aligned track extent in inches, separately from declared room dimensions.
6. **Given** a layout with any uninterpretable track geometry or no track objects, **When** the user requests layout information, **Then** track bounds are explicitly unavailable with a diagnostic, and room dimensions remain independently available when declared.

---

### User Story 2 - Enumerate Supported Track Objects (Priority: P2)

A model railway designer asks an assistant what track objects a layout contains so that they can understand the existing plan before proposing a change.

**Why this priority**: Listing supported objects makes the summary useful for practical layout analysis and validates that file data can be mapped into an understandable model.

**Independent Test**: Open a fixture containing supported track objects and request the track list; compare the returned object identifiers, types, and available positions or orientations with the fixture's expected values.

**Acceptance Scenarios**:

1. **Given** a layout containing supported track sections and turnouts, **When** the user lists tracks, **Then** the assistant receives one structured entry for each supported object and can distinguish turnouts from other supported track sections.
2. **Given** a layout containing an unsupported object, **When** the user lists tracks, **Then** the assistant reports the unsupported object or feature clearly without omitting that fact from the result.
3. **Given** `layouts/mrkln_sample.xtc`, **When** the user lists tracks, **Then** the assistant receives four turnout entries in source order, preserving the UTF-8 Märklin catalogue labels and available connected or open endpoints.

---

### User Story 3 - Receive Actionable Failure Information (Priority: P3)

A model railway designer gives the assistant a missing, malformed, or unsupported layout file and receives a clear result that explains whether inspection can continue.

**Why this priority**: Trust in inspection depends on making failures visible rather than returning incomplete data as if it were complete.

**Independent Test**: Submit missing, malformed, and unsupported-version fixtures and verify that each response is structured, identifies the file or feature involved, and causes no filesystem modification.

**Acceptance Scenarios**:

1. **Given** a nonexistent or unreadable path, **When** the user tries to open it, **Then** the assistant receives a failure that identifies the path and access problem.
2. **Given** a malformed layout, **When** the user tries to open it, **Then** the assistant receives a failure or diagnostic that identifies the parsing problem without presenting a successful layout summary.
3. **Given** a format-version-12 layout containing unknown features, **When** the known portion can still be inspected safely, **Then** the assistant receives supported results together with explicit warnings; if safe interpretation cannot be established, the open fails with a diagnostic.
4. **Given** a layout declaring any format version other than 12, **When** the user opens it, **Then** the open fails with `unsupported_version`, regardless of its XTrackCAD application version.

### Edge Cases

- A supplied path is a directory, has a non-layout extension, or is empty.
- A layout contains no supported track objects.
- Coordinates or bounds are absent, invalid, or exceed the supported numeric range.
- An MCP request refers to no currently opened layout or to a layout that failed to open.
- A parser recognizes a record shape but cannot safely interpret one of its values.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an MCP-accessible read-only workflow that opens a user-supplied XTrackCAD layout file for inspection.
- **FR-002**: The system MUST return a structured layout-information result that includes the layout identity and all supported metadata and dimensions available from the source file.
- **FR-003**: The system MUST return a structured list of supported track objects, with a stable identifier and object type for each item.
- **FR-004**: The system MUST distinguish supported turnouts from other supported track objects in its returned data.
- **FR-005**: The system MUST report unreadable paths, malformed content, and unsupported or unknown file features clearly and without falsely claiming complete support.
- **FR-006**: The system MUST leave source layout files unchanged for every operation in this feature.
- **FR-007**: The system MUST make a failed open unavailable for subsequent inspection until a layout is successfully opened.
- **FR-008**: The system MUST include automated regression coverage for representative valid, malformed, and unsupported-feature layout samples where those samples may legally be retained.
- **FR-009**: The first release MUST run on Linux and use portable path and file handling that does not preclude later Windows or macOS support.
- **FR-010**: The system MUST preserve and return valid UTF-8 layout text, including track-library and catalogue labels containing non-ASCII characters.
- **FR-011**: The system MUST successfully inspect `layouts/mrkln_sample.xtc` as a representative XTrackCAD 5.3.1GA input and report its source path, declared titles, scale, room dimensions in inches, and four turnout objects.
- **FR-012**: The system MUST report the available endpoint state and references for supported turnout objects, including connections to another turnout and unconnected ends.
- **FR-013**: The system MUST include the source path in every successful `open_layout` result.
- **FR-014**: The system MUST accept only declared layout format version 12 and reject every other format version with `unsupported_version`. The XTrackCAD application version MUST be reported separately and MUST NOT independently cause rejection. A missing or malformed format-version declaration MUST fail with `malformed_record`.
- **FR-015**: The system MUST report declared room dimensions separately from track bounds. Track bounds MUST describe the complete axis-aligned extent of all track centerline geometry in inches, including curve extrema and compound turnout track segments; decorative objects and track width are excluded. If any track geometry cannot be interpreted reliably, an unknown object cannot be established as non-track, or the layout contains no tracks, track bounds MUST be explicitly unavailable with a diagnostic. Partial track bounds MUST NOT be presented as complete.

### Key Entities *(include if feature involves data)*

- **Layout source**: A user-supplied native XTrackCAD layout file selected for read-only inspection.
- **Inspection session**: The current successfully opened layout and the diagnostics created while reading it.
- **Layout summary**: Supported metadata, declared room dimensions, complete axis-aligned track bounds in inches when calculable, and explicit unavailability with diagnostics otherwise.
- **Track object**: A supported section or turnout with a stable source-derived identifier, type, and available geometric information.
- **Diagnostic**: A warning or error describing unreadable input, malformed data, or an unsupported feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the open-and-summary workflow for a representative valid layout in one MCP interaction sequence and receive the source path without manual file conversion.
- **SC-002**: For each supported object in the committed representative fixtures, the returned object count and type match the fixture's expected result exactly.
- **SC-003**: Automated tests demonstrate that inspection leaves every test input byte-for-byte unchanged.
- **SC-004**: Automated tests cover a valid layout, a malformed layout, and a layout with at least one unsupported feature, and each produces the expected success or diagnostic outcome.
- **SC-005**: A client can start the server and invoke the read-only workflow over the selected standard input/output transport on the supported development platform.
- **SC-006**: Automated regression tests open `layouts/mrkln_sample.xtc`, return exactly four turnout entries in source order, and preserve its UTF-8 labels and source bytes unchanged.

## Assumptions

- The initial compatibility target is layout format version 12, represented by the XTrackCAD 5.3.1GA sample. The format version and producing application version are distinct values.
- The first feature is intentionally limited to inspection; creation, modification, native writing, visual export, and parts-list export are out of scope.
- The first proof of concept supports only file paths explicitly supplied by the user or MCP client and does not scan directories.
- Supported metadata, objects, bounds, and connections depend on demonstrated parser coverage; unavailable fields are reported as unavailable rather than inferred.
- Parser evaluation may result in a direct dependency, an adapter, or a small in-project reader; the chosen implementation must preserve the specified observable behavior.
- `layouts/mrkln_sample.xtc` is the first committed compatibility fixture. It is a plain-text UTF-8 XTrackCAD 5.3.1GA file and establishes the minimum support for turnout-only layouts with Märklin catalogue labels.
