# Tasks: Read-Only Layout Inspection

**Input**: Design artifacts from `specs/001-readonly-layout-inspection/`, including the 2026-10-31 clarifications.
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/read-only-tools.md, quickstart.md.
**Tests**: Required by FR-008 and SC-003–SC-006; extend existing tests before implementing changed behavior.
**Status**: Regenerated after clarification and replanning. This list supersedes the previous 38-task baseline/convergence list; IDs are assigned in execution order. Existing code is starting material, not evidence of completion. Every task remains unchecked until implementation verifies it against the revised contract.

## Format and paths

Each task has a checkbox, unique sequential ID, story label when applicable, and concrete repository paths. `[P]` indicates work on independent files after shared prerequisites. Paths use the agreed flat Rust modules: `src/layout.rs`, `src/xtc.rs`, and `src/mcp.rs`.

## Phase 1: Setup

**Goal**: Verify the Cargo executable/library project and establish reproducible dependency resolution.

- [X] T001 Verify Cargo package identity, GPL-3.0-only metadata, library and executable targets, and required SDK/Serde/Tokio/schema dependencies in `Cargo.toml`, `Cargo.lock`, `src/lib.rs`, and `src/main.rs`; retain the official RMCP STDIO implementation and no direct external XTrackCAD parser dependency.
- [X] T002 Verify the rolling stable Rust channel and Rust 2024 edition in `rust-toolchain.toml` and `Cargo.toml`, preserve existing ignore rules while covering Rust artifacts in `.gitignore`, and document compiler-version recording in `specs/001-readonly-layout-inspection/quickstart.md`.
- [X] T003 [P] Record actual dependency licenses and attribution in `THIRD_PARTY_LICENSES.md` using resolved dependency metadata; flag unresolved licensing facts rather than assuming terms.

## Phase 2: Foundational

**Goal**: Establish owned types and native-format boundaries shared by all stories. Complete this phase before story implementation.

- [X] T004 Define `LayoutSource` and coherent inspection-session state in `src/layout.rs` with the constraints “Must name a readable regular `.xtc` file”, “Capture a testable fingerprint; never modify the file”, and “Required after a successful open” for source and layout; keep source, layout, and diagnostics in one consistent session snapshot.
- [X] T005 Define typed summary/version/room/bounds fields in `src/layout.rs`: format version is “Required validated integer 12; never inferred from an application version”; application version is “Required source text; informational, independent of format acceptance”; room dimensions are finite positive inch values or null; bounds are finite ordered extrema with inch units or null.
- [X] T006 Define track, endpoint, geometry, and diagnostic types in `src/layout.rs`: IDs are “Unique per session; never array-index derived”; kinds are `straight`, `curve`, or `turnout`; coordinates/radii/lengths carry inches; angles carry degrees and clockwise-from-positive-Y convention; “Geometry values are finite; unsupported or unavailable geometry is never represented by a fabricated zero.”
- [X] T007 Establish reader/adapter boundaries inside `src/xtc.rs`, mapping native records into the owned `src/layout.rs` types; validate unique IDs and preserve source locations; retain local turnout track segments separately from decorative segments.
- [X] T008 Define shared input/result schema and diagnostic mapping in `src/mcp.rs` per `specs/001-readonly-layout-inspection/contracts/read-only-tools.md`; “All optional result fields use explicit null rather than omission”; use stable codes and warning/error severities with line/record references when available.

## Phase 3: User Story 1 — Inspect a Layout Summary (P1, MVP)

**Goal**: Open format-12 layouts and report source, metadata, room dimensions, counts, and complete-or-unavailable bounds.

**Independent validation**: Launch the executable over STDIO, open `layouts/mrkln_sample.xtc`, and verify source identity, two titles, HO scale, 96-by-48 inch room dimensions, four turnout records, and reliable track bounds independently of room size. For incomplete geometry, return null bounds with a diagnostic. Verify source bytes and modification time are unchanged.

### Tests first

- [X] T009 [US1] Add original, provenance-described format-12 fixtures in `tests/fixtures/authored/` for metadata, straight tracks, circular arcs, and compound turnouts; retain `layouts/mrkln_sample.xtc` as the real compatibility input; provide expected geometry and source hashes without copying unlicensed layouts.
- [X] T010 [US1] Write or extend `tests/parser_tests.rs` for declared metadata, separate integer format/application versions, UTF-8 titles and labels, explicit room units, null absent values, correct object counts, and byte/mtime preservation across all valid fixtures (FR-002, FR-006, FR-010, FR-011; SC-002, SC-003, SC-006).
- [X] T011 [US1] Write analytical geometry tests in `tests/bounds_tests.rs` for lines, arc cardinal extrema, full circles, signed-radius direction, rotated asymmetric turnout S/C segments, and ignored decorative L/A segments; assert no endpoint-only or room-size substitute bounds and null bounds for empty/unknown/incomplete track geometry (FR-015).
- [X] T012 [US1] Write or extend the actual executable STDIO test in `tests/mcp_stdio_tests.rs` to discover tools, open the sample, call `get_layout_info`, and verify source, summary, units, null conventions, immediate diagnostics, and source integrity using absolute fixture paths and bounded process/request timeouts (FR-001, FR-011, FR-013; SC-001, SC-005).

### Implementation

- [X] T013 [US1] Implement format-12 UTF-8 header/metadata parsing in `src/xtc.rs`, preserving declared title text and distinct format/application versions, finite positive room dimensions, and explicit metadata unavailability; retain source-path and record-location context (FR-002, FR-010, FR-011).
- [X] T014 [US1] Complete structural parsing of `STRAIGHT`, `CURVE`, and `TURNOUT` records in `src/xtc.rs`, including correct native field offsets, endpoints, signed radius and sweep semantics, complete segment boundaries, and transformed S/C centerline segments; map source-order object counts into `src/layout.rs` (FR-003, FR-004, FR-011, FR-015).
- [X] T015 [US1] Calculate complete world-space track centerline bounds in `src/xtc.rs` using line endpoints and arc interior cardinal extrema after applying turnout transforms; return `bounds: null` plus `bounds_unavailable` for empty layouts, unknown potentially-track objects, or any uninterpretable track geometry; exclude decorations and track width (FR-015).
- [X] T016 [US1] Implement source identity/fingerprint and atomic replacement or invalidation of the inspection session in `src/mcp.rs` and `src/layout.rs`; a failed open must clear earlier usable state, and read-only calls must leave source contents and modification time unchanged (FR-006, FR-007).
- [X] T017 [US1] Implement contract-compliant `open_layout` and `get_layout_info` outputs in `src/mcp.rs`, including source path/format, separate version fields, independent room dimensions and bounds, and all inspection diagnostics on successful open (FR-001, FR-002, FR-011, FR-013, FR-015).
- [X] T018 [US1] Wire typed tools and STDIO transport through `src/main.rs` and `src/mcp.rs`, keep protocol stdout free of non-protocol output, and validate the US1 parser, bounds, and subprocess test cases in `tests/parser_tests.rs`, `tests/bounds_tests.rs`, and `tests/mcp_stdio_tests.rs` (SC-001, SC-005).

**Checkpoint**: The summary workflow satisfies US1 on its own; listing details is validated in US2.

## Phase 4: User Story 2 — Enumerate Supported Track Objects (P2)

**Goal**: Return every supported track in source order with reliable identity, geometry, units, and connection state.

**Independent validation**: Through `open_layout` and `list_tracks`, inspect both the mixed straight/curve fixtures and the supplied four-turnout sample. Compare expected IDs, kinds, positions, directions, labels, and connected/open endpoints.

### Tests first

- [X] T019 [US2] Extend `tests/parser_tests.rs` with exact expected IDs, stable ordering, scale, coordinates, orientation, radius/sweep where available, UTF-8 labels, track/turnout counts, and open/connected endpoints for the sample and mixed-track fixtures (FR-003, FR-004, FR-010, FR-012; SC-002, SC-006).
- [X] T020 [P] [US2] Extend `tests/mcp_stdio_tests.rs` with `list_tracks` calls asserting all per-field units/angle conventions, four turnout entries in source order, mixed track kinds, and `no_open_layout` before opening; test the exposed tool schemas and structured result shape against the contract (FR-003, FR-004, FR-012).
- [X] T021 [US2] Add duplicate-ID and unresolved-endpoint fixture assertions in `tests/parser_tests.rs`: duplicates must fail with `malformed_record`, while dangling references produce `invalid_reference` with source location; ensure references never resolve by array position (data-model TrackObject).

### Implementation

- [X] T022 [US2] Map native IDs and object kinds to stable owned track records in `src/xtc.rs` and `src/layout.rs`; validate uniqueness, preserve source order, distinguish turnouts from straight/curved track, and preserve UTF-8 catalogue labels (FR-003, FR-004, FR-010).
- [X] T023 [US2] Map turnout and simple-track endpoint position/direction, open/connected state, and target identity in `src/xtc.rs`; validate references after reading all tracks and attach `invalid_reference` source diagnostics without inventing missing targets (FR-012).
- [X] T024 [US2] Complete the per-kind serialized geometry in `src/layout.rs`, with explicit inch coordinates/radii/lengths and degree orientations/sweeps; preserve native direction semantics and use explicit null for unavailable geometry (data-model TrackObject; contract stability rules).
- [X] T025 [US2] Implement `list_tracks` in `src/mcp.rs` to expose application-owned track data in stable source order, include unsupported-feature diagnostics without implying completeness, and return `no_open_layout` when the session is unavailable (FR-003, FR-004, FR-005, FR-012).
- [X] T026 [US2] Verify the US2 parser/contract cases in `tests/parser_tests.rs` and `tests/mcp_stdio_tests.rs`, including identical sample bytes/mtime after tool inspection and consistent count/type totals across summary and listing (SC-002, SC-003, SC-006).

## Phase 5: User Story 3 — Receive Actionable Failure Information (P3)

**Goal**: Make compatibility limits and unsafe input failures explicit without exposing stale or misleading results.

**Independent validation**: Use existing, directory, empty, missing, unreadable, malformed, and unsupported inputs. Format 12 must work independently of application version; all other format numbers must fail. Safe unsupported geometry can preserve inspection while yielding null bounds with diagnostics.

### Tests first

- [X] T027 [US3] Add fixtures and assertions in `tests/fixtures/authored/` and `tests/parser_tests.rs` for format 12 with differing application versions, format 11/13 rejection, and missing/malformed/conflicting version declarations; require `unsupported_version` or `malformed_record` exactly as FR-014 specifies.
- [X] T028 [US3] Extend `tests/parser_tests.rs` with empty/directory/missing/unreadable paths, archives, invalid UTF-8, non-finite/overflow numeric values, malformed supported headers and endpoints, missing/invalid `END$SEGS`, unsupported nested track segments, missing trailer, and unknown objects; verify stable severity/codes, source locations, safe bounds unavailability, and input integrity (FR-005, FR-008; SC-003, SC-004).
- [X] T029 [P] [US3] Extend `tests/mcp_stdio_tests.rs` with malformed tool arguments versus expected file-failure outcomes, immediate open warnings, malformed/version-rejected inputs after a successful open, and subsequent `get_layout_info`/`list_tracks` failures; preserve every test input (FR-005, FR-006, FR-007).

### Implementation

- [X] T030 [US3] Enforce format-version acceptance in `src/xtc.rs`: only integer format 12 is allowed; every other declared format fails with `unsupported_version`; missing/malformed/conflicting declarations fail with `malformed_record`; application-version differences never independently reject input (FR-014).
- [X] T031 [US3] Implement path validation and strict supported-record validation in `src/xtc.rs`, reporting stable codes with path/line/record context; reject unsafe malformed data, prevent silent invalid-number skips, and distinguish recognized decoration from unknown potentially-track content and unsupported track geometry (FR-005).
- [X] T032 [US3] Implement consistent diagnostic severity and propagation in `src/xtc.rs` and `src/mcp.rs`: unsafe parses fail and invalidate the session, while safely inspectable unsupported features produce warnings and unavailable bounds as appropriate; preserve the diagnostic on the immediate open result (FR-005, FR-007, FR-015).
- [X] T033 [US3] Run the US3 parser and executable tool failure tests in `tests/parser_tests.rs` and `tests/mcp_stdio_tests.rs` and ensure no unsuccessful open leaves usable prior layout state (FR-007, FR-008; SC-004).

## Phase 6: Polish and Cross-Cutting Validation

- [X] T034 Update `README.md` with actual supported format-12 records, separate application-version policy, complete-or-unavailable bounds behavior, build/client instructions, and current test commands; distinguish known support from unsupported features.
- [X] T035 [P] Add producer, origin/permission, SHA-256, expected records, and expected metadata for `layouts/mrkln_sample.xtc` in `layouts/manifest.json`, and complete original fixture provenance in `tests/fixtures/authored/README.md` without asserting unknown licensing facts.
- [X] T036 Add bounded timeout and child-process cleanup assertions to `tests/mcp_stdio_tests.rs` so a broken handshake or tool call fails predictably without leaving the launched executable running; retain portable process/path handling for Linux and future Windows/macOS support (FR-009; SC-005).
- [X] T037 Complete the remaining production error-handling/formatting cleanup in `src/layout.rs`, `src/xtc.rs`, `src/mcp.rs`, and `src/main.rs`; run `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, and `cargo test --locked`; fix issues that prevent these required checks from passing.
- [X] T038 Record actual `rustc`/`cargo` versions, final test totals, and Linux validation outcomes in `specs/001-readonly-layout-inspection/quickstart.md`; mark tasks complete only against passing evidence and confirm no pending task contradicts the clarified spec.

## Dependencies and execution order

```text
Setup T001–T003
  → Foundation T004–T008
  → US1 tests T009–T012 → US1 implementation T013–T018
  → US2 tests T019–T021 → US2 implementation T022–T026
  → US3 tests T027–T029 → US3 implementation T030–T033
  → Polish T034–T038
```

Every story depends on the shared foundation. US2 reuses US1 opening/parsing and US3 verifies its failure lifecycle; each story has its own independently executable acceptance scenario once its predecessors exist. New tests must fail for the intended missing behavior before their implementation, then pass. Existing passing tests should be extended, not deleted merely because result schemas changed.

Same-file edits are sequential: T010/T011 use separate files, but T019/T021 share `tests/parser_tests.rs`; T027/T028 also share it. Execute test groups first, then implementation; `[P]` never authorizes bypassing a dependency.

## Parallel examples

- **US1:** after T009 and the foundation, author parser/integrity tests (T010, `tests/parser_tests.rs`) alongside bounds tests (T011, `tests/bounds_tests.rs`) and STDIO tests (T012, `tests/mcp_stdio_tests.rs`); serialize edits within each file.
- **US2:** parser assertions (T019 followed by T021) can proceed alongside tool assertions (T020).
- **US3:** parser failure tests (T027 followed by T028) can proceed alongside tool/session failure tests (T029).
- **Polish:** README updates (T034) and fixture provenance (T035) affect independent files. Final validation follows both and all implementation work.

## Implementation strategy

Use the current implementation as a starting point and verify the regenerated tasks rather than blindly rebuilding completed behavior. Deliver US1's safe open-and-summary workflow first, including complete bounds or explicit unavailability (FR-015). Add detailed enumeration in US2, then finish compatibility and failure coverage in US3. The feature is complete only after all three story checkpoints and the final Linux checks pass.

## Requirement traceability

| Requirement | Tasks |
|---|---|
| FR-001 / SC-001 | T012, T017, T018 |
| FR-002 | T005, T010, T013, T017 |
| FR-003 / FR-004 / SC-002 | T014, T019, T020, T022, T025, T026 |
| FR-005 | T008, T021, T025, T028–T032 |
| FR-006 / SC-003 | T004, T010, T012, T016, T026, T028, T029 |
| FR-007 | T016, T029, T032, T033 |
| FR-008 / SC-004 | T009–T012, T019–T021, T027–T029, T033 |
| FR-009 | T001, T002, T018, T036–T038 |
| FR-010 | T010, T013, T019, T022 |
| FR-011 / SC-006 | T010, T012–T017, T019, T026 |
| FR-012 | T019–T021, T023–T026 |
| FR-013 | T004, T012, T016, T017 |
| FR-014 | T005, T027, T030 |
| FR-015 | T005–T007, T011, T014, T015, T017, T028, T032 |
| SC-005 | T012, T018, T036–T038 |

There is no current constitution gate beyond the project-context constraints because the checked-in constitution is an unfilled template. Product scope remains read-only XTrackCAD inspection; editing, native writing, exports, and cross-platform release certification remain outside this feature.

## Phase 7: Convergence

Four remaining gaps were identified by inspection after the 38-task implementation pass. Prior completion markers are retained; these tasks qualify the earlier completion claim.

- [X] T039 Validate the full shape of supported metadata records in `src/xtc.rs`, including rejecting or explicitly diagnosing trailing unsupported fields such as `MAPSCALE 53 garbage`, and add regression assertions with path/line diagnostics in `tests/parser_tests.rs` per FR-005 and T031 (partial; HIGH).
- [X] T040 Correct multi-turn curve length reporting in `src/xtc.rs`: the current `helix >= 1` path computes one revolution regardless of the declared turn count. Establish reliable native turn/sweep semantics before returning a length, or expose null with a diagnostic for unsupported helix geometry; preserve complete XY bounds only when reliably established. Add multi-turn and fractional-turn regression cases in `tests/parser_tests.rs` and `tests/bounds_tests.rs` per T024 and plan: evidence-based geometry (partial; MEDIUM).
- [X] T041 Add exact expected-value assertions for supported track scales, all sample endpoint coordinates/directions, mixed-track positions/orientations, radius/sweep values, and source-derived identities in `tests/parser_tests.rs` and `tests/mcp_stdio_tests.rs`; retain unit and null assertions, and fix any demonstrated adapter mismatches per FR-003, FR-012, SC-002, and T019–T024 (partial; MEDIUM).
- [X] T042 Extend the actual executable STDIO cases in `tests/mcp_stdio_tests.rs` to assert malformed/version-rejected open results after a successful open and verify both inspection tools then return `no_open_layout`; retain timeout, child-exit, and source-integrity assertions per FR-007, SC-004, and T033 (partial; MEDIUM).

## Phase 8: Review closeout

- [X] T043 Consume counted F3/Y3 and F4/Y4 decorative polygon vertex payloads in `src/xtc.rs` without treating their coordinates as unknown track records or invalidating reliable bounds; reject malformed/truncated payloads with source locations and add regression coverage in `tests/bounds_tests.rs` and `tests/parser_tests.rs` per FR-005, FR-015, and US1/AC5. The new bounds test failed before the fix; both polygon regressions pass after it.
