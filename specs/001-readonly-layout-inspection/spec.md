# Feature Specification: Read-Only Layout Inspection

**Feature Branch**: `dev`

**Created**: 2026-10-31

**Status**: Draft

**Input**: User description: "Design a plan for the initial implementations: a read-only XTrackCAD layout-inspection proof of concept."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect a Layout Summary (Priority: P1)

A model railway designer asks an MCP-compatible assistant to inspect an XTrackCAD layout file and receive a structured summary of the layout that can be safely used for further discussion.

**Why this priority**: This establishes the first end-to-end value: an assistant can obtain trustworthy information from a real layout without risking the original file.

**Independent Test**: Start the server, submit a representative valid layout file to the layout-information tool, and verify that the response identifies the opened layout and reports the supported metadata and dimensions that are available in the file.

**Acceptance Scenarios**:

1. **Given** a valid supported XTrackCAD layout file, **When** the user opens it and requests layout information, **Then** the assistant receives a structured summary containing the layout identity and every supported metadata and bounds value available in that file.
2. **Given** a layout lacking an optional metadata or bounds value, **When** the user requests layout information, **Then** the response identifies that value as unavailable rather than inventing it.
3. **Given** a valid layout, **When** it is inspected, **Then** its contents and modification time remain unchanged.

---

### User Story 2 - Enumerate Supported Track Objects (Priority: P2)

A model railway designer asks an assistant what track objects a layout contains so that they can understand the existing plan before proposing a change.

**Why this priority**: Listing supported objects makes the summary useful for practical layout analysis and validates that file data can be mapped into an understandable model.

**Independent Test**: Open a fixture containing supported track objects and request the track list; compare the returned object identifiers, types, and available positions or orientations with the fixture's expected values.

**Acceptance Scenarios**:

1. **Given** a layout containing supported track sections and turnouts, **When** the user lists tracks, **Then** the assistant receives one structured entry for each supported object and can distinguish turnouts from other supported track sections.
2. **Given** a layout containing an unsupported object, **When** the user lists tracks, **Then** the assistant reports the unsupported object or feature clearly without omitting that fact from the result.

---

### User Story 3 - Receive Actionable Failure Information (Priority: P3)

A model railway designer gives the assistant a missing, malformed, or unsupported layout file and receives a clear result that explains whether inspection can continue.

**Why this priority**: Trust in inspection depends on making failures visible rather than returning incomplete data as if it were complete.

**Independent Test**: Submit missing, malformed, and unsupported-version fixtures and verify that each response is structured, identifies the file or feature involved, and causes no filesystem modification.

**Acceptance Scenarios**:

1. **Given** a nonexistent or unreadable path, **When** the user tries to open it, **Then** the assistant receives a failure that identifies the path and access problem.
2. **Given** a malformed layout, **When** the user tries to open it, **Then** the assistant receives a failure or diagnostic that identifies the parsing problem without presenting a successful layout summary.
3. **Given** a layout containing unknown features, **When** the known portion can still be inspected, **Then** the assistant receives the supported results together with explicit warnings about unknown features.

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
- **FR-009**: The system MUST make its read-only workflow usable on Linux and avoid assumptions that prevent later use on Windows or macOS.

### Key Entities *(include if feature involves data)*

- **Layout source**: A user-supplied native XTrackCAD layout file selected for read-only inspection.
- **Inspection session**: The current successfully opened layout and the diagnostics created while reading it.
- **Layout summary**: Supported metadata, bounds, dimensions, and declared availability of omitted values.
- **Track object**: A supported section or turnout with a stable source-derived identifier, type, and available geometric information.
- **Diagnostic**: A warning or error describing unreadable input, malformed data, or an unsupported feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the open-and-summary workflow for a representative valid layout in one MCP interaction sequence with no manual file conversion.
- **SC-002**: For each supported object in the committed representative fixtures, the returned object count and type match the fixture's expected result exactly.
- **SC-003**: Automated tests demonstrate that inspection leaves every test input byte-for-byte unchanged.
- **SC-004**: Automated tests cover a valid layout, a malformed layout, and a layout with at least one unsupported feature, and each produces the expected success or diagnostic outcome.
- **SC-005**: A client can start the server and invoke the read-only workflow over the selected standard input/output transport on the supported development platform.

## Assumptions

- The initial compatibility target is the current stable XTrackCAD layout-file form represented by the first legally retainable fixtures; exact version compatibility will be recorded with those fixtures.
- The first feature is intentionally limited to inspection; creation, modification, native writing, visual export, and parts-list export are out of scope.
- The first proof of concept supports only file paths explicitly supplied by the user or MCP client and does not scan directories.
- Supported metadata, objects, bounds, and connections depend on demonstrated parser coverage; unavailable fields are reported as unavailable rather than inferred.
- Parser evaluation may result in a direct dependency, an adapter, or a small in-project reader; the chosen implementation must preserve the specified observable behavior.
