# Track parameter catalogue retrieval

Status: required follow-on capability; not yet implemented. This document records project requirements and design direction for a subsequent Spec-Kit feature. The initial `001-readonly-layout-inspection` scope remains unchanged.

## Purpose

After opening an XTrackCAD layout, an assistant needs the available straights, curves, turnouts, crossings, and other parts for the relevant track systems, including parts not already placed. These definitions are necessary to design extensions and complete layouts using actual catalogue geometry.

## Native format facts

XTrackCAD parameter libraries use `.xtp` files. A library has a `CONTENTS` label and may have `SUBCONTENTS` groupings. Its native `TURNOUT` object type covers sectional straights, curves, crossings, and other track objects as well as physical turnouts. Do not classify every catalogue `TURNOUT` record as a physical switch.

Placed turnout and structure definitions are copied into the `.xtc` layout. A layout therefore remains inspectable without the original library, and its placed parts do not establish the complete available catalogue. One layout can mix libraries and custom definitions; one track system can span several files.

XTrackCAD maintains mappings from `CONTENTS` labels to filenames in its configuration. These may be useful resolution hints, but labels and historical mappings are not proof of an exact source definition.

Source: [XTrackCAD parameter file information](https://sourceforge.net/p/xtrkcad-fork/wiki/ParameterFileInformation/), especially Basic Information, File Headers, Object Headers, and Object Format.

## Required behaviour

1. Accept explicitly configured library files or directories. Read only those sources; the initial implementation must not require an XTrackCAD process or an internet download.
2. After a successful layout load, resolve candidate libraries from configured sources using available part identity and scale information. Report candidates and supporting evidence without claiming that a matching label proves the original source.
3. Allow the client to select one or more libraries explicitly, including for layouts with no catalogue-labelled tracks. Do not require every selected library to have a part already placed.
4. Distinguish resolution states such as unconfigured, no match, candidates requiring selection, selected, and selected with unavailable or unsupported content. State whether selection came from the client or an unambiguous automatic match.
5. Expose the full supported catalogue in selected libraries, not only the intersection with placed parts. Support search by available manufacturer, catalogue number, description, scale, and part category; return bounded pages with deterministic ordering.
6. Give each library and part an identity that distinguishes duplicate catalogue numbers and different source files. Include source path, library labels, and a content fingerprint so clients can recognize the exact definition retrieved.
7. Return supported part geometry in library-local coordinates, endpoints and directions, and named traversal routes where defined. Include explicit units and coordinate conventions. Preserve the native type and label; report unavailable classification or dimensions rather than guessing.
8. Preserve scale and any explicit gauge information separately. Do not infer gauge compatibility from scale or similar names alone. A candidate match is not a guarantee that two parts can connect.
9. Report malformed or unsupported definitions with source locations and completeness information. A partially understood definition must not appear ready for placement. Other supported parts should remain accessible when their record boundaries can be recovered reliably.
10. Missing, unreadable, or ambiguous libraries must not turn a valid layout load into a failure. Existing layout summary and track inspection must remain available with catalogue diagnostics.
11. Scope library resolution and selection to the current layout session. Opening another layout recomputes resolution; a failed layout open clears the prior session's selections and layout-specific results. Configured library sources may persist independently.
12. Keep both layouts and parameter files unchanged. Catalogue lookup does not authorize part placement, layout editing, library modification, or native writing.

## Proposed MCP workflow

Tool names and payloads below are design candidates, not implemented contracts.

| Operation | Intended result |
|---|---|
| Configure library sources at server startup | Establish explicit `.xtp` files or directories available for lookup; document the eventual cross-platform configuration mechanism |
| `open_layout(path)` | Preserve the existing inspection result and add catalogue resolution status and diagnostics |
| `list_track_libraries()` | List configured libraries, labels, availability, candidate matches, evidence, and current selection |
| `select_track_libraries(library_ids)` | Select one or more libraries explicitly for this layout session |
| `list_track_parts(filters, cursor, limit)` | List supported and flagged unsupported catalogue entries in selected libraries, including unplaced parts |
| `get_track_part(library_id, part_id)` | Return identity, provenance, supported local geometry, endpoints, routes, units, and completeness diagnostics |

The layout model owns placed instances. A separate catalogue model owns reusable definitions; resolution associates them without replacing the geometry already present in a layout. Future placement can instantiate a selected definition with a position and rotation.

## Acceptance cases for the feature specification

- A fixture layout uses one part from a configured fixture library containing at least a straight, curve, turnout, and crossing. After opening it, the assistant can retrieve all four definitions, including the three unplaced ones, with expected geometry and units.
- A mixed-system layout resolves multiple candidate libraries. Explicit selection exposes each catalogue without merging colliding part numbers.
- Two libraries contain the same manufacturer, description, part number, and scale. The result exposes ambiguity and source identities; it does not silently choose one.
- No libraries are configured, or a configured file is missing or unreadable. The layout still opens and its placed tracks remain inspectable; catalogue status explains the limitation.
- An empty layout or a layout containing only custom geometry allows explicit library selection and retrieval of unplaced parts.
- A selected library contains an unsupported definition alongside supported definitions. Diagnostics identify the affected definition, and it is not advertised as complete geometry.
- Opening a different layout or failing to open one never exposes the previous layout's library selections as current.
- Automated checks confirm that lookup preserves layout and parameter-file bytes and modification times.

## Decisions for planning

- Select the first real track-system library and verify its redistribution terms before committing upstream data. Use independently authored fixtures for basic parser tests.
- Define the supported `.xtp` record subset, category classification rules, route representation, and recovery rules using native documentation and representative files.
- Define configuration precedence, directory traversal limits, refresh behaviour for changed sources, pagination, and stable identifier rules.
- Determine whether importing XTrackCAD's existing configuration mappings is useful after explicit source configuration works. Do not make it a prerequisite.

Native writing, catalogue editing, automatic downloading, geometric placement, connection solving, and full layout design are later features. This capability supplies their reusable part data.
